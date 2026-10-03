"""Independent regressions for routing and ambiguous outgoing deliveries.

Synthetic signed input, temporary SQLite and mocked HTTP; no real messaging.
Run through tests/run_isolated.py.
"""
import hashlib
import hmac
import json
import os
import unittest
from unittest.mock import patch

if os.environ.get("TEXEIRA_ISOLATED_TEST") != "1":
    raise RuntimeError("Run via tests/run_isolated.py")

import httpx
import app
import test_webhook_recovery as recovery
from src.services import whatsapp


class IntegratedWebhookReview(recovery.RecoveryTests):
    def post_batch(self, messages, contacts):
        payload = {
            "object": "whatsapp_business_account",
            "entry": [{"changes": [{"field": "messages", "value": {
                "messaging_product": "whatsapp",
                "metadata": {"phone_number_id": "synthetic_graph_phone_id"},
                "messages": messages,
                "contacts": contacts,
            }}]}],
        }
        raw = json.dumps(payload).encode()
        signature = "sha256=" + hmac.new(b"synthetic", raw, hashlib.sha256).hexdigest()
        # Use request(), keeping the mocked Client.post limited to outbound calls.
        return self.client.request("POST", "/webhook", content=raw,
                                   headers={"X-Hub-Signature-256": signature})

    def test_uncertain_send_is_not_blindly_repeated_on_redelivery(self):
        incoming = [{"id": "wamid.review_uncertain", "from": "51900000001",
                     "type": "text", "timestamp": "1", "text": {"body": "Hola"}}]
        simulated_provider_acceptances = []

        def accept_then_lose_first_response(*args, **kwargs):
            # Simulate Meta accepting a request before its HTTP response is lost.
            simulated_provider_acceptances.append(kwargs["json"]["type"])
            if len(simulated_provider_acceptances) == 1:
                raise httpx.ReadTimeout("Synthetic response lost after acceptance")
            return httpx.Response(200, json={"messages": [{"id": "wamid.second_send"}]})

        with patch.dict(os.environ, {"META_ACCESS_TOKEN": "synthetic_token",
                                     "META_PHONE_NUMBER_ID": "synthetic_graph_phone_id"}), \
             patch.object(app, "rag_chain", return_value={
                 "response": "Hola", "response_route": "social", "is_fallback": False,
             }), \
             patch.object(app, "get_quick_buttons", return_value=[{
                 "id": "btn_tours", "title": "Ver tours",
             }]), \
             patch.object(app, "send_whatsapp_message", wraps=whatsapp.send_whatsapp_message), \
             patch("httpx.Client.post", side_effect=accept_then_lose_first_response):
            first = self.post_batch(incoming, [{"wa_id": "51900000001"}])
            redelivery = self.post_batch(incoming, [{"wa_id": "51900000001"}])
        print("UNCERTAIN DELIVERY REVIEW:", first.status_code, redelivery.status_code,
              "simulated_acceptances=", len(simulated_provider_acceptances))
        self.assertEqual(len(simulated_provider_acceptances), 1,
                         "An uncertain delivery was sent again on incoming redelivery")

    def test_batch_contacts_are_matched_to_each_message_sender(self):
        messages = [
            {"id": "wamid.review_customer_a", "from": "51900000001", "type": "text",
             "timestamp": "1", "text": {"body": "Hola A"}},
            {"id": "wamid.review_customer_b", "from": "51900000002", "type": "text",
             "timestamp": "2", "text": {"body": "Hola B"}},
        ]
        contacts = [{"wa_id": "51900000001"}, {"wa_id": "51900000002"}]
        with patch.object(app, "rag_chain", return_value={
            "response": "Hola", "response_route": "social", "is_fallback": False,
        }) as rag, patch.object(app, "send_whatsapp_message", return_value=True) as send:
            result = self.post_batch(messages, contacts)
        destinations = [call.kwargs.get("to_phone") for call in send.call_args_list]
        memory_users = [call.kwargs.get("user_id") for call in rag.call_args_list]
        print("CONTACT ROUTING REVIEW:", result.status_code,
              "destinations=", destinations, "memory_users=", memory_users)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(destinations, ["51900000001", "51900000002"])
        self.assertEqual(memory_users, ["51900000001", "51900000002"])


if __name__ == "__main__":
    names = [
        "test_uncertain_send_is_not_blindly_repeated_on_redelivery",
        "test_batch_contacts_are_matched_to_each_message_sender",
    ]
    outcome = unittest.TextTestRunner(verbosity=2).run(
        unittest.TestSuite(IntegratedWebhookReview(name) for name in names)
    )
    raise SystemExit(0 if outcome.wasSuccessful() else 1)
