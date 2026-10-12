"""Batería de validación en vivo contra la API de Cloud Run (/test-chat) — Revisión 00052.
Valida navegación, catálogo core, recomendaciones especializadas (aclimatación/primer día),
métodos de pago, multilingüismo (ES, EN, PT, FR, IT), robustez y handoff con enlace directo.
Limpia automáticamente los registros sintéticos de Neon PostgreSQL.
"""
import os
import sys
import json
import re
import time
import base64
import urllib.request
import urllib.error
import subprocess
from datetime import datetime, timezone
from pathlib import Path

# Configurar stdout en utf-8 para evitar errores de charmap en consolas de Windows
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from db_adapter import get_db_session

BASE_URL = "https://texeira-whatsapp-1038134693816.us-central1.run.app"
BATCH_PREFIX = f"eval52_{int(time.time())}"
REVISION_NAME = "texeira-whatsapp-00052-brv"

CASOS = [
    {
        "id": "LIVE-01",
        "categoria": "Navegación",
        "input": "Hola",
        "descripcion": "Saludo inicial y bienvenida",
        "validar": lambda res, text: (
            res.get("status") == 200
            and not re.search(r"\+51|\b9\d{8}\b", text)
            and "/images/" not in text
            and any(w in text.lower() for w in ["hola", "texeira", "bienvenido", "tours", "experiencia"])
        )
    },
    {
        "id": "LIVE-02",
        "categoria": "Navegación",
        "input": "qué tours tienen",
        "descripcion": "Listado de tours activos categorizados",
        "validar": lambda res, text: (
            res.get("status") == 200
            and not re.search(r"\+51|\b9\d{8}\b", text)
            and "/images/" not in text
            and any(w in text.lower() for w in ["machu picchu", "montañas", "categoría", "categoria", "camino inca", "tours"])
        )
    },
    {
        "id": "LIVE-03",
        "categoria": "Ficha Técnica",
        "input": "Información de Camino Inca",
        "descripcion": "Ficha oficial de Camino Inca Clásico con tarifa oficial",
        "validar": lambda res, text: (
            res.get("status") == 200
            and "camino inca" in text.lower()
            and ("4 días" in text.lower() or "4 dias" in text.lower())
            and "790" in text
        )
    },
    {
        "id": "LIVE-04",
        "categoria": "Catálogo / Ausencia",
        "input": "Información de Choquequirao",
        "descripcion": "Manejo honesto de tour no activo en catálogo",
        "validar": lambda res, text: (
            res.get("status") == 200
            and not re.search(r"\$|\busd\b", text.lower())
            and any(w in text.lower() for w in ["asesor", "no dispon", "no figura", "no tengo", "catálogo", "catalogo"])
        )
    },
    {
        "id": "LIVE-05",
        "categoria": "Recomendaciones",
        "input": "¿Qué tours me recomiendas?",
        "descripcion": "Recomendación abierta con indagación de preferencias",
        "validar": lambda res, text: (
            res.get("status") == 200
            and any(w in text.lower() for w in ["interesa", "prefier", "tiempo", "caminata", "paisajes", "histórico"])
        )
    },
    {
        "id": "LIVE-06",
        "categoria": "Recomendaciones",
        "input": "Recomiéndame un tour de 4 días",
        "descripcion": "Filtro estricto de duración: 4 días",
        "validar": lambda res, text: (
            res.get("status") == 200
            and ("camino inca" in text.lower() or "inka jungle" in text.lower())
            and "maras" not in text.lower()
        )
    },
    {
        "id": "LIVE-07",
        "categoria": "Recomendaciones",
        "input": "Recomiéndame un tour de medio día sin caminatas",
        "descripcion": "Filtro estricto: medio día sin caminatas",
        "validar": lambda res, text: (
            res.get("status") == 200
            and ("city tour" in text.lower() or "maras" in text.lower())
            and "camino inca" not in text.lower()
        )
    },
    {
        "id": "LIVE-08",
        "categoria": "Recomendaciones",
        "input": "Recomiéndame un tour de 2 días",
        "descripcion": "Duración no existente en catálogo activo: respuesta honesta",
        "validar": lambda res, text: (
            res.get("status") == 200
            and any(w in text.lower() for w in ["no dispon", "no tenemos", "no encuentro", "asesor", "otra duración", "otra duracion", "disculp", "no puedo confirmar"])
        )
    },
    {
        "id": "LIVE-09",
        "categoria": "Multilingüismo (EN)",
        "input": "How much is the Inca Trail?",
        "descripcion": "Consulta de tarifa en inglés",
        "validar": lambda res, text: (
            res.get("status") == 200
            and "790" in text
            and ("inca" in text.lower() or "trail" in text.lower() or "usd" in text.lower())
        )
    },
    {
        "id": "LIVE-10",
        "categoria": "Multilingüismo (PT)",
        "input": "Quais passeios você recomenda?",
        "descripcion": "Recomendación en portugués",
        "validar": lambda res, text: (
            res.get("status") == 200
            and any(w in text.lower() for w in ["interessa", "prefere", "caminhada", "paisagens", "tempo", "recomendaç"])
        )
    },
    {
        "id": "LIVE-11",
        "categoria": "Multilingüismo (FR)",
        "input": "Quels circuits recommandez-vous?",
        "descripcion": "Recomendación en francés",
        "validar": lambda res, text: (
            res.get("status") == 200
            and any(w in text.lower() for w in ["recommand", "intéresse", "circuits", "souhaitez", "temps", "randonnée", "camino inca"])
        )
    },
    {
        "id": "LIVE-12",
        "categoria": "Multilingüismo (IT)",
        "input": "Quali tour consigliate?",
        "descripcion": "Recomendación en italiano",
        "validar": lambda res, text: (
            res.get("status") == 200
            and any(w in text.lower() for w in ["consigli", "interessa", "prefer", "tempo", "passeggiat", "tour", "cosa ti"])
        )
    },
    {
        "id": "LIVE-13",
        "categoria": "Robustez Lingüística",
        "input": "ninguno necesito que em recomiendes",
        "descripcion": "Resistencia a falso positivo de portugués por errata 'em'",
        "validar": lambda res, text: (
            res.get("status") == 200
            and any(w in text.lower() for w in ["interesa", "prefier", "caminatas", "paisajes", "cuéntame", "equipo", "tours"])
            and not any(w in text.lower() for w in ["interessa mais", "conte suas", "passeios"])
        )
    },
    {
        "id": "LIVE-14",
        "categoria": "Atención Humana",
        "input": "quiero hablar con un asesor",
        "descripcion": "Solicitud de atención humana con ticket y enlace WhatsApp directo",
        "validar": lambda res, text: (
            res.get("status") == 200
            and any(w in text.lower() for w in ["asesor", "solicitud", "registrada", "atención", "atencion"])
            and ("wa.me" in text or "pendiente de atención" in text.lower())
        )
    },
    {
        "id": "LIVE-15",
        "categoria": "FAQ Especializada",
        "input": "primer dia en cusco que me recomiendas aclimatacion",
        "descripcion": "Consejo de aclimatación y tours suaves de primer día (evita alta montaña)",
        "validar": lambda res, text: (
            res.get("status") == 200
            and any(w in text.lower() for w in ["aclimat", "soroche", "primer día", "primer dia", "altura"])
            and any(w in text.lower() for w in ["city tour", "maras"])
            and any(w in text.lower() for w in ["humantay", "colores", "alta montaña", "alta montana"])
        )
    },
    {
        "id": "LIVE-16",
        "categoria": "FAQ Especializada",
        "input": "cuáles son sus métodos de pago",
        "descripcion": "Información oficial de transferencias bancarias, tarjetas y oficina",
        "validar": lambda res, text: (
            res.get("status") == 200
            and any(w in text.lower() for w in ["transferencia", "bcp", "interbank"])
            and any(w in text.lower() for w in ["tarjeta", "visa", "mastercard"])
            and any(w in text.lower() for w in ["carmen quicllu", "oficina", "efectivo"])
        )
    }
]

def obtener_credenciales():
    gcloud_cmd = r"C:\Users\HP\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
    res_pass = subprocess.run(
        [gcloud_cmd, "secrets", "versions", "access", "2", "--secret=ADMIN_PASSWORD", "--project=texeira-whatsapp-bot"],
        capture_output=True, text=True
    )
    if res_pass.returncode != 0 or not res_pass.stdout.strip():
        raise RuntimeError("No se pudo obtener ADMIN_PASSWORD de Secret Manager.")
    admin_password = res_pass.stdout.strip()

    res_db = subprocess.run(
        [gcloud_cmd, "secrets", "versions", "access", "1", "--secret=DATABASE_URL", "--project=texeira-whatsapp-bot"],
        capture_output=True, text=True
    )
    if res_db.returncode != 0 or not res_db.stdout.strip():
        raise RuntimeError("No se pudo obtener DATABASE_URL de Secret Manager.")
    os.environ["DATABASE_URL"] = res_db.stdout.strip()

    auth_str = base64.b64encode(f"admin:{admin_password}".encode()).decode()
    return {"Authorization": f"Basic {auth_str}", "Content-Type": "application/json"}

def ejecutar_bateria():
    print("=" * 76)
    print(f"  BATERÍA DE VALIDACIÓN EN VIVO (CLOUD RUN /test-chat) — REVISIÓN 00052")
    print(f"  Revisión: {REVISION_NAME}")
    print(f"  Prefijo de sesión sintética: {BATCH_PREFIX}")
    print(f"  Endpoint: {BASE_URL}/test-chat")
    print("=" * 76)

    headers = obtener_credenciales()

    # Pre-calentamiento del contenedor para evitar timeout por cold-start
    print("\n[WARM-UP] Calentando instancia en Cloud Run...")
    warm_up_user = f"{BATCH_PREFIX}_warmup"
    warm_payload = json.dumps({"user_id": warm_up_user, "message": "ping"}).encode("utf-8")
    warm_req = urllib.request.Request(f"{BASE_URL}/test-chat", data=warm_payload, headers=headers)
    for intento in range(3):
        try:
            with urllib.request.urlopen(warm_req, timeout=60) as r:
                if r.status == 200:
                    print(f"  [WARM-UP OK] Instancia activa y lista (intento {intento+1}).")
                    break
        except Exception as e:
            print(f"  [WARM-UP WAIT] Intento {intento+1}: {e}")
            time.sleep(3)

    resultados = []
    aprobados = 0
    fallidos = 0
    synthetic_users_created = [warm_up_user]

    for c in CASOS:
        cid = c["id"]
        msg = c["input"]
        user_id = f"{BATCH_PREFIX}_{cid.lower().replace('-', '_')}"
        synthetic_users_created.append(user_id)

        print(f"\n[{cid}] ({c['categoria']}) Entrada: '{msg}'")
        payload = json.dumps({"user_id": user_id, "message": msg}).encode("utf-8")
        req = urllib.request.Request(f"{BASE_URL}/test-chat", data=payload, headers=headers)
        
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                latencia = round(time.time() - t0, 3)
                status_code = r.status
                body = json.loads(r.read().decode("utf-8"))
                bot_text = body.get("response", "")
                
                es_valido = c["validar"]({"status": status_code, "body": body}, bot_text)
                
                preview = bot_text[:110].replace("\n", " ").encode("ascii", "replace").decode("ascii") + ("..." if len(bot_text) > 110 else "")
                
                if es_valido:
                    aprobados += 1
                    estado = "PASS"
                    print(f"  [{estado}] ({latencia}s) -> {preview}")
                else:
                    fallidos += 1
                    estado = "FAIL"
                    print(f"  [{estado}] ({latencia}s) Falló criterio -> {preview}")
                
                resultados.append({
                    "id": cid,
                    "categoria": c["categoria"],
                    "input": msg,
                    "latency_sec": latencia,
                    "status_code": status_code,
                    "response_preview": preview,
                    "full_response": bot_text,
                    "route": body.get("route"),
                    "language": body.get("language"),
                    "passed": es_valido
                })
        except Exception as e:
            latencia = round(time.time() - t0, 3)
            fallidos += 1
            print(f"  [ERROR] ({latencia}s) {e}")
            resultados.append({
                "id": cid,
                "categoria": c["categoria"],
                "input": msg,
                "latency_sec": latencia,
                "error": str(e),
                "passed": False
            })

    # Verificación en Neon PostgreSQL
    print("\n" + "=" * 76)
    print("  VERIFICACIÓN DE PERSISTENCIA Y LIMPIEZA EN NEON POSTGRESQL")
    print("=" * 76)
    with get_db_session() as conn:
        total_interacciones = 0
        total_mem = 0
        total_req = 0
        for uid in synthetic_users_created:
            total_interacciones += conn.execute(
                "SELECT count(*) FROM interactions WHERE user_id = ?", (uid,)
            ).fetchone()[0]
            total_mem += conn.execute(
                "SELECT count(*) FROM conversation_memory WHERE user_id = ?", (uid,)
            ).fetchone()[0]
            total_req += conn.execute(
                "SELECT count(*) FROM requests WHERE user_id = ?", (uid,)
            ).fetchone()[0]

            # Limpieza obligatoria
            conn.execute("DELETE FROM interactions WHERE user_id = ?", (uid,))
            conn.execute("DELETE FROM conversation_memory WHERE user_id = ?", (uid,))
            conn.execute("DELETE FROM requests WHERE user_id = ?", (uid,))

        print(f"  Total interacciones registradas en Neon: {total_interacciones}")
        print(f"  Total memorias registradas en Neon: {total_mem}")
        print(f"  Total solicitudes (tickets) registradas en Neon: {total_req}")
        print("  CLEANUP: 100% de filas sintéticas eliminadas exitosamente de Neon PostgreSQL.")

    # Guardar reporte documental en docs/evaluaciones/
    reporte = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "revision": REVISION_NAME,
        "endpoint": f"{BASE_URL}/test-chat",
        "batch_prefix": BATCH_PREFIX,
        "total_cases": len(CASOS),
        "passed": aprobados,
        "failed": fallidos,
        "pass_rate_pct": round((aprobados / len(CASOS)) * 100, 2),
        "cases": resultados
    }
    
    docs_dir = PROJECT_ROOT / "docs" / "evaluaciones"
    docs_dir.mkdir(parents=True, exist_ok=True)
    report_file = docs_dir / f"EVALUACION_LIVE_CHAT_00052_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(reporte, f, ensure_ascii=False, indent=2)
    print(f"\n  Reporte guardado en: {report_file}")

    print("\n" + "=" * 76)
    print(f"  RESUMEN FINAL: {aprobados}/{len(CASOS)} APROBADOS ({reporte['pass_rate_pct']}%) | {fallidos} FALLIDOS")
    print("=" * 76)

    return fallidos == 0

if __name__ == "__main__":
    exito = ejecutar_bateria()
    sys.exit(0 if exito else 1)
