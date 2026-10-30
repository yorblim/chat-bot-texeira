"""Pruebas integrales del ciclo completo de atención humana (pausa, chat, cierre y contexto).

Verifica con entradas firmadas sintéticas, SQLite temporal y transporte simulado:
  1. Solicitud al asesor ('pending'): el cliente aún puede consultar mientras nadie tome el caso.
  2. Toma por el asesor ('in_progress'): aviso opcional al cliente y pausa inmediata del bot IA.
  3. Conversación humano-cliente: mensajes entrantes del cliente (texto, botones y reentregas)
     se guardan sin disparar respuestas del bot ni contaminar métricas del RAG; el asesor puede
     enviar múltiples mensajes sin cerrar el ticket (/handoffs/{id}/message).
  4. Finalización ('closed'): envío de mensaje de agradecimiento/cierre en el idioma del cliente
     (ES/EN/PT) y reactivación inmediata del bot.
  5. Continuidad de contexto: al retomar, el bot recuerda lo hablado durante la pausa con el asesor.
  6. Red de seguridad: timeout de inactividad del asesor (HANDOFF_PAUSE_TIMEOUT_HOURS) y rollback
     atómico ante fallo del proveedor o falta de CSRF.
"""
import hashlib
import hmac
import json
import os
import re
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["TEXEIRA_ENABLE_WHATSAPP"] = "false"

import app
import conversation_memory
import database
import handoff_support as handoff
import operational_metrics
from fastapi.testclient import TestClient


class HandoffPauseAndCloseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.logs_db = str(base / "webhook.db")
        self.requests_db = base / "requests.db"
        self.metrics_db = base / "metrics.db"

        env_clean = dict(
            os.environ,
            DATABASE_URL="",
            ADMIN_USER="",
            ADMIN_PASSWORD="",
            K_SERVICE="",
            ALLOW_CLOUD_RUN="",
            HANDOFF_PAUSE_TIMEOUT_HOURS="24",
        )
        p_env = patch.object(os, "environ", env_clean)
        p_env.start()
        self.addCleanup(p_env.stop)

        database.init_db(self.logs_db)
        isolated_mem = conversation_memory.ConversationMemory(lambda: self.logs_db, 20)

        patches = [
            patch.object(app, "SQLITE_DB_PATH", self.logs_db),
            patch.object(app, "META_APP_SECRET", "synthetic_secret"),
            patch.object(app, "conversation_history", isolated_mem),
            patch.object(handoff, "DB", self.requests_db),
            patch.object(handoff, "is_postgres", return_value=False),
            patch.object(operational_metrics, "DB", self.metrics_db),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

        # Garantizar que los hooks apunten a las funciones actuales de app.
        handoff._HOOKS.update(
            add_to_history=app.add_to_history,
            get_history=app.get_history,
            detect_language=app.detect_language,
        )

        self.client = TestClient(app.app)
        self.addCleanup(self.client.close)

    def _csrf_headers(self):
        page = self.client.get("/handoffs").text
        match = re.search(r"'X-Handoff-CSRF':'([^']+)'", page)
        self.assertIsNotNone(match, "No se encontró el token CSRF en /handoffs")
        return {"X-Handoff-CSRF": match.group(1)}

    def _post_wa_text(self, mid: str, phone: str, text: str):
        payload = {
            "object": "whatsapp_business_account",
            "entry": [{
                "changes": [{
                    "field": "messages",
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {"phone_number_id": "synthetic_phone_id"},
                        "contacts": [{"wa_id": phone}],
                        "messages": [{
                            "id": mid,
                            "from": phone,
                            "type": "text",
                            "timestamp": "1700000000",
                            "text": {"body": text},
                        }],
                    },
                }]
            }],
        }
        raw = json.dumps(payload).encode("utf-8")
        sig = "sha256=" + hmac.new(b"synthetic_secret", raw, hashlib.sha256).hexdigest()
        return self.client.post("/webhook", content=raw, headers={"X-Hub-Signature-256": sig})

    def _post_wa_button(self, mid: str, phone: str, btn_id: str, title: str):
        payload = {
            "object": "whatsapp_business_account",
            "entry": [{
                "changes": [{
                    "field": "messages",
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {"phone_number_id": "synthetic_phone_id"},
                        "contacts": [{"wa_id": phone}],
                        "messages": [{
                            "id": mid,
                            "from": phone,
                            "type": "interactive",
                            "timestamp": "1700000001",
                            "interactive": {
                                "type": "button_reply",
                                "button_reply": {"id": btn_id, "title": title},
                            },
                        }],
                    },
                }]
            }],
        }
        raw = json.dumps(payload).encode("utf-8")
        sig = "sha256=" + hmac.new(b"synthetic_secret", raw, hashlib.sha256).hexdigest()
        return self.client.post("/webhook", content=raw, headers={"X-Hub-Signature-256": sig})

    def test_full_lifecycle_pause_chat_thankyou_and_context_preservation(self):
        phone = "51911222333"
        outbound = []

        def fake_wa_send(*, text="", to_phone=None, recipient_bsuid=None, **kwargs):
            outbound.append({"text": text, "to_phone": to_phone, "buttons": kwargs.get("buttons")})
            return True

        with patch.object(app, "send_whatsapp_message", side_effect=fake_wa_send), \
             patch("src.services.whatsapp.send_whatsapp_message", side_effect=fake_wa_send), \
             patch.object(handoff, "notify_advisor", return_value=True):

            # 1. Cliente consulta Camino Inca y luego solicita hablar con un asesor
            r1 = self._post_wa_text("wamid.1", phone, "Hola, información de Camino Inca")
            self.assertEqual(r1.status_code, 200)
            self.assertEqual(len(outbound), 1)
            self.assertTrue(
                "Camino Inka" in outbound[-1]["text"] or "Camino Inca" in outbound[-1]["text"],
                outbound[-1]["text"],
            )

            r2 = self._post_wa_text("wamid.2", phone, "Quiero hablar con un asesor")
            self.assertEqual(r2.status_code, 200)
            self.assertEqual(len(outbound), 2)
            self.assertIn("pendiente de atención humana", outbound[-1]["text"])

            rows = self.client.get("/handoffs/data").json()
            self.assertEqual(len(rows), 1)
            ticket_id = rows[0]["id"]
            self.assertEqual(rows[0]["status"], "pending")
            self.assertFalse(rows[0]["bot_paused"])

            # 2. Mientras nadie toma el ticket ('pending'), el cliente aún puede consultar
            r_pending = self._post_wa_text("wamid.2b", phone, "¿Cuál es el precio de Camino Inca?")
            self.assertEqual(r_pending.status_code, 200)
            self.assertEqual(len(outbound), 3)

            # 3. El asesor Carlos toma la solicitud y avisa al cliente -> bot entra en PAUSA
            headers = self._csrf_headers()
            take_resp = self.client.post(
                f"/handoffs/{ticket_id}",
                headers=headers,
                json={"status": "in_progress", "advisor": "Carlos", "note": "", "notify_customer": True},
            )
            self.assertEqual(take_resp.status_code, 200)
            self.assertTrue(take_resp.json()["customer_notified"])
            self.assertEqual(len(outbound), 4)
            self.assertIn("Carlos", outbound[-1]["text"])

            rows_taken = self.client.get("/handoffs/data").json()
            self.assertEqual(rows_taken[0]["status"], "in_progress")
            self.assertTrue(rows_taken[0]["bot_paused"])

            # 4. Durante la pausa, el cliente cambia de opinión y habla con el asesor sobre Valle Sagrado.
            # El bot NO debe responder ni invocar rag_chain.
            outbound_before_pause_msgs = len(outbound)
            metrics_before = database.get_metrics_summary(self.logs_db)["total_interactions"]

            with patch.object(app, "rag_chain", side_effect=AssertionError("rag_chain NO debe ejecutarse en pausa")):
                r3 = self._post_wa_text(
                    "wamid.3",
                    phone,
                    "Hola Carlos, mejor queremos el tour Valle Sagrado para 3 adultos este sábado",
                )
                self.assertEqual(r3.status_code, 200)

                # Reentrega duplicada del mismo wamid no debe duplicar historial
                r3_dup = self._post_wa_text(
                    "wamid.3",
                    phone,
                    "Hola Carlos, mejor queremos el tour Valle Sagrado para 3 adultos este sábado",
                )
                self.assertEqual(r3_dup.status_code, 200)
                self.assertTrue(r3_dup.json().get("dedup"))

                # Clic en botón antiguo durante pausa tampoco dispara al bot
                r3_btn = self._post_wa_button("wamid.3btn", phone, "btn_rates", "💰 Precios")
                self.assertEqual(r3_btn.status_code, 200)

            self.assertEqual(len(outbound), outbound_before_pause_msgs, "El bot debió permanecer en silencio")
            self.assertEqual(
                database.get_metrics_summary(self.logs_db)["total_interactions"],
                metrics_before,
                "Los mensajes durante atención humana no deben contaminar las métricas del bot",
            )
            self.assertEqual(
                operational_metrics.summary()["processing"],
                0,
                "No deben quedar eventos operativos colgados en estado 'processing'",
            )

            # 5. El asesor envía respuesta al cliente SIN cerrar todavía la conversación
            msg_resp = self.client.post(
                f"/handoffs/{ticket_id}/message",
                headers=headers,
                json={
                    "advisor": "Carlos",
                    "text": "¡Claro! Para Valle Sagrado este sábado sí tenemos 3 cupos confirmados. ¿Te envío la cuenta BCP?",
                },
            )
            self.assertEqual(msg_resp.status_code, 200)
            self.assertTrue(msg_resp.json()["message_sent"])
            self.assertEqual(len(outbound), outbound_before_pause_msgs + 1)
            self.assertIn("*Carlos · Texeira Travel:*", outbound[-1]["text"])
            self.assertIn("Valle Sagrado", outbound[-1]["text"])

            # El cliente responde al asesor y el bot sigue esperando en silencio
            with patch.object(app, "rag_chain", side_effect=AssertionError("Bot sigue en pausa")):
                r4 = self._post_wa_text("wamid.4", phone, "Sí por favor, ya realicé la transferencia, todo listo")
                self.assertEqual(r4.status_code, 200)
            self.assertEqual(len(outbound), outbound_before_pause_msgs + 1)

            # El panel /handoffs/data refleja la conversación completa cliente <-> asesor
            live_conv = self.client.get("/handoffs/data").json()[0]["conversation"]
            authors = [m["author"] for m in live_conv]
            self.assertIn("cliente", authors)
            self.assertIn("asesor", authors)
            self.assertEqual(
                sum(1 for m in live_conv if "mejor queremos el tour Valle Sagrado" in m["content"]),
                1,
                "El mensaje del cliente durante la pausa debe registrarse exactamente una vez",
            )

            # 6. El asesor resuelve y finaliza la conversación enviando el agradecimiento
            close_resp = self.client.post(
                f"/handoffs/{ticket_id}",
                headers=headers,
                json={
                    "status": "closed",
                    "advisor": "Carlos",
                    "note": "Reserva de Valle Sagrado para 3 adultos coordinada y pagada.",
                    "send_to_customer": False,
                    "send_closing": True,
                },
            )
            self.assertEqual(close_resp.status_code, 200)
            close_json = close_resp.json()
            self.assertTrue(close_json["ok"])
            self.assertFalse(close_json["message_sent"])
            self.assertTrue(close_json["closing_sent"])
            self.assertEqual(len(outbound), outbound_before_pause_msgs + 2)
            self.assertIn("gracias por confiar en Texeira Travel", outbound[-1]["text"])
            self.assertIn("Carlos", outbound[-1]["text"])

            # 7. El bot vuelve a estar activo Y conserva el contexto de Valle Sagrado hablado con Carlos
            r5 = self._post_wa_text("wamid.5", phone, "¿Qué incluye ese tour?")
            self.assertEqual(r5.status_code, 200)
            self.assertEqual(len(outbound), outbound_before_pause_msgs + 3)
            resumed_reply = outbound[-1]["text"]
            self.assertIn("Valle Sagrado", resumed_reply)
            self.assertNotIn("Camino Inka", resumed_reply)
            self.assertNotIn("Camino Inca", resumed_reply)

    def test_direct_message_from_pending_takes_ticket_and_rollbacks_on_failure(self):
        phone = "51944555666"
        ticket, created = handoff.create_request(phone, "whatsapp", "asesor", [])
        self.assertTrue(created)
        tid = ticket["id"]
        headers = self._csrf_headers()

        # Sin CSRF -> 403
        self.assertEqual(
            self.client.post(f"/handoffs/{tid}/message", json={"advisor": "Ana", "text": "Hola"}).status_code,
            403,
        )

        # Si WhatsApp falla -> 502 y el ticket permanece 'pending' (rollback atómico)
        with patch("src.services.whatsapp.send_whatsapp_message", return_value=False):
            fail_resp = self.client.post(
                f"/handoffs/{tid}/message",
                headers=headers,
                json={"advisor": "Ana", "text": "Hola, te atiendo"},
            )
            self.assertEqual(fail_resp.status_code, 502)
        self.assertIsNone(handoff.active_pause(phone, "whatsapp"))

        # Si WhatsApp acepta -> pasa automáticamente a 'in_progress' y activa la pausa
        with patch("src.services.whatsapp.send_whatsapp_message", return_value=True):
            ok_resp = self.client.post(
                f"/handoffs/{tid}/message",
                headers=headers,
                json={"advisor": "Ana", "text": "Hola, ya reviso tu reserva"},
            )
            self.assertEqual(ok_resp.status_code, 200)
        paused = handoff.active_pause(phone, "whatsapp")
        self.assertIsNotNone(paused)
        self.assertEqual(paused["advisor"], "Ana")

    def test_closing_greeting_respects_english_and_portuguese_and_timeout_rescues(self):
        headers = self._csrf_headers()
        sent_messages = []

        def capture_send(*, text="", to_phone=None, **kwargs):
            sent_messages.append((to_phone, text))
            return True

        # Cliente angloparlante
        en_phone = "51977000111"
        app.add_to_history(en_phone, "human", "Hello, I want to speak to an advisor about Inca Trail")
        t_en, _ = handoff.create_request(en_phone, "whatsapp", "speak to an advisor", [])

        with patch("src.services.whatsapp.send_whatsapp_message", side_effect=capture_send):
            r_take = self.client.post(
                f"/handoffs/{t_en['id']}",
                headers=headers,
                json={"status": "in_progress", "advisor": "Elena", "note": "", "notify_customer": True},
            )
            self.assertEqual(r_take.status_code, 200)
            self.assertIn("I have your request", sent_messages[-1][1])

            r_close = self.client.post(
                f"/handoffs/{t_en['id']}",
                headers=headers,
                json={
                    "status": "closed",
                    "advisor": "Elena",
                    "note": "Resolved in English",
                    "send_to_customer": False,
                    "send_closing": True,
                },
            )
            self.assertEqual(r_close.status_code, 200)
            self.assertIn("Thank you very much for choosing Texeira Travel", sent_messages[-1][1])

        # Cliente lusófono + verificación de timeout de seguridad (24 h sin actividad del asesor)
        pt_phone = "51977000222"
        app.add_to_history(pt_phone, "human", "Olá, preciso falar com um assessor sobre o passeio")
        t_pt, _ = handoff.create_request(pt_phone, "whatsapp", "falar com um assessor", [])
        handoff.update_request(t_pt["id"], "in_progress", "João", "")

        self.assertIsNotNone(handoff.active_pause(pt_phone, "whatsapp"))
        future = datetime.now(timezone.utc) + timedelta(hours=25)
        self.assertIsNone(
            handoff.active_pause(pt_phone, "whatsapp", now=future),
            "Tras superar HANDOFF_PAUSE_TIMEOUT_HOURS sin actividad del asesor, el bot debe retomar",
        )

        with patch("src.services.whatsapp.send_whatsapp_message", side_effect=capture_send):
            handoff.update_request(
                t_pt["id"], "closed", "João", "Atendimento concluído", send_to_customer=False, send_closing=True
            )
        self.assertIn("Muito obrigado por confiar na Texeira Travel", sent_messages[-1][1])

    def test_customer_can_finish_in_progress_conversation_via_button_and_casual_thanks_does_not_close(self):
        phone = "51988111222"
        outbound = []

        def fake_wa_send(*, text="", to_phone=None, recipient_bsuid=None, **kwargs):
            outbound.append({"text": text, "to_phone": to_phone, "buttons": kwargs.get("buttons")})
            return True

        with patch.object(app, "send_whatsapp_message", side_effect=fake_wa_send), \
             patch("src.services.whatsapp.send_whatsapp_message", side_effect=fake_wa_send), \
             patch.object(handoff, "notify_advisor", return_value=True):

            # 1. Cliente pide asesor -> el mensaje inicial ya ofrece el botón '✅ Finalizar atención'
            r1 = self._post_wa_text("wamid.c1", phone, "Quiero hablar con un asesor")
            self.assertEqual(r1.status_code, 200)
            init_btns = outbound[-1]["buttons"] or []
            self.assertTrue(any(b["id"] == "btn_end_handoff:es" for b in init_btns), init_btns)

            ticket_id = self.client.get("/handoffs/data").json()[0]["id"]
            headers = self._csrf_headers()

            # 2. La asesora Lucía toma el caso y escribe al cliente -> incluye botón '✅ Finalizar atención'
            msg_resp = self.client.post(
                f"/handoffs/{ticket_id}/message",
                headers=headers,
                json={"advisor": "Lucía", "text": "Hola, dime para qué tour deseas disponibilidad."},
            )
            self.assertEqual(msg_resp.status_code, 200)
            advisor_btns = outbound[-1]["buttons"] or []
            end_btn = next((b for b in advisor_btns if b["id"].startswith("btn_end_handoff:")), None)
            self.assertIsNotNone(end_btn, "El mensaje del asesor debe incluir botón de finalizar atención")
            self.assertLessEqual(len(end_btn["title"]), 20)

            # 3. Un simple "gracias" a mitad de conversación NUNCA debe cerrar la atención del asesor
            count_before = len(outbound)
            r_thanks = self._post_wa_text(
                "wamid.c2",
                phone,
                "Muchas gracias Lucía, queremos reservar Laguna Humantay para 2 personas mañana",
            )
            self.assertEqual(r_thanks.status_code, 200)
            self.assertEqual(len(outbound), count_before, "Un 'gracias' casual no debe despertar al bot ni cerrar el ticket")
            self.assertIsNotNone(handoff.active_pause(phone, "whatsapp"))

            # 4. Una vez resuelta su duda, el cliente pulsa el botón '✅ Finalizar atención' emitido
            r_end = self._post_wa_button("wamid.c3", phone, end_btn["id"], end_btn["title"])
            self.assertEqual(r_end.status_code, 200)
            self.assertEqual(len(outbound), count_before + 1)
            self.assertIn("Lucía", outbound[-1]["text"])
            self.assertIn("gracias por confiar en Texeira Travel", outbound[-1]["text"])
            self.assertIsNone(handoff.active_pause(phone, "whatsapp"))

            # El panel refleja que el ticket quedó cerrado por el cliente conservando el nombre de Lucía
            closed_row = self.client.get("/handoffs/data").json()[0]
            self.assertEqual(closed_row["status"], "closed")
            self.assertEqual(closed_row["advisor"], "Lucía")
            self.assertIn("[Finalizado por el cliente]", closed_row["note"])

            # 5. La IA vuelve a responder de inmediato Y recuerda Laguna Humantay hablado con Lucía
            r_next = self._post_wa_text("wamid.c4", phone, "¿Qué incluye ese tour?")
            self.assertEqual(r_next.status_code, 200)
            self.assertIn("Humantay", outbound[-1]["text"])

            # 6. Si el cliente vuelve a tocar un botón antiguo '✅ Finalizar atención', responde con cortesía
            r_end_again = self._post_wa_button("wamid.c5", phone, end_btn["id"], end_btn["title"])
            self.assertEqual(r_end_again.status_code, 200)
            self.assertIn("ya se encuentra finalizada", outbound[-1]["text"])

    def test_customer_text_closure_guards_and_pending_cancellation(self):
        # Frases casuales, preguntas de tours o negaciones NO deben disparar cierre
        for safe_phrase in (
            "gracias",
            "muchas gracias Carlos",
            "ok perfecto, gracias!",
            "¿a qué hora termina el tour?",
            "¿dónde finaliza el recorrido?",
            "no quiero finalizar la conversación",
            "todavía no cierres la consulta",
            "don't end conversation",
            "não encerrar conversa",
        ):
            with self.subTest(safe_phrase=safe_phrase):
                self.assertFalse(handoff.close_requested_by_customer(safe_phrase))

        # Frases explícitas de cierre en ES/EN/PT SÍ deben reconocerse y NO abrir nuevo handoff
        for close_phrase in (
            "finalizar conversación",
            "Quiero finalizar la atención",
            "volver al bot",
            "cancelar solicitud de reserva",
            "end conversation",
            "return to bot",
            "encerrar conversa",
            "voltar ao bot",
        ):
            with self.subTest(close_phrase=close_phrase):
                self.assertTrue(handoff.close_requested_by_customer(close_phrase))
                self.assertFalse(handoff.requested(close_phrase))

        # Cierre por texto desde /test-chat cuando la solicitud estaba 'pending'
        uid = "web_tourist_01"
        r_open = self.client.post("/test-chat", json={"user_id": uid, "message": "Quiero hablar con un asesor"})
        self.assertEqual(r_open.status_code, 200)
        tid = r_open.json()["handoff_id"]
        self.assertEqual(r_open.json()["handoff_status"], "pending")

        r_close = self.client.post("/test-chat", json={"user_id": uid, "message": "finalizar conversación"})
        self.assertEqual(r_close.status_code, 200)
        close_data = r_close.json()
        self.assertEqual(close_data["handoff_id"], tid)
        self.assertEqual(close_data["handoff_status"], "closed")
        self.assertEqual(close_data["route"], "human_request_closed")
        self.assertIn("fue finalizada", close_data["response"])


if __name__ == "__main__":
    unittest.main()
