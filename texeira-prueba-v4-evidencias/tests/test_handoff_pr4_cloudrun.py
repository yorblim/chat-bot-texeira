"""
test_handoff_pr4_cloudrun.py — Validación en vivo de PR #4 en Google Cloud Run (00023-rp9)

Verifica de punta a punta a través de la API pública y protegida de Cloud Run:
  1. Estado de salud (/health -> 200).
  2. Protección de seguridad (/handoffs anónimo -> 401).
  3. Consola de asesores con Basic Auth (/handoffs -> 200) y extracción de token CSRF.
  4. Generación de ticket de derivación humana vía /test-chat.
  5. Protección CSRF: POST /handoffs/{id} sin token -> 403 Forbidden.
  6. Transición inválida: Cierre directo de ticket pending sin tomar -> 400 Bad Request.
  7. Toma de ticket: Transición a in_progress -> 200 OK.
  8. Validación estricta de tipos: send_to_customer='false' (string) -> 400 Bad Request.
  9. Cierre con nota interna: status='closed', send_to_customer=False -> 200 OK (ok=True, message_sent=False).
  10. Idempotencia y protección contra doble cierre: Repetir POST de cierre -> 400 Bad Request.
  11. Consulta en /handoffs/data para verificar estado final 'closed'.
"""

import os
import re
import sys
import json
import base64
import subprocess
import urllib.request
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

cloud_cmd = r"C:\Users\HP\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"

def get_secret(name, version="2"):
    res = subprocess.run(
        [cloud_cmd, "secrets", "versions", "access", version, f"--secret={name}", "--project=texeira-whatsapp-bot"],
        capture_output=True, text=True
    )
    if res.returncode != 0:
        raise RuntimeError(f"No se pudo acceder al secreto {name}: {res.stderr}")
    return res.stdout.strip()

def run_test():
    print("=====================================================================")
    print("   VALIDACIÓN EN VIVO: PR #4 EN GOOGLE CLOUD RUN (00023-rp9)")
    print("=====================================================================")

    base_url = "https://texeira-whatsapp-1038134693816.us-central1.run.app"

    # Obtener credenciales administrativas
    print("\n[1/6] Obteniendo credenciales administrativas de Secret Manager...")
    admin_pass = get_secret("ADMIN_PASSWORD", "2")
    auth_header = "Basic " + base64.b64encode(f"admin:{admin_pass}".encode()).decode()
    auth_headers = {
        "Authorization": auth_header,
        "Content-Type": "application/json"
    }
    print("  PASS | Credenciales obtenidas exitosamente.")

    # 1. Health y Seguridad Anónima
    print("\n[2/6] Verificando /health y seguridad en /handoffs...")
    req_health = urllib.request.Request(f"{base_url}/health")
    with urllib.request.urlopen(req_health, timeout=45) as r:
        assert r.status == 200
        data_health = json.loads(r.read().decode("utf-8"))
        assert data_health.get("status") == "ok"
    print("  PASS | /health responde 200 OK.")

    try:
        urllib.request.urlopen(f"{base_url}/handoffs", timeout=45)
        raise AssertionError("Error: /handoffs sin autenticación debió responder 401.")
    except urllib.error.HTTPError as e:
        assert e.code == 401, f"Se esperaba 401, recibido {e.code}"
        print("  PASS | /handoffs sin credenciales rechazado con HTTP 401 Unauthorized.")

    # 2. Renderizado del Panel y Token CSRF
    print("\n[3/6] Renderizando consola de asesores y extrayendo token CSRF...")
    req_panel = urllib.request.Request(f"{base_url}/handoffs", headers=auth_headers)
    with urllib.request.urlopen(req_panel, timeout=45) as r:
        assert r.status == 200
        html = r.read().decode("utf-8")
        assert "Consola de Asesores" in html or "Solicitudes para asesores" in html
        csrf_match = re.search(r"X-Handoff-CSRF':\s*'([^']+)'", html)
        assert csrf_match, "No se encontró el token anti-CSRF en el HTML de la consola"
        csrf_token = csrf_match.group(1)
        print(f"  PASS | Consola cargada (200 OK), CSRF={csrf_token[:8]}...")

    headers_with_csrf = dict(auth_headers)
    headers_with_csrf["X-Handoff-CSRF"] = csrf_token

    # 3. Generación de Ticket vía /test-chat
    print("\n[4/6] Generando ticket de prueba para derivación humana vía /test-chat...")
    test_user_id = f"eval_pr4_{os.urandom(4).hex()}"
    chat_payload = json.dumps({
        "user_id": test_user_id,
        "message": "Quiero hablar con un asesor"
    }).encode("utf-8")
    req_chat = urllib.request.Request(f"{base_url}/test-chat", data=chat_payload, headers=auth_headers)
    with urllib.request.urlopen(req_chat, timeout=45) as r:
        assert r.status == 200
        chat_data = json.loads(r.read().decode("utf-8"))
        ticket_id = chat_data.get("handoff_id")
        assert ticket_id, "No se recibió handoff_id en la respuesta"
        assert chat_data.get("escalated_to_human") is True
        print(f"  PASS | Ticket generado: #{ticket_id}")

    endpoint_ticket = f"{base_url}/handoffs/{ticket_id}"

    # 4. Validaciones de Seguridad y Manejo de Errores (PR #4)
    print("\n[5/6] Evaluando correcciones de PR #4 (CSRF, transición, tipos y canales)...")

    # A. Petición sin header CSRF -> 403
    close_body = json.dumps({
        "status": "closed",
        "advisor": "Auditor CloudRun",
        "note": "Nota sintética",
        "send_to_customer": False
    }).encode("utf-8")
    req_no_csrf = urllib.request.Request(endpoint_ticket, data=close_body, headers=auth_headers)
    try:
        urllib.request.urlopen(req_no_csrf, timeout=45)
        raise AssertionError("Se esperaba 403 Forbidden para petición sin header CSRF.")
    except urllib.error.HTTPError as e:
        assert e.code == 403
        print("  PASS | Intento de actualización sin header CSRF rechazado con HTTP 403.")

    # B. Intento de cierre de ticket 'pending' sin pasar por 'in_progress' -> 400
    req_invalid_trans = urllib.request.Request(endpoint_ticket, data=close_body, headers=headers_with_csrf)
    try:
        urllib.request.urlopen(req_invalid_trans, timeout=45)
        raise AssertionError("Se esperaba 400 Bad Request para cierre directo de ticket pending.")
    except urllib.error.HTTPError as e:
        assert e.code == 400
        err_msg = json.loads(e.read().decode("utf-8")).get("error", "")
        assert "Primero toma la solicitud en atención" in err_msg
        print(f"  PASS | Transición inválida (pending -> closed directo) rechazada con HTTP 400: '{err_msg}'.")

    # C. Toma formal del ticket (pending -> in_progress) -> 200
    take_body = json.dumps({
        "status": "in_progress",
        "advisor": "Auditor CloudRun",
        "note": "Tomando caso para auditoría"
    }).encode("utf-8")
    req_take = urllib.request.Request(endpoint_ticket, data=take_body, headers=headers_with_csrf)
    with urllib.request.urlopen(req_take, timeout=45) as r:
        assert r.status == 200
        take_res = json.loads(r.read().decode("utf-8"))
        assert take_res.get("ok") is True
        print("  PASS | Ticket tomado en atención (in_progress) exitosamente (HTTP 200).")

    # D. Validación estricta de booleano: send_to_customer='false' (string) -> 400
    invalid_bool_body = json.dumps({
        "status": "in_progress",
        "advisor": "Auditor CloudRun",
        "note": "Nota",
        "send_to_customer": "false"
    }).encode("utf-8")
    req_bad_bool = urllib.request.Request(endpoint_ticket, data=invalid_bool_body, headers=headers_with_csrf)
    try:
        urllib.request.urlopen(req_bad_bool, timeout=45)
        raise AssertionError("Se esperaba 400 Bad Request para booleano como string.")
    except urllib.error.HTTPError as e:
        assert e.code == 400
        err_bool = json.loads(e.read().decode("utf-8")).get("error", "")
        assert "La opción de envío debe ser verdadera o falsa" in err_bool
        print(f"  PASS | Booleano estricto validado: '{err_bool}' (HTTP 400).")

    # 5. Cierre con Nota Interna e Idempotencia
    print("\n[6/6] Cerrando ticket con nota interna y verificando idempotencia...")
    valid_close_body = json.dumps({
        "status": "closed",
        "advisor": "Auditor CloudRun",
        "note": "Atención concluida en auditoría en vivo.",
        "send_to_customer": False
    }).encode("utf-8")
    req_close = urllib.request.Request(endpoint_ticket, data=valid_close_body, headers=headers_with_csrf)
    with urllib.request.urlopen(req_close, timeout=45) as r:
        assert r.status == 200
        close_res = json.loads(r.read().decode("utf-8"))
        assert close_res.get("ok") is True
        assert close_res.get("message_sent") is False
        print("  PASS | Ticket cerrado formalmente con nota interna (HTTP 200, message_sent=False).")

    # Segundo intento de cierre debe ser rechazado (400) porque ya está cerrado
    req_double_close = urllib.request.Request(endpoint_ticket, data=valid_close_body, headers=headers_with_csrf)
    try:
        urllib.request.urlopen(req_double_close, timeout=45)
        raise AssertionError("Se esperaba 400 Bad Request para segundo cierre.")
    except urllib.error.HTTPError as e:
        assert e.code == 400
        err_double = json.loads(e.read().decode("utf-8")).get("error", "")
        assert "La solicitud ya está cerrada" in err_double
        print(f"  PASS | Doble cierre bloqueado: '{err_double}' (HTTP 400).")

    # Consulta final en /handoffs/data
    req_data = urllib.request.Request(f"{base_url}/handoffs/data", headers=auth_headers)
    with urllib.request.urlopen(req_data, timeout=45) as r:
        assert r.status == 200
        data_list = json.loads(r.read().decode("utf-8"))
        closed_ticket = next((x for x in data_list if x.get("id") == ticket_id), None)
        assert closed_ticket is not None
        assert closed_ticket.get("status") == "closed"
        assert closed_ticket.get("advisor") == "Auditor CloudRun"
        print(f"  PASS | /handoffs/data confirma ticket #{ticket_id} en estado 'closed'.")

    print("\n=====================================================================")
    print("   ¡PR #4 VALIDADO AL 100% EN VIVO EN CLOUD RUN (00023-rp9)!")
    print("=====================================================================")

if __name__ == "__main__":
    run_test()
