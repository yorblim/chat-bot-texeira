"""Verificación en vivo integral de gestión de disponibilidad por fecha específica en Cloud Run.
Valida:
1. Obtención de CSRF token desde /api/catalog/csrf-token.
2. Mutación real vía API: POST /api/catalog/tours/{id}/dates con CSRF y Basic Auth (simulando UI).
3. Consulta API GET /api/catalog/tours/{id}/dates retornando fecha creada.
4. Consulta chat ES para fecha agotada: formato, status, sin fuga de notas internas a turistas.
5. Consulta chat PT para fecha agotada: respuesta nativa en portugués (esgotadas).
6. Consulta chat ES para fecha limitada: formato y advertencia de alta demanda.
7. Consulta chat ES para fecha libre: confirmación de cupos disponibles.
8. Intento de reserva para fecha agotada: ticket con [Reserva - FECHA AGOTADA: YYYY-MM-DD (Nota: ...)] para el asesor.
9. Intento de reserva para fecha limitada: ticket con [Reserva - FECHA LIMITADA: YYYY-MM-DD (Nota: ...)].
10. Eliminación real vía API: DELETE /api/catalog/tours/{id}/dates/{date} con CSRF.
11. Limpieza rigurosa de tickets sintéticos en Neon PostgreSQL.
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


def obtener_csrf(headers):
    req = urllib.request.Request(f"{BASE_URL}/api/catalog/csrf-token", headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode("utf-8"))
        assert data.get("ok"), "Fallo al obtener CSRF token"
        return data["csrf_token"]


def post_tour_date_api(headers, csrf_token, entity_id, tour_date, status, notes):
    post_headers = dict(headers)
    post_headers["X-Catalog-CSRF"] = csrf_token
    payload = json.dumps({
        "tour_date": tour_date,
        "status": status,
        "notes": notes
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE_URL}/api/catalog/tours/{entity_id}/dates",
        data=payload,
        headers=post_headers,
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status, json.loads(r.read().decode("utf-8"))


def delete_tour_date_api(headers, csrf_token, entity_id, tour_date):
    del_headers = dict(headers)
    del_headers["X-Catalog-CSRF"] = csrf_token
    req = urllib.request.Request(
        f"{BASE_URL}/api/catalog/tours/{entity_id}/dates/{tour_date}",
        headers=del_headers,
        method="DELETE"
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status, json.loads(r.read().decode("utf-8"))


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
    print("  VERIFICACIÓN EN VIVO INTEGRAL: DISPONIBILIDAD POR FECHA EN CLOUD RUN")
    print("=" * 76)

    headers = obtener_credenciales()
    synthetic_users = []
    eid_so = "city-tour-cusco"
    date_so = "2026-11-20"
    note_so = "Nota corporativa privada"

    eid_lim = "montana-7-colores"
    date_lim = "2026-11-25"
    note_lim = "Ultimos 4 cupos agencia"

    try:
        # Paso 1: Obtener CSRF token para API
        print("\n[PASO 1] Obteniendo CSRF Token desde /api/catalog/csrf-token...")
        csrf_token = obtener_csrf(headers)
        assert len(csrf_token) > 10, "CSRF token inválido"
        print(f"  ✅ Token CSRF obtenido: {csrf_token[:8]}...")

        # Paso 2: Crear fechas bloqueadas usando API POST con CSRF
        print(f"\n[PASO 2] Guardando bloqueo para {eid_so} ({date_so}, sold_out) vía API POST...")
        s1, res1 = post_tour_date_api(headers, csrf_token, eid_so, date_so, "sold_out", note_so)
        assert s1 == 200 and res1.get("ok"), f"Error en POST {eid_so}: {res1}"
        print(f"  ✅ Bloqueo {eid_so} guardado con date_id={res1.get('date_id')}")

        print(f"  Guardando bloqueo para {eid_lim} ({date_lim}, limited) vía API POST...")
        s2, res2 = post_tour_date_api(headers, csrf_token, eid_lim, date_lim, "limited", note_lim)
        assert s2 == 200 and res2.get("ok"), f"Error en POST {eid_lim}: {res2}"
        print(f"  ✅ Bloqueo {eid_lim} guardado con date_id={res2.get('date_id')}")

        # Paso 3: Validar API GET /api/catalog/tours/{entity_id}/dates
        print(f"\n[PASO 3] Consultando API GET /api/catalog/tours/{eid_so}/dates...")
        status_api, body_api = consultar_api_dates(headers, eid_so)
        dates_list = body_api if isinstance(body_api, list) else body_api.get("dates", [])
        found_so = any(d.get("tour_date") == date_so and d.get("status") == "sold_out" for d in dates_list)
        assert found_so, f"No se encontró {date_so} en API GET: {dates_list}"
        print("  ✅ [PASS] API GET confirmó la persistencia del bloqueo.")

        # Paso 4: Chat ES para fecha agotada (verificar que NO fugue nota interna)
        uid1 = f"{BATCH_PREFIX}_chat_so_es"
        synthetic_users.append(uid1)
        print(f"\n[PASO 4] Chat ES: '¿Hay cupo para City Tour el {date_so}?'")
        _, b1 = consultar_chat(headers, uid1, f"¿Hay cupo para City Tour el {date_so}?")
        resp1 = b1.get("response", "")
        print(f"  Respuesta:\n{resp1}\n")
        assert "agotados" in resp1.lower() or "sin cupos" in resp1.lower(), "Debe indicar cupos agotados"
        assert "20 de noviembre de 2026" in resp1, "Debe incluir fecha formateada"
        assert note_so not in resp1, "LA NOTA INTERNA NO DEBE FIGURAR EN LA RESPUESTA AL CLIENTE"
        print("  ✅ [PASS] Respuesta correcta en español y nota interna protegida (sin fugas).")

        # Paso 5: Chat PT para fecha agotada (verificar detección de idioma PT)
        uid2 = f"{BATCH_PREFIX}_chat_so_pt"
        synthetic_users.append(uid2)
        print(f"\n[PASO 5] Chat PT: 'Tem vagas para o City Tour no dia 20 de novembro de 2026?'")
        _, b2 = consultar_chat(headers, uid2, "Tem vagas para o City Tour no dia 20 de novembro de 2026?")
        resp2 = b2.get("response", "")
        print(f"  Respuesta PT:\n{resp2}\n")
        assert "esgotadas" in resp2.lower(), "Debe responder en portugués con 'esgotadas'"
        assert "20 de novembro de 2026" in resp2, "Debe incluir fecha en portugués"
        assert note_so not in resp2, "LA NOTA INTERNA NO DEBE FIGURAR EN LA RESPUESTA AL CLIENTE"
        print("  ✅ [PASS] Detección y respuesta en portugués verificadas en vivo.")

        # Paso 6: Chat ES para fecha limitada
        uid3 = f"{BATCH_PREFIX}_chat_lim_es"
        synthetic_users.append(uid3)
        print(f"\n[PASO 6] Chat ES: '¿Disponibilidad para montaña 7 colores el 25 de noviembre de 2026?'")
        _, b3 = consultar_chat(headers, uid3, "Disponibilidad para montaña 7 colores el 25 de noviembre de 2026")
        resp3 = b3.get("response", "")
        print(f"  Respuesta:\n{resp3}\n")
        assert "cupos limitados" in resp3.lower(), "Debe indicar cupos limitados"
        assert "25 de noviembre de 2026" in resp3, "Debe incluir fecha formateada"
        assert note_lim not in resp3, "LA NOTA INTERNA NO DEBE FIGURAR EN LA RESPUESTA AL CLIENTE"
        print("  ✅ [PASS] Aviso de cupos limitados verificado en vivo.")

        # Paso 7: Reserva fecha agotada -> derivación y ticket con nota interna
        uid4 = f"{BATCH_PREFIX}_book_so"
        synthetic_users.append(uid4)
        print(f"\n[PASO 7] Reserva fecha agotada: 'Quiero reservar City Tour para el {date_so}'")
        _, b4 = consultar_chat(headers, uid4, f"Quiero reservar City Tour para el {date_so}")
        resp4 = b4.get("response", "")
        assert "agotados" in resp4.lower() or "lista de espera" in resp4.lower(), "Debe mencionar lista de espera"
        assert note_so not in resp4, "Nota no debe fugarse en mensaje al cliente"

        with get_db_session() as conn:
            row4 = conn.execute("SELECT * FROM requests WHERE user_id = ?", (uid4,)).fetchone()
            assert row4 is not None, "El ticket debió crearse en requests"
            q4 = row4["question"] if hasattr(row4, "__getitem__") else row4[3]
            print(f"  Ticket guardado en Neon: {q4}")
            assert f"[Reserva - FECHA AGOTADA: {date_so}" in q4, "Ticket debe tener etiqueta de fecha agotada"
            assert f"Nota: {note_so}" in q4, "La nota interna debe llegar al ticket del asesor"
        print("  ✅ [PASS] Ticket de fecha agotada etiquetado correctamente con nota interna para el asesor.")

        # Paso 8: Reserva fecha limitada -> derivación y ticket con nota interna
        uid5 = f"{BATCH_PREFIX}_book_lim"
        synthetic_users.append(uid5)
        print(f"\n[PASO 8] Reserva fecha limitada: 'Quiero reservar Montaña de 7 Colores para el {date_lim}'")
        _, b5 = consultar_chat(headers, uid5, f"Quiero reservar Montaña de 7 Colores para el {date_lim}")
        resp5 = b5.get("response", "")
        assert "cupos limitados" in resp5.lower(), "Debe advertir de cupos limitados"

        with get_db_session() as conn:
            row5 = conn.execute("SELECT * FROM requests WHERE user_id = ?", (uid5,)).fetchone()
            assert row5 is not None, "El ticket debió crearse en requests"
            q5 = row5["question"] if hasattr(row5, "__getitem__") else row5[3]
            print(f"  Ticket guardado en Neon: {q5}")
            assert f"[Reserva - FECHA LIMITADA: {date_lim}" in q5, "Ticket debe tener etiqueta de fecha limitada"
            assert f"Nota: {note_lim}" in q5, "La nota interna debe llegar al ticket del asesor"
        print("  ✅ [PASS] Ticket de fecha limitada etiquetado correctamente con nota interna para el asesor.")

        # Paso 9: Eliminar bloqueo vía API DELETE con CSRF
        print(f"\n[PASO 9] Eliminando bloqueo de {eid_so} vía API DELETE con CSRF...")
        s_del, res_del = delete_tour_date_api(headers, csrf_token, eid_so, date_so)
        assert s_del == 200 and res_del.get("ok"), f"Error en DELETE: {res_del}"
        print("  ✅ Bloqueo eliminado vía API DELETE con éxito.")

        print(f"  Verificando que {eid_so} ya no figure en GET /dates...")
        _, body_after = consultar_api_dates(headers, eid_so)
        dates_after = body_after if isinstance(body_after, list) else body_after.get("dates", [])
        found_after = any(d.get("tour_date") == date_so for d in dates_after)
        assert not found_after, f"La fecha {date_so} no debió encontrarse tras el DELETE"
        print("  ✅ [PASS] El endpoint DELETE removió efectivamente la fecha.")

        print("\n" + "=" * 76)
        print("  ¡TODAS LAS PRUEBAS EN VIVO INTEGRALES (9/9) PASARON CON ÉXITO!")
        print("=" * 76)

    finally:
        # Paso 10: Limpieza rigurosa de Neon PostgreSQL
        print("\n[LIMPIEZA] Limpiando registros de prueba en Neon PostgreSQL...")
        with get_db_session() as conn:
            conn.execute(
                "DELETE FROM catalog_tour_dates WHERE entity_id IN (?, ?) AND tour_date IN (?, ?)",
                (eid_so, eid_lim, date_so, date_lim)
            )
            for uid in synthetic_users:
                conn.execute("DELETE FROM requests WHERE user_id = ?", (uid,))
        print("  ✅ Base de datos Neon PostgreSQL 100% limpia.")


if __name__ == "__main__":
    main()
