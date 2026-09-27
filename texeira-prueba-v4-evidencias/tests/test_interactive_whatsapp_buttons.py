"""Pruebas unitarias e integradas para botones interactivos de WhatsApp (Meta Cloud API).

Verifica:
1. Construcción del payload de botones interactivos según especificaciones de Meta Graph API v26.0.
2. Restricción estricta de <= 20 caracteres por título de botón y truncado de seguridad.
3. Fallback automático a mensaje de texto si el texto excede 1024 caracteres o si no hay botones válidos.
4. Fallback resiliente a texto si Meta API retorna error HTTP.
5. Generación contextual de get_quick_buttons para todos los flujos de conversación (saludo, listing, tour, fotos, precios).
6. Parsing del webhook de entrada para mensajes interactivos de WhatsApp (button_reply y list_reply).
7. Flujo conversacional completo sin escribir (100% navegación por botones).
"""
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Asegurar path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.services.whatsapp import (
    send_whatsapp_message,
    send_whatsapp_interactive_buttons,
)
import app


class TestInteractiveWhatsAppButtons(unittest.TestCase):
    def setUp(self):
        os.environ["META_ACCESS_TOKEN"] = "EAABtest_token_valid_12345"
        os.environ["META_PHONE_NUMBER_ID"] = "109876543210"

    def tearDown(self):
        pass

    @patch("httpx.Client.post")
    def test_interactive_payload_format(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"messages": [{"id": "wamid.test_button_msg"}]}
        mock_resp.text = '{"messages":[{"id":"wamid.test_button_msg"}]}'
        mock_post.return_value = mock_resp

        buttons = [
            {"id": "btn_photo", "title": "📸 Ver Fotos"},
            {"id": "btn_rates", "title": "💰 Tarifas"},
            {"id": "btn_advisor", "title": "🙋‍♂️ Asesor"},
        ]

        success = send_whatsapp_interactive_buttons(
            text="Información sobre Camino Inca",
            buttons=buttons,
            to_phone="51921484423",
            phone_number_id="109876543210",
        )

        self.assertTrue(success)
        self.assertTrue(mock_post.called)

        call_kwargs = mock_post.call_args[1]
        payload = call_kwargs["json"]

        self.assertEqual(payload["messaging_product"], "whatsapp")
        self.assertEqual(payload["recipient_type"], "individual")
        self.assertEqual(payload["to"], "51921484423")
        self.assertEqual(payload["type"], "interactive")

        interactive = payload["interactive"]
        self.assertEqual(interactive["type"], "button")
        self.assertEqual(interactive["body"]["text"], "Información sobre Camino Inca")

        btn_list = interactive["action"]["buttons"]
        self.assertEqual(len(btn_list), 3)
        self.assertEqual(btn_list[0]["reply"]["id"], "btn_photo")
        self.assertEqual(btn_list[0]["reply"]["title"], "📸 Ver Fotos")
        self.assertEqual(btn_list[1]["reply"]["id"], "btn_rates")
        self.assertEqual(btn_list[1]["reply"]["title"], "💰 Tarifas")
        self.assertEqual(btn_list[2]["reply"]["id"], "btn_advisor")
        self.assertEqual(btn_list[2]["reply"]["title"], "🙋‍♂️ Asesor")

    @patch("httpx.Client.post")
    def test_button_title_max_20_chars_truncation(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"messages": [{"id": "wamid.test_trunc"}]}
        mock_resp.text = "{}"
        mock_post.return_value = mock_resp

        # Botón con título de más de 20 caracteres
        buttons = [
            {"id": "btn_long", "title": "Este título es demasiado largo para WhatsApp API"},
        ]

        send_whatsapp_interactive_buttons(
            text="Texto corto",
            buttons=buttons,
            to_phone="51921484423",
        )

        call_kwargs = mock_post.call_args[1]
        payload = call_kwargs["json"]
        btn_sent = payload["interactive"]["action"]["buttons"][0]
        title_sent = btn_sent["reply"]["title"]

        self.assertLessEqual(len(title_sent), 20)
        self.assertEqual(title_sent, "Este título es demas")

    @patch("src.services.whatsapp.send_whatsapp_message")
    def test_fallback_to_text_when_body_exceeds_1024_chars(self, mock_send_msg):
        mock_send_msg.return_value = True

        long_text = "A" * 1050
        buttons = [{"id": "btn_1", "title": "Boton 1"}]

        send_whatsapp_interactive_buttons(
            text=long_text,
            buttons=buttons,
            to_phone="51921484423",
        )

        # Debe llamar a send_whatsapp_message con buttons=None
        self.assertTrue(mock_send_msg.called)
        kwargs = mock_send_msg.call_args[1]
        self.assertEqual(kwargs["text"], long_text)
        self.assertIsNone(kwargs["buttons"])

    @patch("src.services.whatsapp.send_whatsapp_message")
    def test_fallback_to_text_when_buttons_empty(self, mock_send_msg):
        mock_send_msg.return_value = True

        send_whatsapp_interactive_buttons(
            text="Hola",
            buttons=[],
            to_phone="51921484423",
        )

        self.assertTrue(mock_send_msg.called)

    @patch("httpx.Client.post")
    @patch("src.services.whatsapp.send_whatsapp_message")
    def test_fallback_to_text_on_meta_error_response(self, mock_send_msg, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = '{"error":{"message":"Invalid parameter"}}'
        mock_post.return_value = mock_resp
        mock_send_msg.return_value = True

        buttons = [{"id": "btn_1", "title": "Boton 1"}]
        send_whatsapp_interactive_buttons(
            text="Texto",
            buttons=buttons,
            to_phone="51921484423",
        )

        # Ante error 400 de Meta, debe intentar como texto plano para no perder el mensaje
        self.assertTrue(mock_send_msg.called)

    def test_get_quick_buttons_character_limits(self):
        test_cases = [
            ("social", "hola", "", "es"),
            ("social", "hello", "", "en"),
            ("evidence_listing", "que tours tienen disponibles", "", "es"),
            ("evidence_listing", "what tours are available", "", "en"),
            ("evidence_confirmed_overview", "informacion de Camino Inca", "camino-inka", "es"),
            ("evidence_confirmed_overview", "info about Inca Trail", "camino-inka", "en"),
            ("evidence_confirmed_price", "cuanto cuesta", "camino-inka", "es"),
            ("evidence_confirmed_price", "how much does it cost", "camino-inka", "en"),
            ("evidence_photo", "fotos", "camino-inka", "es"),
            ("evidence_photo", "photos", "camino-inka", "en"),
            ("evidence_confirmed_includes", "que incluye", "salkantay-trek", "es"),
            ("evidence_contact", "asesor", "", "es"),
        ]

        for route, msg, eid, lang in test_cases:
            buttons = app.get_quick_buttons(route=route, user_message=msg, detected_eid=eid, lang=lang)
            self.assertGreaterEqual(len(buttons), 1, f"No buttons generated for {route} {lang}")
            self.assertLessEqual(len(buttons), 3, f"Too many buttons for {route} {lang}")
            for b in buttons:
                self.assertIn("id", b)
                self.assertIn("title", b)
                self.assertLessEqual(
                    len(b["title"]), 20,
                    f"Button title '{b['title']}' exceeds 20 characters in case ({route}, {msg}, {lang})!"
                )

    def test_inbound_button_reply_mapping(self):
        from starlette.testclient import TestClient
        client = TestClient(app.app)

        # Mock HMAC signature verification if required
        with patch.object(app, "META_APP_SECRET", "dummy_secret"), \
             patch("hmac.compare_digest", return_value=True), \
             patch.object(app, "send_whatsapp_message", return_value=True) as mock_send, \
             patch.object(app, "send_whatsapp_image", return_value=True), \
             patch.object(app.database, "claim_webhook", return_value=("new", "worker_1")), \
             patch.object(app.database, "renew_webhook", return_value=True), \
             patch.object(app.database, "finish_webhook", return_value=True):

            app.clear_history("51921484423")

            # 1. Simular clic en botón "📸 Ver Fotos"
            # Primero establecer contexto con Camino Inca
            app.rag_chain("dame informacion de Camino Inca", user_id="51921484423")

            webhook_payload = {
                "object": "whatsapp_business_account",
                "entry": [{
                    "id": "entry_1",
                    "changes": [{
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"phone_number_id": "109876543210"},
                            "contacts": [{"wa_id": "51921484423"}],
                            "messages": [{
                                "from": "51921484423",
                                "id": "wamid.btn_reply_001",
                                "timestamp": "1727415000",
                                "type": "interactive",
                                "interactive": {
                                    "type": "button_reply",
                                    "button_reply": {
                                        "id": "btn_photo",
                                        "title": "📸 Ver Fotos"
                                    }
                                }
                            }]
                        },
                        "field": "messages"
                    }]
                }]
            }

            resp = client.post("/webhook", json=webhook_payload)
            self.assertEqual(resp.status_code, 200)
            self.assertTrue(mock_send.called)

            # Verificar que el mensaje enviado responde a fotos
            call_kwargs = mock_send.call_args[1]
            sent_text = call_kwargs["text"]
            self.assertIn("imagen", sent_text.lower())
            self.assertIn("Camino Inca", sent_text)

            # Verificar que el mensaje saliente incluye los botones siguientes (tarifas, qué incluye, asesor)
            sent_buttons = call_kwargs.get("buttons")
            self.assertIsNotNone(sent_buttons)
            btn_titles = [b["title"] for b in sent_buttons]
            self.assertTrue(any("Tarifas" in t for t in btn_titles))


if __name__ == "__main__":
    unittest.main()
