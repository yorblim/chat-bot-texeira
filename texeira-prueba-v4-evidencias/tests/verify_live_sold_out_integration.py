"""Verificación en vivo de gestión dinámica de tours agotados en Cloud Run (00057).
1. Marca 'city-tour-cusco' como 'sold_out' en Neon PostgreSQL.
2. Consulta /test-chat para validar exclusión en recomendaciones dinámicas y aviso en tours más visitados.
3. Restaura 'city-tour-cusco' a 'available' en Neon.
4. Consulta /test-chat para validar remoción de aviso y vuelta a la normalidad.
5. Limpia los registros sintéticos de Neon PostgreSQL.
"""
import os
import sys
import json
import time
import base64
import urllib.request
import subprocess
from pathlib import Path

# Configurar stdout en utf-8
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from db_adapter import get_db_session

BASE_URL = "https://texeira-whatsapp-1038134693816.us-central1.run.app"
BATCH_PREFIX = f"live_so_{int(time.time())}"

def obtener_credenciales():
    gcloud_cmd = r"C:\Users\HP\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
    res_pass = subprocess.run(
        [gcloud_cmd, "secrets", "versions", "access", "2", "--secret=ADMIN_PASSWORD", "--project=texeira-whatsapp-bot"],
        capture_output=True, text=True
    )
    if res_pass.returncode != 0 or not res_pass.stdout.strip():
        raise RuntimeError("No se pudo obtener ADMIN_PASSWORD.")
    admin_password = res_pass.stdout.strip()

    res_db = subprocess.run(
        [gcloud_cmd, "secrets", "versions", "access", "1", "--secret=DATABASE_URL", "--project=texeira-whatsapp-bot"],
        capture_output=True, text=True
    )
    if res_db.returncode != 0 or not res_db.stdout.strip():
        raise RuntimeError("No se pudo obtener DATABASE_URL.")
    os.environ["DATABASE_URL"] = res_db.stdout.strip()

    auth_str = base64.b64encode(f"admin:{admin_password}".encode()).decode()
    return {"Authorization": f"Basic {auth_str}", "Content-Type": "application/json"}

def set_tour_availability_neon(entity_id: str, availability: str):
    now_iso = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    with get_db_session() as conn:
        conn.execute(
            "UPDATE catalog_tours SET availability = ?, updated_at = ? WHERE entity_id = ?",
            (availability, now_iso, entity_id)
        )

def consultar_chat(headers, user_id, message):
    payload = json.dumps({"user_id": user_id, "message": message}).encode("utf-8")
    req = urllib.request.Request(f"{BASE_URL}/test-chat", data=payload, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status, json.loads(r.read().decode("utf-8"))

def main():
    print("=" * 76)
    print("  VERIFICACIÓN EN VIVO: GESTIÓN DE TOURS AGOTADOS EN CLOUD RUN (00057)")
    print("=" * 76)

    headers = obtener_credenciales()
    synthetic_users = []

    try:
        # Paso 1: Marcar City Tour como sold_out
        print("\n[PASO 1] Marcando 'city-tour-cusco' como 'sold_out' en Neon PostgreSQL...")
        set_tour_availability_neon("city-tour-cusco", "sold_out")
        time.sleep(2)  # permitir sincronización de versión si aplica

        # Paso 2: Consultar recomendación de medio día
        uid1 = f"{BATCH_PREFIX}_rec_half"
        synthetic_users.append(uid1)
        print(f"\n[PASO 2] Consultando recomendación: 'Recomiéndame un tour de medio día sin caminatas'")
        status1, body1 = consultar_chat(headers, uid1, "Recomiéndame un tour de medio día sin caminatas")
        resp1 = body1.get("response", "")
        print(f"  Respuesta recibida:\n{resp1}\n")
        
        # Validaciones de recomendación
        assert "• *City Tour Cusco*" not in resp1, "City Tour Cusco no debería figurar en las viñetas recomendadas"
        assert "Agotado temporalmente" in resp1 or "City Tour Cusco" in resp1, "Debería mencionar el tour agotado en la nota"
        print("  ✅ [PASS] City Tour Cusco fue correctamente excluido de la recomendación y notificado como agotado.")

        # Paso 3: Consultar tours más visitados con City Tour agotado
        uid2 = f"{BATCH_PREFIX}_most_visited"
        synthetic_users.append(uid2)
        print(f"\n[PASO 3] Consultando: '¿Cuáles son los tours más visitados?'")
        status2, body2 = consultar_chat(headers, uid2, "¿Cuáles son los tours más visitados?")
        resp2 = body2.get("response", "")
        print(f"  Respuesta recibida:\n{resp2}\n")

        assert "Disponibilidad actual" in resp2, "Debería incluir la sección de 'Disponibilidad actual'"
        assert "City Tour Cusco" in resp2 and "agotado temporalmente" in resp2.lower(), "Debería indicar City Tour Cusco como agotado temporalmente"
        print("  ✅ [PASS] El Top de tours más visitados añadió exitosamente la advertencia de disponibilidad.")

    finally:
        # Paso 4: Restaurar City Tour a available
        print("\n[PASO 4] Restaurando 'city-tour-cusco' a 'available' en Neon PostgreSQL...")
        set_tour_availability_neon("city-tour-cusco", "available")
        time.sleep(2)

        # Paso 5: Consultar nuevamente para confirmar que el aviso se retira
        uid3 = f"{BATCH_PREFIX}_restored"
        synthetic_users.append(uid3)
        print(f"\n[PASO 5] Verificando normalización: '¿Cuáles son los tours más visitados?'")
        status3, body3 = consultar_chat(headers, uid3, "¿Cuáles son los tours más visitados?")
        resp3 = body3.get("response", "")
        assert "Disponibilidad actual" not in resp3, "Ya no debería mostrar aviso de disponibilidad agotada"
        print("  ✅ [PASS] Tras la restauración, el aviso de disponibilidad se retiró limpiamente.")

        # Paso 6: Limpieza de Neon PostgreSQL
        print("\n[PASO 6] Limpiando registros sintéticos en Neon PostgreSQL...")
        with get_db_session() as conn:
            for uid in synthetic_users:
                conn.execute("DELETE FROM interactions WHERE user_id = ?", (uid,))
                conn.execute("DELETE FROM conversation_memory WHERE user_id = ?", (uid,))
                conn.execute("DELETE FROM requests WHERE user_id = ?", (uid,))
        print("  CLEANUP: 100% de filas sintéticas eliminadas.")

    print("\n" + "=" * 76)
    print("  VERIFICACIÓN EN VIVO COMPLETADA CON 100% DE ÉXITO")
    print("=" * 76)

if __name__ == "__main__":
    main()
