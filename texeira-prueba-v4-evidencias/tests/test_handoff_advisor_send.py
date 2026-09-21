"""
test_handoff_advisor_send.py — Prueba unitaria del envío directo a WhatsApp desde el panel de asesores.
"""

import sys
import os
import re
import tempfile
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import httpx
import app
import handoff_support as h

async def run_test():
    print("=====================================================================")
    print("   PRUEBA: ENVÍO DIRECTO A WHATSAPP DESDE EL PANEL DE ASESORES")
    print("=====================================================================")

    with tempfile.TemporaryDirectory() as folder:
        h.DB = Path(folder) / "requests.db"
        
        # Crear un ticket para usuario de WhatsApp
        ticket_data, created = h.create_request("51921484423", "whatsapp", "Consulta sobre precio grupal", [])
        ticket_id = ticket_data["id"]
        assert created

        mock_send = MagicMock(return_value=True)

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app.app), base_url="http://test") as c:
            page = (await c.get("/handoffs")).text
            csrf = re.search(r"'X-Handoff-CSRF':'([^']+)'", page).group(1)
            headers = {"X-Handoff-CSRF": csrf}

            # 1. Tomar solicitud
            r1 = await c.post(f"/handoffs/{ticket_id}", headers=headers, json={
                "status": "in_progress",
                "advisor": "Eugenio",
                "note": ""
            })
            assert r1.status_code == 200

            # 2. Caso A: Cerrar SIN enviar a cliente (send_to_customer=False)
            with patch("src.services.whatsapp.send_whatsapp_message", mock_send):
                r2 = await c.post(f"/handoffs/{ticket_id}", headers=headers, json={
                    "status": "closed",
                    "advisor": "Eugenio",
                    "note": "Nota interna: coordinado en persona",
                    "send_to_customer": False
                })
                assert r2.status_code == 200
                data2 = r2.json()
                assert data2.get("ok") == True
                assert data2.get("message_sent") == False
                mock_send.assert_not_called()
                print("  PASS | send_to_customer=False: Guarda la nota interna sin llamar a WhatsApp.")

        # Crear otro ticket para probar envío con send_to_customer=True
        ticket_data2, _ = h.create_request("51921484423", "whatsapp", "Consulta 2", [])
        ticket_id2 = ticket_data2["id"]

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app.app), base_url="http://test") as c:
            headers = {"X-Handoff-CSRF": csrf}
            # Tomar solicitud
            await c.post(f"/handoffs/{ticket_id2}", headers=headers, json={"status": "in_progress", "advisor": "Eugenio"})

            # Caso B: Cerrar CON envío a cliente (send_to_customer=True)
            with patch("src.services.whatsapp.send_whatsapp_message", mock_send):
                r3 = await c.post(f"/handoffs/{ticket_id2}", headers=headers, json={
                    "status": "closed",
                    "advisor": "Eugenio",
                    "note": "Hola! Para 10 personas tenemos tarifa especial de $65 USD en servicio privado.",
                    "send_to_customer": True
                })
                assert r3.status_code == 200
                data3 = r3.json()
                assert data3.get("ok") == True
                assert data3.get("message_sent") == True
                mock_send.assert_called_once()
                args, kwargs = mock_send.call_args
                assert "Eugenio" in kwargs["text"]
                assert "$65 USD" in kwargs["text"]
                assert kwargs["to_phone"] == "51921484423"
                print("  PASS | send_to_customer=True: Despacha el mensaje al WhatsApp del cliente con formato profesional.")

    print("=====================================================================")
    print("  ¡TODAS LAS PRUEBAS DE ENVÍO DIRECTO A WHATSAPP APROBADAS!")
    print("=====================================================================")

if __name__ == "__main__":
    asyncio.run(run_test())
