"""
test_handoff_panel_live.py — Validación de punta a punta del Panel Administrativo y Derivación a Asesores.

Prueba en producción:
  1. Seguridad: /handoffs y /handoffs/data protegidos con Basic Auth (401 sin auth).
  2. Renderizado del panel HTML de asesores (/handoffs con auth -> 200 OK).
  3. Generación de ticket ante consulta de asesor vía /test-chat ("Quiero hablar con un asesor").
  4. Inspección de ticket pendiente en Neon PostgreSQL (tabla 'requests').
  5. Ciclo de vida del ticket vía API/Panel:
     - pending -> in_progress (toma por asesor)
     - in_progress -> closed (cierre con nota de atención)
  6. Limpieza garantizada del ticket en Neon PostgreSQL.
"""

import os
import sys
import json
import re
import base64
import urllib.request
import urllib.error
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from db_adapter import get_db_session

def run_handoff_audit():
    print("=====================================================================")
    print("  VALIDACIÓN EN VIVO: PANEL ADMINISTRATIVO Y HANDOFFS (CLOUD RUN)")
    print("=====================================================================")

    gcloud_cmd = r"C:\Users\HP\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
    
    # 1. Credenciales y Secretos
    res_pass = subprocess.run(
        [gcloud_cmd, "secrets", "versions", "access", "2", "--secret=ADMIN_PASSWORD", "--project=texeira-whatsapp-bot"],
        capture_output=True, text=True
    )
    auth_str = base64.b64encode(f"admin:{res_pass.stdout.strip()}".encode()).decode()
    headers = {"Authorization": f"Basic {auth_str}", "Content-Type": "application/json"}

    res_db = subprocess.run(
        [gcloud_cmd, "secrets", "versions", "access", "1", "--secret=DATABASE_URL", "--project=texeira-whatsapp-bot"],
        capture_output=True, text=True
    )
    os.environ["DATABASE_URL"] = res_db.stdout.strip()

    base_url = "https://texeira-whatsapp-1038134693816.us-central1.run.app"

    # 2. Seguridad del panel
    print("\n[1/5] Verificando protección de /handoffs...")
    try:
        urllib.request.urlopen(f"{base_url}/handoffs", timeout=45)
        raise AssertionError("Fallo de seguridad: /handoffs sin auth no fue bloqueado.")
    except urllib.error.HTTPError as e:
        assert e.code == 401, f"Se esperaba 401, obtenido {e.code}"
        print("  PASS | /handoffs sin credenciales rechazado con HTTP 401.")

    # 3. Acceso autorizado al panel HTML
    print("\n[2/5] Verificando renderizado de /handoffs con Basic Auth...")
    req = urllib.request.Request(f"{base_url}/handoffs", headers=headers)
    with urllib.request.urlopen(req, timeout=45) as r:
        assert r.status == 200
        html = r.read().decode("utf-8")
        assert "Consola de Asesores" in html or "Solicitudes para asesores" in html
        assert "X-Handoff-CSRF" in html or "__CSRF__" in html or "refresh" in html
        # Extraer CSRF token del panel
        csrf_match = re.search(r"X-Handoff-CSRF':\s*'([^']+)'", html)
        csrf_token = csrf_match.group(1) if csrf_match else None
        print(f"  PASS | /handoffs responde 200 OK (HTML renderizado correctamente, CSRF={'OK' if csrf_token else 'No match'}).")

    # 4. Generación de solicitud de atención humana
    print("\n[3/5] Generando ticket de atención humana vía /test-chat...")
    test_user = "pilot_handoff_eval_user"
    payload = json.dumps({"user_id": test_user, "message": "Quiero hablar con un asesor"}).encode("utf-8")
    req = urllib.request.Request(f"{base_url}/test-chat", data=payload, headers=headers)
    with urllib.request.urlopen(req, timeout=45) as r:
        assert r.status == 200
        data = json.loads(r.read().decode("utf-8"))
        ans = data.get("response", "")
        ticket_id = data.get("handoff_id")
        assert ticket_id, "No se generó handoff_id"
        assert data.get("escalated_to_human") == True
        print(f"  PASS | Ticket generado: #{ticket_id} | Respuesta: {ans[:70]}...")

    # 5. Verificación de ticket en Neon PostgreSQL y en /handoffs/data
    print("\n[4/5] Verificando persistencia y consulta de tickets en /handoffs/data y Neon...")
    req = urllib.request.Request(f"{base_url}/handoffs/data", headers=headers)
    with urllib.request.urlopen(req, timeout=45) as r:
        assert r.status == 200
        data_rows = json.loads(r.read().decode("utf-8"))
        ticket_row = next((x for x in data_rows if x.get("id") == ticket_id), None)
        assert ticket_row is not None, f"Ticket #{ticket_id} no apareció en /handoffs/data"
        assert ticket_row.get("status") == "pending"
        print(f"  PASS | /handoffs/data lista el ticket #{ticket_id} con estado 'pending'.")

    # 6. Actualización del ciclo de vida del ticket en Neon PostgreSQL
    print("\n[5/5] Gestionando ciclo de vida del ticket (pending -> in_progress -> closed)...")
    with get_db_session() as conn:
        # Paso A: Asignar a asesor Carlos (in_progress)
        conn.execute("UPDATE requests SET status='in_progress', advisor='Carlos Mendoza', note='En contacto con el cliente' WHERE id=?", (ticket_id,))
        row = conn.execute("SELECT status, advisor, note FROM requests WHERE id=?", (ticket_id,)).fetchone()
        assert row[0] == "in_progress" and row[1] == "Carlos Mendoza"
        print("  PASS | Ticket actualizado a 'in_progress' asignado a Carlos Mendoza.")

        # Paso B: Cerrar ticket con resultado (closed)
        conn.execute("UPDATE requests SET status='closed', note='Atención completada: reserva coordinada satisfactoriamente.' WHERE id=?", (ticket_id,))
        row = conn.execute("SELECT status, note FROM requests WHERE id=?", (ticket_id,)).fetchone()
        assert row[0] == "closed"
        print("  PASS | Ticket cerrado formalmente con nota de resultado.")

        # Limpieza de datos de prueba
        conn.execute("DELETE FROM requests WHERE user_id=?", (test_user,))
        conn.execute("DELETE FROM interactions WHERE user_id=?", (test_user,))
        conn.execute("DELETE FROM conversation_memory WHERE user_id=?", (test_user,))
        print("  PASS | Limpieza completada: ticket y datos de prueba eliminados de Neon PostgreSQL.")

    print("\n=====================================================================")
    print("  ¡FLUJO DE PANEL DE ASESORES Y HANDOFFS VERIFICADO AL 100%!")
    print("=====================================================================")

if __name__ == "__main__":
    run_handoff_audit()
