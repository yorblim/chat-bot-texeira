"""Portuguese WhatsApp controls and callback routing, without external transport.

The generation stub observes callback semantics; it does not assess LLM quality.
Run through tests/run_isolated.py so all catalog and receipt state is temporary.
"""
import os
import sys
import unittest
from contextlib import ExitStack
from unittest.mock import Mock, patch

if os.environ.get("TEXEIRA_ISOLATED_TEST") != "1":
    raise RuntimeError("Run tests/run_isolated.py; temporary database required")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app
import catalog_service
from starlette.testclient import TestClient


class PortugueseButtons(unittest.TestCase):
    def setUp(self):
        app.database.init_db(app.SQLITE_DB_PATH)
        catalog_service.init_catalog_db()
        self.client = TestClient(app.app)
        self.uid = "51955559009"
        app.clear_history(self.uid)

    def tearDown(self):
        app.clear_history(self.uid)

    def payload(self, button_id, title=""):
        return {
            "object": "whatsapp_business_account",
            "entry": [{"changes": [{"value": {
                "metadata": {"phone_number_id": "109876543210"},
                "contacts": [{"wa_id": self.uid}],
                "messages": [{
                    "from": self.uid, "id": "wamid.pt." + button_id,
                    "type": "interactive", "interactive": {
                        "type": "button_reply",
                        "button_reply": {"id": button_id, "title": title},
                    },
                }],
            }}]}],
        }

    def mocked_webhook(self, button_id, title="", history=None, text=None, result_language=None):
        """Observe real parsing, routing and outgoing controls with fake generation."""
        with ExitStack() as stack:
            stack.enter_context(patch.object(app, "META_APP_SECRET", "dummy_secret"))
            stack.enter_context(patch("hmac.compare_digest", return_value=True))
            generated = stack.enter_context(patch.object(app, "rag_chain", return_value={
                "response": "Escolha um passeio ou consulte nosso assessor.",
                "route": "evidence_recommendation", "response_route": "evidence_recommendation",
                "resolved_autonomously": False, "is_predefined": True,
                "language": result_language,
            }))
            sent = stack.enter_context(patch.object(app, "send_whatsapp_message", return_value=True))
            logged = stack.enter_context(patch.object(app.database, "log_interaction"))
            stack.enter_context(patch.object(app.database, "claim_webhook", return_value=("new", "worker_pt")))
            stack.enter_context(patch.object(app.database, "renew_webhook", return_value=True))
            stack.enter_context(patch.object(app.database, "finish_webhook", return_value=True))
            if history is not None:
                stack.enter_context(patch.object(app, "get_history", return_value=history))
            payload = self.payload(button_id, title)
            if text is not None:
                message = payload["entry"][0]["changes"][0]["value"]["messages"][0]
                message.update(type="text", text={"body": text})
                message.pop("interactive")
            response = self.client.post("/webhook", json=payload)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(sent.called)
            return generated, sent, logged

    def test_recommendation_controls_have_portuguese_labels(self):
        buttons = app.get_quick_buttons(route="evidence_recommendation", lang="pt")
        self.assertEqual(buttons, [
            {"id": "btn_tours:pt", "title": "🗺️ Ver passeios"},
            {"id": "btn_advisor:pt", "title": "Consultar assessor"},
        ])

    def test_contextual_controls_preserve_ids_and_meta_limits(self):
        routes = (
            "social", "evidence_catalog_empty", "evidence_catalog_error",
            "evidence_category_empty", "evidence_inactive_tour", "evidence_ambiguous",
            "evidence_listing", "evidence_category_tours", "evidence_photo",
            "evidence_photo_unavailable", "evidence_confirmed_price",
            "evidence_confirmed_includes", "evidence_schedule",
            "evidence_confirmed_overview", "human_request",
        )
        spanish_labels = {"Ver otros tours", "Consultar asesor", "Reintentar", "⬅️ Categorías",
                          "🗺️ Ver Tours", "📄 Qué incluye", "📸 Reintentar foto", "💰 Tarifas",
                          "📸 Ver Fotos", "🙋‍♂️ Asesor", "🌄 Clásicos Cusco",
                          "🚌 Rutas Regionales", "➡️ Más tours"}
        for route in routes:
            with self.subTest(route=route):
                msg = "categoria treks pagina 0 de passeios" if route == "evidence_category_tours" else ""
                eid = "camino-inka,maras-moray" if route == "evidence_ambiguous" else "camino-inka"
                buttons = app.get_quick_buttons(route=route, user_message=msg, detected_eid=eid, lang="pt")
                self.assertGreater(len(buttons), 0)
                self.assertLessEqual(len(buttons), 3)
                for button in buttons:
                    self.assertTrue(button["id"].endswith(":pt"))
                    self.assertLessEqual(len(button["id"]), 256)
                    self.assertLessEqual(len(button["title"]), 20)
                    self.assertNotIn(button["title"], spanish_labels)

    def test_callback_language_and_entity_are_preserved(self):
        callbacks = {
            "btn_tours:pt": "ver categorias de passeios",
            "btn_cats:pt": "ver categorias de passeios",
            "btn_cat:treks:pt": "categoria treks de passeios",
            "btn_cat_page:cusco:2:pt": "categoria cusco pagina 2 de passeios",
            "btn_tour:camino-inka:pt": "informações sobre Camino Inca Clásico 4D/3N",
            "btn_rates:camino-inka:pt": "preços oficiais de Camino Inca Clásico 4D/3N",
            "btn_inc:camino-inka:pt": "o que está incluído em Camino Inca Clásico 4D/3N",
            "btn_photo:camino-inka:pt": "fotos do passeio Camino Inca Clásico 4D/3N",
            "btn_book:camino-inka:pt": "solicitar reserva do passeio Camino Inca Clásico 4D/3N",
            "btn_advisor:pt": "consultar assessor",
        }
        spanish_history = [{"role": "human", "content": "hola"}]
        for button_id, query in callbacks.items():
            with self.subTest(button_id=button_id):
                generated, sent, logged = self.mocked_webhook(button_id, history=spanish_history)
                self.assertEqual(generated.call_args.args[0], query)
                self.assertEqual(app.detect_language(query), "pt")
                self.assertEqual(logged.call_args.kwargs["detected_language"], "pt")
                self.assertTrue(all(b["id"].endswith(":pt") for b in sent.call_args.kwargs["buttons"]))

    def test_legacy_portuguese_title_preserves_language(self):
        generated, sent, logged = self.mocked_webhook("btn_tours", "🗺️ Ver passeios")
        self.assertEqual(generated.call_args.args[0], "ver categorias de passeios")
        self.assertEqual(logged.call_args.kwargs["detected_language"], "pt")
        self.assertTrue(all(b["id"].endswith(":pt") for b in sent.call_args.kwargs["buttons"]))

    def test_legacy_shared_title_uses_portuguese_history(self):
        history = [{"role": "human", "content": "Recomende um passeio de meio dia, não quero fazer caminhadas."}]
        generated, _, logged = self.mocked_webhook("btn_book", "Solicitar reserva", history)
        self.assertEqual(generated.call_args.args[0], "solicitar reserva do passeio")
        self.assertEqual(logged.call_args.kwargs["detected_language"], "pt")

    def test_shared_text_reply_uses_resolved_language_metadata(self):
        generated, sent, logged = self.mocked_webhook("text_language", text="4 dias", result_language="pt")
        self.assertEqual(generated.call_args.args[0], "4 dias")
        self.assertEqual(logged.call_args.kwargs["detected_language"], "pt")
        self.assertTrue(all(b["id"].endswith(":pt") for b in sent.call_args.kwargs["buttons"]))

    def test_synthetic_api_shared_reply_uses_resolved_language_metadata(self):
        with patch.object(app, "rag_chain", return_value={
            "response": "Quer ajustar suas preferências?", "language": "pt",
            "route": "evidence_recommendation", "response_route": "evidence_recommendation",
            "is_fallback": False, "is_predefined": True, "resolved_autonomously": False,
        }), patch.object(app.database, "log_interaction") as logged:
            response = self.client.post("/test-chat", json={"user_id": self.uid, "message": "4 dias"})
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(result["detected_language"], "pt")
        self.assertFalse(result["resolved_autonomously"])
        self.assertEqual(logged.call_args.kwargs["detected_language"], "pt")
        self.assertTrue(all(b["id"].endswith(":pt") for b in result["quick_buttons"]))

    def test_real_portuguese_catalog_and_category_callbacks(self):
        original_tours = catalog_service.get_all_tours(active_only=False)
        try:
            active = {"camino-inka", "inka-jungle", "maras-moray"}
            for tour in original_tours:
                ok, message = catalog_service.upsert_tour({"entity_id": tour["entity_id"], "name": tour["name"], "is_active": tour["entity_id"] in active})
                self.assertTrue(ok, message)
            with ExitStack() as stack:
                stack.enter_context(patch.object(app, "META_APP_SECRET", "dummy_secret"))
                stack.enter_context(patch("hmac.compare_digest", return_value=True))
                sent = stack.enter_context(patch.object(app, "send_whatsapp_message", return_value=True))
                logged = stack.enter_context(patch.object(app.database, "log_interaction"))
                retriever = stack.enter_context(patch.object(app, "get_retriever", side_effect=AssertionError("Catalog navigation needs no retrieval")))
                model = stack.enter_context(patch.object(app, "get_llm", side_effect=AssertionError("Catalog navigation needs no model")))
                stack.enter_context(patch.object(app.database, "claim_webhook", return_value=("new", "worker_pt")))
                stack.enter_context(patch.object(app.database, "renew_webhook", return_value=True))
                stack.enter_context(patch.object(app.database, "finish_webhook", return_value=True))
                response = self.client.post("/webhook", json=self.payload("btn_tours:pt"))
                self.assertEqual(response.status_code, 200)
                listing = sent.call_args.kwargs
                self.assertIn("Selecione uma categoria", listing["text"])
                self.assertTrue(all(b["id"].endswith(":pt") for b in listing["buttons"]))
                self.assertIn("btn_cat:cusco:pt", [b["id"] for b in listing["buttons"]])
                self.assertEqual(logged.call_args.kwargs["detected_language"], "pt")
                response = self.client.post("/webhook", json=self.payload("btn_cat:cusco:pt"))
                self.assertEqual(response.status_code, 200)
                category = sent.call_args.kwargs
                self.assertIn("Maras - Moray", category["text"])
                self.assertIn("disponíveis", category["text"])
                self.assertIn("Escreva", category["text"])
                self.assertNotIn("Escribe", category["text"])
                self.assertTrue(all(b["id"].endswith(":pt") for b in category["buttons"]))
                self.assertIn("btn_tour:maras-moray:pt", [b["id"] for b in category["buttons"]])
                self.assertEqual(logged.call_args.kwargs["detected_language"], "pt")
                retriever.assert_not_called()
                model.assert_not_called()
        finally:
            for tour in original_tours:
                ok, detail = catalog_service.upsert_tour({"entity_id": tour["entity_id"], "name": tour["name"], "is_active": tour["is_active"]})
                if not ok:
                    raise AssertionError("Temporary catalog restore failed: " + str(detail))

    def test_ambiguous_portuguese_callback_stays_pending_without_guessing(self):
        history = [
            {"role": "human", "content": "informações sobre Camino Inca"},
            {"role": "human", "content": "informações sobre Maras Moray"},
        ]
        generated, sent, logged = self.mocked_webhook("btn_inc:pt", "📄 O que inclui", history)
        self.assertFalse(generated.called)
        self.assertIn("Qual passeio você deseja consultar?", sent.call_args.kwargs["text"])
        self.assertFalse(logged.call_args.kwargs["resolved_autonomously"])
        self.assertEqual(logged.call_args.kwargs["detected_language"], "pt")
        ids = [b["id"] for b in sent.call_args.kwargs["buttons"]]
        self.assertEqual(ids, ["btn_tour:camino-inka:pt", "btn_tour:maras-moray:pt", "btn_advisor:pt"])

    def test_missing_retriever_fallback_is_portuguese_and_unresolved(self):
        with patch.object(app, "get_retriever", return_value=None), \
             patch.object(app, "get_llm", side_effect=AssertionError("No model call without documents")) as model:
            result = app.rag_chain("Como devo me preparar para Camino Inca?", self.uid)
        self.assertTrue(result["is_fallback"])
        self.assertFalse(result["resolved_autonomously"])
        self.assertIn("Não tenho essa informação exata documentada", result["response"])
        self.assertNotIn("No dispongo", result["response"])
        model.assert_not_called()

    def test_transport_failure_fallback_is_portuguese_and_unresolved(self):
        retriever = Mock()
        retriever.invoke.side_effect = RuntimeError("controlled retrieval failure")
        with patch.object(app, "get_retriever", return_value=retriever), \
             patch.object(app, "get_llm", side_effect=AssertionError("No model call on failed retrieval")) as model:
            result = app.rag_chain("Como devo me preparar para Camino Inca?", self.uid)
        self.assertTrue(result["is_fallback"])
        self.assertFalse(result["resolved_autonomously"])
        self.assertIn("Desculpe, ocorreu um erro técnico", result["response"])
        self.assertNotIn("Lo siento", result["response"])
        model.assert_not_called()

    def test_rate_limit_response_is_portuguese_and_not_rag_fallback(self):
        import httpx
        response = httpx.Response(429, request=httpx.Request("POST", "https://test.invalid"))
        retriever = Mock()
        retriever.invoke.side_effect = app.RateLimitError("controlled rate limit", response=response, body=None)
        with patch.object(app, "get_retriever", return_value=retriever), \
             patch.object(app, "get_llm", side_effect=AssertionError("No model call on failed retrieval")) as model:
            result = app.rag_chain("Como devo me preparar para Camino Inca?", self.uid)
        self.assertTrue(result["is_rate_limit"])
        self.assertFalse(result["is_fallback"])
        self.assertFalse(result["resolved_autonomously"])
        self.assertIn("Tente novamente em alguns segundos", result["response"])
        self.assertNotIn("intenta de nuevo", result["response"])
        model.assert_not_called()


if __name__ == "__main__":
    unittest.main()
