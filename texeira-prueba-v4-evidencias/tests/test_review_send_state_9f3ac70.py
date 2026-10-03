"""Fault injection after dispatch, plus existing webhook and fallback contracts.

Run with tests/run_isolated.py; no real provider or customer data.
"""
import hashlib
import hmac
import json
import os
import unittest
from unittest.mock import patch

if os.environ.get("TEXEIRA_ISOLATED_TEST") != "1":
    raise RuntimeError("Run via tests/run_isolated.py")

import app
import database
import operational_metrics
from src.services.whatsapp import WhatsAppSendResult, is_interactive_format_error
from test_review_webhook_2a6d01d import IntegratedWebhookReview


class SendStateReview(IntegratedWebhookReview):
    def check_metrics_failure_preserves_send_state(self, send_status):
        incoming_id = "wamid.metrics_failure_" + send_status
        incoming = [{"id": incoming_id, "from": "51900000001", "type": "text",
                     "timestamp": "1", "text": {"body": "Hola"}}]
        contacts = [{"wa_id": "51900000001"}]
        original_finish = operational_metrics.finish
        finish_calls = []

        def fail_first_metrics_write(*args, **kwargs):
            finish_calls.append(args[1])
            if len(finish_calls) == 1:
                raise RuntimeError("Synthetic metrics failure after dispatch")
            return original_finish(*args, **kwargs)

        result = WhatsAppSendResult(send_status, accepted=send_status == "accepted")
        with patch.object(app, "rag_chain", return_value={
            "response": "Hola", "response_route": "social", "is_fallback": False,
        }), patch.object(app, "send_whatsapp_message", return_value=result) as send, \
             patch.object(operational_metrics, "finish", side_effect=fail_first_metrics_write):
            first = self.post_batch(incoming, contacts)
            with database.get_db_session(self.db) as conn:
                receipt = conn.execute("SELECT status FROM webhook_receipts WHERE message_id=?",
                                       (incoming_id,)).fetchone()
                saved_status = receipt["status"]
            redelivery = self.post_batch(incoming, contacts)
        print("POST-SEND METRICS REVIEW:", send_status, "first=", first.status_code,
              "redelivery=", redelivery.status_code, "saved_status=", saved_status,
              "send_calls=", send.call_count)
        self.assertEqual(send.call_count, 1,
                         "A metrics failure must not make a dispatched message send again")
        self.assertEqual(saved_status, "completed" if send_status == "accepted" else "uncertain")

    def test_metrics_failure_after_accepted_send_does_not_repeat_delivery(self):
        self.check_metrics_failure_preserves_send_state("accepted")

    def test_metrics_failure_after_uncertain_send_does_not_repeat_delivery(self):
        self.check_metrics_failure_preserves_send_state("uncertain")

    def test_existing_synthetic_webhook_channel_still_processes_without_delivery(self):
        raw = json.dumps({"user_id": "synthetic_web_user", "message": "Hola"}).encode()
        signature = "sha256=" + hmac.new(b"synthetic", raw, hashlib.sha256).hexdigest()
        with patch.object(app, "rag_chain", return_value={
            "response": "Hola", "response_route": "social", "is_fallback": False,
        }), patch.object(app, "send_whatsapp_message") as send:
            result = self.client.request("POST", "/webhook", content=raw,
                                         headers={"X-Hub-Signature-256": signature})
        print("SYNTHETIC CHANNEL REVIEW:", result.status_code, result.json())
        self.assertEqual(result.status_code, 200)
        send.assert_not_called()

    def test_invalid_recipient_is_not_an_interactive_format_error(self):
        error = json.dumps({"error": {"code": 100,
                            "message": "Parameter to is not a valid WhatsApp number"}})
        self.assertFalse(is_interactive_format_error(400, error),
                         "Switching to plain text cannot repair an invalid recipient")


    def test_synthetic_webhook_channel_failure_reports_error(self):
        raw = json.dumps({"user_id": "synthetic_failing_user", "message": "Hola"}).encode()
        signature = "sha256=" + hmac.new(b"synthetic", raw, hashlib.sha256).hexdigest()
        with patch.object(app, "rag_chain", side_effect=RuntimeError("Synthetic inference error")):
            result = self.client.request("POST", "/webhook", content=raw,
                                         headers={"X-Hub-Signature-256": signature})
        self.assertNotEqual(result.status_code, 200, "Synthetic failure must not report HTTP 200 success")
        self.assertIn(result.status_code, (500, 503))


if __name__ == "__main__":
    names = [
        "test_metrics_failure_after_accepted_send_does_not_repeat_delivery",
        "test_metrics_failure_after_uncertain_send_does_not_repeat_delivery",
        "test_existing_synthetic_webhook_channel_still_processes_without_delivery",
        "test_synthetic_webhook_channel_failure_reports_error",
        "test_invalid_recipient_is_not_an_interactive_format_error",
    ]
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.TestSuite(SendStateReview(name) for name in names)
    )
    raise SystemExit(0 if result.wasSuccessful() else 1)
