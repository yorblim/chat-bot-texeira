"""Verificación en vivo de gestión de disponibilidad por fecha específica en Cloud Run.
Valida:
1. Inserción de bloqueos por fecha ('sold_out' y 'limited') en Neon PostgreSQL.
2. Endpoint API /api/catalog/tours/{entity_id}/dates retornando fechas bloqueadas.
3. Respuestas deterministas en /test-chat para fecha agotada, fecha limitada y fecha disponible.
4. Flujo de reserva con derivación (handoff) etiquetando ticket con fecha agotada.
5. Limpieza exhaustiva de registros sintéticos en Neon PostgreSQL.
"""
import os
import sys
import json
import time
import base64
import urllib.request
from pathlib import Path
import subprocess

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from db_adapter import get_db_session

BASE_URL = "https://texeira-whatsapp-1038134693816.us-central1.run.app"
BATCH_PREFIX = f"live_date_{int(time.time())}"


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


def consultar_chat(headers, user_id, message):
    payload = json.dumps({"user_id": user_id, "message": message}).encode("utf-8")
    req = urllib.request.Request(f"{BASE_URL}/test-chat", data=payload, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status, json.loads(r.read().decode("utf-8"))


def consultar_api_dates(headers, entity_id):
    req = urllib.request.Request(f"{BASE_URL}/api/catalog/tours/{entity_id}/dates", headers=headers)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status, json.loads(r.read().decode("utf-8"))


def main():
    print("=" * 76)
    print("  VERIFICACIÓN EN VIVO: DISPONIBILIDAD POR FECHA EN CLOUD RUN")
    print("=" * 76)

    headers = obtener_credenciales()
    synthetic_users = []
    eid_so = "city-tour-cusco"
    date_so = "2026-11-20"
    eid_lim = "montana-7-colores"
    date_lim = "2026-11-25"

    try:
        # Paso 1: Configurar fechas en Neon PostgreSQL
        print("\n[PASO 1] Insertando fechas bloqueadas de prueba en Neon PostgreSQL...")
        now_iso = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        with get_db_session() as conn:
            # Asegurar tabla creada si es primera vez en Postgres
            import catalog_service
            catalog_service.init_catalog_db()

            # Limpiar posibles restos
            conn.execute(
                "DELETE FROM catalog_tour_dates WHERE entity_id IN (?, ?) AND tour_date IN (?, ?)",
                (eid_so, eid_lim, date_so, date_lim)
            )
            # Insertar City Tour sold_out
            conn.execute(
                "INSERT INTO catalog_tour_dates (entity_id, tour_date, status, notes, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (eid_so, date_so, "sold_out", "Bloqueo corporativo en vivo", now_iso, now_iso)
            )
            # Insertar Montana limited
            conn.execute(
                "INSERT INTO catalog_tour_dates (entity_id, tour_date, status, notes, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (eid_lim, date_lim, "limited", "Últimos 3 cupos en vivo", now_iso, now_iso)
            )
        print("  ✅ Registros insertados en Neon PostgreSQL con éxito.")

        # Paso 2: Validar API GET /api/catalog/tours/{entity_id}/dates
        print(f"\n[PASO 2] Verificando API GET /api/catalog/tours/{eid_so}/dates...")
        status_api, body_api = consultar_api_dates(headers, eid_so)
        print(f"  Status: {status_api}")
        dates_list = body_api if isinstance(body_api, list) else body_api.get("dates", [])
        print(f"  Fechas retornadas ({len(dates_list)}): {dates_list}")
        found_so = any(d.get("tour_date") == date_so and d.get("status") == "sold_out" for d in dates_list)
        assert found_so, f"No se encontró {date_so} con status sold_out en respuesta API: {body_api}"
        print("  ✅ [PASS] API /api/catalog/tours/{id}/dates responde correctamente con la fecha bloqueada.")

        # Paso 3: Consultar /test-chat para fecha agotada
        uid1 = f"{BATCH_PREFIX}_chat_so"
        synthetic_users.append(uid1)
        print(f"\n[PASO 3] Consultando chat: '¿Hay cupo para City Tour el {date_so}?'")
        status1, body1 = consultar_chat(headers, uid1, f"¿Hay cupo para City Tour el {date_so}?")
        resp1 = body1.get("response", "")
        print(f"  Respuesta recibida:\n{resp1}\n")
        assert "agotados" in resp1.lower() or "sin cupos" in resp1.lower(), "Debe indicar que los cupos están agotados"
        assert "20 de noviembre de 2026" in resp1, "Debe mencionar la fecha en formato legible"
        print("  ✅ [PASS] El bot respondió correctamente informando que los cupos están agotados para esa fecha.")

        # Paso 4: Consultar /test-chat para fecha limitada
        uid2 = f"{BATCH_PREFIX}_chat_lim"
        synthetic_users.append(uid2)
        print(f"\n[PASO 4] Consultando chat: '¿Disponibilidad para montaña 7 colores el 25 de noviembre de 2026?'")
        status2, body2 = consultar_chat(headers, uid2, "Disponibilidad para montaña 7 colores el 25 de noviembre de 2026")
        resp2 = body2.get("response", "")
        print(f"  Respuesta recibida:\n{resp2}\n")
        assert "cupos limitados" in resp2.lower(), "Debe indicar cupos limitados"
        assert "25 de noviembre de 2026" in resp2, "Debe mencionar la fecha en formato legible"
        print("  ✅ [PASS] El bot respondió correctamente indicando cupos limitados para la fecha solicitada.")

        # Paso 5: Consultar /test-chat para fecha disponible
        uid3 = f"{BATCH_PREFIX}_chat_avail"
        synthetic_users.append(uid3)
        print(f"\n[PASO 5] Consultando chat: '¿Tienen salidas para Valle Sagrado el 15 de diciembre de 2026?'")
        status3, body3 = consultar_chat(headers, uid3, "Tienen salidas para Valle Sagrado el 15 de diciembre de 2026")
        resp3 = body3.get("response", "")
        print(f"  Respuesta recibida:\n{resp3}\n")
        assert "cupos disponibles" in resp3.lower(), "Debe confirmar cupos disponibles"
        assert "15 de diciembre de 2026" in resp3, "Debe mencionar la fecha en formato legible"
        print("  ✅ [PASS] El bot respondió correctamente confirmando cupos disponibles para una fecha libre.")

        # Paso 6: Intentar reserva para fecha agotada y validar handoff tagging
        uid4 = f"{BATCH_PREFIX}_booking_so"
        synthetic_users.append(uid4)
        print(f"\n[PASO 6] Intentando reserva para fecha agotada: 'Quiero reservar City Tour para el {date_so}'")
        status4, body4 = consultar_chat(headers, uid4, f"Quiero reservar City Tour para el {date_so}")
        resp4 = body4.get("response", "")
        print(f"  Respuesta recibida:\n{resp4}\n")
        assert "agotados" in resp4.lower() or "lista de espera" in resp4.lower(), "Debe advertir de cupos agotados / lista de espera"

        # Verificar ticket en Neon
        with get_db_session() as conn:
            row = conn.execute("SELECT * FROM requests WHERE user_id = ?", (uid4,)).fetchone()
            assert row is not None, "El ticket debió ser registrado en Neon requests"
            q_val = row["question"] if hasattr(row, "__getitem__") else row[3]
            print(f"  Ticket question en Neon: {q_val}")
            assert "[Reserva - FECHA AGOTADA: 2026-11-20" in q_val, "El ticket debe estar etiquetado con la fecha agotada"
        print("  ✅ [PASS] Reserva para fecha agotada derivó a asesor etiquetando [Reserva - FECHA AGOTADA].")

        print("\n" + "=" * 76)
        print("  ¡TODAS LAS PRUEBAS EN VIVO PASARON SATISFACTORIAMENTE (6/6)!")
        print("=" * 76)

    finally:
        # Paso 7: Limpieza rigurosa de Neon
        print("\n[LIMPIEZA] Eliminando registros de prueba de Neon PostgreSQL...")
        with get_db_session() as conn:
            conn.execute(
                "DELETE FROM catalog_tour_dates WHERE entity_id IN (?, ?) AND tour_date IN (?, ?)",
                (eid_so, eid_lim, date_so, date_lim)
            )
            for uid in synthetic_users:
                conn.execute("DELETE FROM requests WHERE user_id = ?", (uid,))
        print("  ✅ Registros sintéticos eliminados. Neon PostgreSQL limpio.")


if __name__ == "__main__":
    main()
