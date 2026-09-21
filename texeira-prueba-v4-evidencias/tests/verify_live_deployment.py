"""Script de verificación en vivo del servicio Cloud Run y base de datos Neon."""
import os
import sys
import json
import re
import base64
import urllib.request
import urllib.error
import subprocess
from pathlib import Path

# Configurar path local
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from db_adapter import get_db_session

def run_verification():
    print("=====================================================================")
    print("       VERIFICACIÓN EN VIVO: CLOUD RUN + NEON POSTGRESQL")
    print("=====================================================================")

    # 1. Recuperar secretos en memoria
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
    headers = {"Authorization": f"Basic {auth_str}", "Content-Type": "application/json"}
    base_url = "https://texeira-whatsapp-1038134693816.us-central1.run.app"

    # 2. Endpoint de salud /health
    print("\n[1/5] Verificando /health...")
    with urllib.request.urlopen(f"{base_url}/health", timeout=20) as r:
        assert r.status == 200
        body = json.loads(r.read().decode("utf-8"))
        assert body.get("status") == "ok"
        print("  PASS | /health responde 200 OK con {'status': 'ok'}")

    # 3. Endpoint raíz /
    print("\n[2/5] Verificando endpoint raíz /...")
    with urllib.request.urlopen(f"{base_url}/", timeout=20) as r:
        assert r.status == 200
        root_data = json.loads(r.read().decode("utf-8"))
        assert root_data.get("status") == "running"
        print(f"  PASS | / responde 200 OK (versión: {root_data.get('version')})")

    # 4. Seguridad de rutas administrativas
    print("\n[3/5] Verificando autenticación Basic Auth...")
    try:
        urllib.request.urlopen(f"{base_url}/dashboard", timeout=20)
        raise AssertionError("Fallo de seguridad: /dashboard sin auth no fue rechazado.")
    except urllib.error.HTTPError as e:
        assert e.code == 401
        print("  PASS | /dashboard sin credenciales es rechazado con HTTP 401.")

    req = urllib.request.Request(f"{base_url}/dashboard", headers=headers)
    with urllib.request.urlopen(req, timeout=20) as r:
        assert r.status == 200
        html = r.read().decode("utf-8")
        assert "Panel de Administración" in html or len(html) > 5000
        print(f"  PASS | /dashboard con credenciales responde HTTP 200 ({len(html)} bytes).")

    # 5. Interacciones conversacionales con usuario sintético
    print("\n[4/5] Probando flujo conversacional con usuario sintético...")
    user_id = "synthetic_pilot_audit_final"

    # Prueba A: Ayuda
    payload_ayuda = json.dumps({"user_id": user_id, "message": "ayuda"}).encode("utf-8")
    req = urllib.request.Request(f"{base_url}/test-chat", data=payload_ayuda, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        assert r.status == 200
        res = json.loads(r.read().decode("utf-8"))
        ans = res.get("response", "")
        assert not re.search(r"\+51|\b9\d{8}\b", ans), "Se detectó teléfono no solicitado en 'ayuda'"
        assert "/images/" not in ans, "Se detectó imagen no solicitada en 'ayuda'"
        print("  PASS | 'ayuda': responde 200 OK sin teléfonos ni imágenes no pedidas.")

    # Prueba B: Qué tours tienen
    payload_tours = json.dumps({"user_id": user_id, "message": "qué tours tienen"}).encode("utf-8")
    req = urllib.request.Request(f"{base_url}/test-chat", data=payload_tours, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        assert r.status == 200
        res = json.loads(r.read().decode("utf-8"))
        ans = res.get("response", "")
        assert not re.search(r"\+51|\b9\d{8}\b", ans), "Se detectó teléfono no solicitado en lista de tours"
        assert "/images/" not in ans, "Se detectó imagen no solicitada en lista de tours"
        assert "Tour" in ans or "Tours" in ans
        print("  PASS | 'qué tours tienen': responde 200 OK con lista limpia.")

    # 6. Verificación de persistencia en Neon PostgreSQL
    print("\n[5/5] Verificando persistencia y memoria en Neon PostgreSQL...")
    with get_db_session() as conn:
        interactions = conn.execute(
            "SELECT id, timestamp, user_id, user_message, bot_response FROM interactions WHERE user_id = ?",
            (user_id,)
        ).fetchall()
        assert len(interactions) == 2, f"Se esperaban 2 interacciones en Neon, encontradas: {len(interactions)}"
        print(f"  PASS | Se verificaron {len(interactions)} interacciones guardadas en tabla 'interactions'.")

        mem = conn.execute(
            "SELECT user_id, messages FROM conversation_memory WHERE user_id = ?",
            (user_id,)
        ).fetchall()
        assert len(mem) == 1, "Falta fila de memoria conversacional en Neon"
        turns = json.loads(mem[0][1])
        assert len(turns) == 4, f"Se esperaban 4 turnos (2 pares), encontrados: {len(turns)}"
        print(f"  PASS | Se verificaron {len(turns)} turnos en tabla 'conversation_memory'.")

        # Limpieza obligatoria de datos sintéticos
        conn.execute("DELETE FROM interactions WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM conversation_memory WHERE user_id = ?", (user_id,))
        print("  PASS | Limpieza completada: datos sintéticos eliminados de Neon PostgreSQL.")

    print("\n=====================================================================")
    print("  ¡TODAS LAS VERIFICACIONES EN VIVO FUERON SUPERADAS EXITOSAMENTE!")
    print("=====================================================================")


if __name__ == "__main__":
    run_verification()
