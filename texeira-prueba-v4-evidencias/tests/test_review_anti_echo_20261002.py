"""Protocol review: legitimate messages survive batching; status is not input.

Run only via tests/run_isolated.py. Signed synthetic events; no real messaging.
"""
import hashlib
import hmac
import json
import os
import unittest
from unittest.mock import patch

if os.environ.get("TEXEIRA_ISOLATED_TEST") != "1":
    raise RuntimeError("Run with tests/run_isolated.py")

import app
import test_webhook_recovery as recovery


class EventFilterReview(recovery.RecoveryTests):
    def post_events(self, messages=None, statuses=None):
        value = {
            "messaging_product": "whatsapp",
            "metadata": {"phone_number_id": "synthetic_graph_phone_id"},
            "contacts": [{"wa_id": "51900000000"}],
        }
        if messages is not None:
            value["messages"] = messages
        if statuses is not None:
            value["statuses"] = statuses
        payload = {"object": "whatsapp_business_account", "entry": [{"changes": [
            {"field": "messages", "value": value}
        ]}]}
        raw = json.dumps(payload).encode()
        signature = "sha256=" + hmac.new(b"synthetic", raw, hashlib.sha256).hexdigest()
        return self.client.post("/webhook", content=raw,
                                headers={"X-Hub-Signature-256": signature})

    def test_status_notifications_do_not_generate_bot_replies(self):
        with patch.object(app, "rag_chain") as rag, \
             patch.object(app, "send_whatsapp_message") as send:
            result = self.post_events(statuses=[{
                "id": "wamid.synthetic_outbound", "status": "sent",
                "timestamp": "1", "recipient_id": "51900000000",
            }])
            self.assertEqual(result.status_code, 200)
            rag.assert_not_called()
            send.assert_not_called()

    def test_system_event_does_not_drop_valid_message_in_same_batch(self):
        system = {"id": "wamid.synthetic_system", "from": "51900000000",
                  "timestamp": "1", "type": "system",
                  "system": {"type": "customer_changed_number", "body": "number changed"}}
        user = {"id": "wamid.synthetic_text", "from": "51900000000",
                "timestamp": "2", "type": "text", "text": {"body": "Hola"}}
        with patch.object(app, "rag_chain", return_value={
            "response": "Hola", "is_fallback": False, "response_route": "social",
        }) as rag, patch.object(app, "send_whatsapp_message", return_value=True) as send:
            result = self.post_events(messages=[system, user])
            print("REVIEW BATCH RESULT:", result.status_code, result.json(),
                  "rag_calls=", rag.call_count, "send_calls=", send.call_count)
            self.assertEqual(result.status_code, 200)
            rag.assert_called_once_with("Hola", user_id="51900000000")
            send.assert_called_once()


    def test_multiple_text_messages_in_same_batch_processed(self):
        user1 = {"id": "wamid.batch_msg_1", "from": "51900000000",
                 "timestamp": "1", "type": "text", "text": {"body": "Hola"}}
        user2 = {"id": "wamid.batch_msg_2", "from": "51900000000",
                 "timestamp": "2", "type": "text", "text": {"body": "¿Qué tours tienen?"}}
        with patch.object(app, "rag_chain", return_value={
            "response": "Respuesta", "is_fallback": False, "response_route": "social",
        }) as rag, patch.object(app, "send_whatsapp_message", return_value=True) as send:
            result = self.post_events(messages=[user1, user2])
            self.assertEqual(result.status_code, 200)
            self.assertEqual(rag.call_count, 2)
            self.assertEqual(send.call_count, 2)

    def test_redelivery_of_same_id_is_deduplicated(self):
        user = {"id": "wamid.synthetic_dedup_id", "from": "51900000000",
                "timestamp": "1", "type": "text", "text": {"body": "Hola"}}
        with patch.object(app, "rag_chain", return_value={
            "response": "Hola", "is_fallback": False, "response_route": "social",
        }) as rag, patch.object(app, "send_whatsapp_message", return_value=True) as send:
            # Primer envío: se procesa
            r1 = self.post_events(messages=[user])
            self.assertEqual(r1.status_code, 200)
            self.assertEqual(rag.call_count, 1)
            self.assertEqual(send.call_count, 1)

            # Reentrega del mismo ID: se deduplica
            r2 = self.post_events(messages=[user])
            self.assertEqual(r2.status_code, 200)
            self.assertTrue(r2.json().get("dedup"))
            self.assertEqual(rag.call_count, 1)
            self.assertEqual(send.call_count, 1)

    @patch("httpx.Client.post")
    @patch("src.services.whatsapp.send_whatsapp_message")
    def test_interactive_accepted_does_not_trigger_fallback(self, mock_send, mock_post):
        from src.services.whatsapp import send_whatsapp_interactive_buttons
        mock_resp = unittest.mock.MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"messages":[{"id":"wamid.test_interactive"}]}'
        mock_resp.json.return_value = {"messages": [{"id": "wamid.test_interactive"}]}
        mock_post.return_value = mock_resp

        with patch.dict(os.environ, {"META_ACCESS_TOKEN": "synthetic_token", "META_PHONE_NUMBER_ID": "synthetic_graph_phone_id"}):
            ok = send_whatsapp_interactive_buttons(
                text="Bienvenido",
                buttons=[{"id": "btn_tours", "title": "🗺️ Ver Tours"}],
                to_phone="51900000000",
                phone_number_id="synthetic_graph_phone_id",
            )
        self.assertTrue(ok)
        mock_post.assert_called_once()
        mock_send.assert_not_called()

    @patch("httpx.Client.post")
    @patch("src.services.whatsapp.send_whatsapp_message")
    def test_explicit_400_rejection_triggers_controlled_fallback(self, mock_send, mock_post):
        from src.services.whatsapp import send_whatsapp_interactive_buttons
        mock_resp = unittest.mock.MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = '{"error":{"message":"Button title too long"}}'
        mock_post.return_value = mock_resp
        mock_send.return_value = True

        with patch.dict(os.environ, {"META_ACCESS_TOKEN": "synthetic_token", "META_PHONE_NUMBER_ID": "synthetic_graph_phone_id"}):
            ok = send_whatsapp_interactive_buttons(
                text="Bienvenido",
                buttons=[{"id": "btn_tours", "title": "🗺️ Ver Tours"}],
                to_phone="51900000000",
                phone_number_id="synthetic_graph_phone_id",
            )
        self.assertTrue(ok)
        mock_post.assert_called_once()
        mock_send.assert_called_once()

    @patch("httpx.Client.post")
    @patch("src.services.whatsapp.send_whatsapp_message")
    def test_read_timeout_does_not_trigger_automatic_duplicate_fallback(self, mock_send, mock_post):
        import httpx
        from src.services.whatsapp import send_whatsapp_interactive_buttons
        mock_post.side_effect = httpx.ReadTimeout("Read timed out on socket")

        with patch.dict(os.environ, {"META_ACCESS_TOKEN": "synthetic_token", "META_PHONE_NUMBER_ID": "synthetic_graph_phone_id"}):
            ok = send_whatsapp_interactive_buttons(
                text="Bienvenido",
                buttons=[{"id": "btn_tours", "title": "🗺️ Ver Tours"}],
                to_phone="51900000000",
                phone_number_id="synthetic_graph_phone_id",
            )
        # Ante timeout incierto, debe retornar False SIN enviar texto plano de fallback a ciegas
        self.assertFalse(ok)
        mock_post.assert_called_once()
        mock_send.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
