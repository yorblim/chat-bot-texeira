"""Finite FR/IT preference and button regressions in an isolated catalog.

Synthetic durations/schedules and three active IDs are authored here. Generation
and transport are blocked or observed with NONFACTUAL markers, never treated as
proof of real model fluency, agency facts or WhatsApp delivery.
"""
import os
import sys
import unittest
from contextlib import ExitStack
from unittest.mock import patch
from uuid import uuid4

if os.environ.get("TEXEIRA_ISOLATED_TEST") != "1":
    raise RuntimeError("Run tests/run_isolated.py")

import app
import catalog_service
import handoff_support
import verified_routes
from starlette.testclient import TestClient


FIXTURE = {
    "camino-inka": {"name": "Camino Inca Clásico 4D/3N", "duration": "4 días / 3 noches"},
    "inka-jungle": {"name": "Inka Jungle to Machu Picchu", "duration": "4 días"},
    "maras-moray": {"name": "Maras - Moray", "duration": "Medio día", "schedule": "08:40-14:00"},
}
QUERIES = {
    "fr": "Je cherche une excursion d'une demi-journée sans randonnée.",
    "it": "Consigliami un tour di mezza giornata senza escursioni a piedi.",
}


class FrenchItalianNavigation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.database.init_db(app.SQLITE_DB_PATH)
        catalog_service.init_catalog_db()
        cls.snapshot = catalog_service.get_all_tours(active_only=False, strict=True)
        for tour in cls.snapshot:
            payload = {"entity_id": tour["entity_id"], "name": tour["name"], "is_active": False}
            if tour["entity_id"] in FIXTURE:
                payload.update(FIXTURE[tour["entity_id"]], is_active=True)
            ok, detail = catalog_service.upsert_tour(payload)
            if not ok:
                raise RuntimeError(detail)

    @classmethod
    def tearDownClass(cls):
        for tour in cls.snapshot:
            ok, detail = catalog_service.upsert_tour(tour)
            if not ok:
                raise RuntimeError(detail)

    def setUp(self):
        self.uid = "synthetic-fr-it-" + uuid4().hex
        self.client = TestClient(app.app)
        app.clear_history(self.uid)
        self.addCleanup(app.clear_history, self.uid)

    def blocked_chain(self, question):
        with patch.object(app, "get_retriever", side_effect=AssertionError("Unexpected retrieval")), \
             patch.object(app, "get_llm", side_effect=AssertionError("Unexpected generation")):
            return app.rag_chain(question, self.uid)

    def assert_rec(self, lang):
        result = self.blocked_chain(QUERIES[lang])
        self.assertEqual(result["response_route"], "evidence_recommendation")
        self.assertEqual(result["language"], lang)
        self.assertEqual(result["recommended_tour_ids"], ["maras-moray"])
        self.assertIn("Maras - Moray", result["response"])
        self.assertIn("Demi-journée" if lang == "fr" else "Mezza giornata", result["response"])
        self.assertNotIn("Camino Inca", result["response"])
        self.assertNotIn("Inka Jungle", result["response"])
        self.assertNotIn("Escribe", result["response"])
        self.assertNotIn("Según", result["response"])
        self.assertNotRegex(result["response"].lower(), r"(?:aucune marche|zero passi|sans aucun effort)")
        self.assertTrue(result["resolved_autonomously"])
        return result

    def test_french_half_day_recommendation(self):
        self.assert_rec("fr")

    def test_italian_half_day_recommendation(self):
        self.assert_rec("it")

    def test_french_time_only_followup_retains_no_hiking(self):
        self.assert_rec("fr")
        result = self.blocked_chain("quatre jours")
        self.assertEqual(result["response_route"], "evidence_recommendation")
        self.assertEqual(result["language"], "fr")
        self.assertFalse(result["resolved_autonomously"])
        self.assertTrue(result["needs_confirmation"])
        self.assertIn("préférences", result["response"])

    def test_italian_time_only_followup_retains_no_hiking(self):
        self.assert_rec("it")
        result = self.blocked_chain("quattro giorni")
        self.assertEqual(result["response_route"], "evidence_recommendation")
        self.assertEqual(result["language"], "it")
        self.assertFalse(result["resolved_autonomously"])
        self.assertTrue(result["needs_confirmation"])
        self.assertIn("preferenze", result["response"])

    def test_french_missing_preferences(self):
        result = self.blocked_chain("Quels tours conseillez-vous ?")
        self.assertEqual(result["response_route"], "evidence_recommendation")
        self.assertFalse(result["resolved_autonomously"])
        self.assertIn("Combien de temps", result["response"])

    def test_italian_missing_preferences(self):
        result = self.blocked_chain("Consigliami un tour")
        self.assertEqual(result["response_route"], "evidence_recommendation")
        self.assertFalse(result["resolved_autonomously"])
        self.assertIn("Quanto tempo", result["response"])

    def test_existing_preference_parsers_remain_valid(self):
        for question, expected in (("medio día", ("half", None)), ("half day", ("half", None)),
                                   ("meio dia", ("half", None)), ("4 days", ("multi", 4)),
                                   ("quatro dias", ("multi", 4))):
            with self.subTest(question=question):
                self.assertEqual(verified_routes.duration_preference(question), expected)
        for question in ("no quiero caminatas", "I do not want hiking", "não quero fazer caminhadas"):
            with self.subTest(question=question):
                self.assertIs(verified_routes.hiking_preference(question), False)

    def payload(self, button_id, title):
        return {"object": "whatsapp_business_account", "entry": [{"changes": [{"value": {
            "metadata": {"phone_number_id": "109876543210"}, "contacts": [{"wa_id": self.uid}],
            "messages": [{"from": self.uid, "id": "wamid.synthetic." + uuid4().hex,
                          "type": "interactive", "interactive": {"type": "button_reply",
                          "button_reply": {"id": button_id, "title": title}}}],
        }}]}]}

    def callback(self, button_id, title="", lang="fr", history=None, real_chain=False):
        with ExitStack() as stack:
            stack.enter_context(patch.object(app, "META_APP_SECRET", "synthetic_secret"))
            stack.enter_context(patch("hmac.compare_digest", return_value=True))
            generated = None
            if not real_chain:
                generated = stack.enter_context(patch.object(app, "rag_chain", return_value={
                    "response": "NONFACTUAL_NAVIGATION_MARKER", "language": lang,
                    "route": "evidence_recommendation", "response_route": "evidence_recommendation",
                    "resolved_autonomously": False, "is_predefined": True,
                }))
            stack.enter_context(patch.object(app, "get_retriever", side_effect=AssertionError("Unexpected retrieval")))
            stack.enter_context(patch.object(app, "get_llm", side_effect=AssertionError("Unexpected generation")))
            sent = stack.enter_context(patch.object(app, "send_whatsapp_message", return_value=True))
            logged = stack.enter_context(patch.object(app.database, "log_interaction"))
            stack.enter_context(patch.object(app.database, "claim_webhook", return_value=("new", "synthetic_worker")))
            stack.enter_context(patch.object(app.database, "renew_webhook", return_value=True))
            stack.enter_context(patch.object(app.database, "finish_webhook", return_value=True))
            if history is not None:
                stack.enter_context(patch.object(app, "get_history", return_value=history))
            response = self.client.post("/webhook", json=self.payload(button_id, title))
            self.assertEqual(response.status_code, 200, response.text)
            self.assertTrue(sent.called)
            self.assertEqual(logged.call_args.kwargs["detected_language"], lang)
            self.assertTrue(all(button["id"].endswith(":" + lang) for button in sent.call_args.kwargs["buttons"]))
            return generated, sent.call_args.kwargs

    def assert_callback_query(self, action, lang):
        generated, _ = self.callback(action, lang=lang, history=[{"role": "human", "content": "hola"}])
        question = generated.call_args.args[0]
        if action.startswith(("btn_advisor", "btn_book")):
            # Handoff is implemented only for ES/EN/PT. The callback must still
            # register the request instead of becoming an unrecognized FR/IT text.
            self.assertTrue(handoff_support.requested(question), question)
            return
        self.assertEqual(app.detect_language(question), lang, question)
        if "camino-inka" in action:
            self.assertIn("Camino Inca Clásico 4D/3N", question)

    def test_french_callbacks_preserve_entity_and_language(self):
        for action in ("btn_tours:fr", "btn_cat:cusco:fr", "btn_cat_page:cusco:2:fr",
                       "btn_rates:camino-inka:fr", "btn_inc:camino-inka:fr",
                       "btn_photo:camino-inka:fr", "btn_tour:camino-inka:fr", "btn_advisor:fr",
                       "btn_book:camino-inka:fr"):
            with self.subTest(action=action):
                self.assert_callback_query(action, "fr")

    def test_italian_callbacks_preserve_entity_and_language(self):
        for action in ("btn_tours:it", "btn_cat:cusco:it", "btn_cat_page:cusco:2:it",
                       "btn_rates:camino-inka:it", "btn_inc:camino-inka:it",
                       "btn_photo:camino-inka:it", "btn_tour:camino-inka:it", "btn_advisor:it",
                       "btn_book:camino-inka:it"):
            with self.subTest(action=action):
                self.assert_callback_query(action, "it")

    def test_legacy_french_title(self):
        self.callback("btn_tours", "🗺️ Voir circuits", lang="fr")

    def test_legacy_italian_title(self):
        self.callback("btn_tours", "🗺️ Mostra tour", lang="it")

    def test_legacy_french_history(self):
        generated, _ = self.callback("btn_rates:camino-inka", "", lang="fr",
                                     history=[{"role": "human", "content": QUERIES["fr"]}])
        self.assertEqual(app.detect_language(generated.call_args.args[0]), "fr")

    def test_legacy_italian_history(self):
        generated, _ = self.callback("btn_rates:camino-inka", "", lang="it",
                                     history=[{"role": "human", "content": QUERIES["it"]}])
        self.assertEqual(app.detect_language(generated.call_args.args[0]), "it")

    def test_control_labels_preserve_meta_limits(self):
        for lang in ("fr", "it"):
            for route in ("evidence_recommendation", "evidence_listing", "evidence_inactive_tour",
                          "evidence_photo", "evidence_confirmed_price", "evidence_category_empty"):
                with self.subTest(lang=lang, route=route):
                    buttons = app.get_quick_buttons(route=route, detected_eid="camino-inka", lang=lang)
                    self.assertTrue(buttons)
                    self.assertLessEqual(len(buttons), 3)
                    for button in buttons:
                        self.assertTrue(button["id"].endswith(":" + lang))
                        self.assertLessEqual(len(button["id"]), 256)
                        self.assertLessEqual(len(button["title"]), 20)
                        self.assertNotRegex(button["title"], r"Asesor|asesor|Ver Tours|Qué incluye|Tarifas|Clásicos")

    def test_real_french_category_navigation(self):
        _, sent = self.callback("btn_tours:fr", lang="fr", real_chain=True)
        self.assertIn("Sélectionnez", sent["text"])
        _, sent = self.callback("btn_cat:cusco:fr", lang="fr", real_chain=True)
        self.assertIn("Maras - Moray", sent["text"])
        self.assertIn("Demi-journée", sent["text"])
        self.assertIn("Écrivez", sent["text"])

    def test_real_italian_category_navigation(self):
        _, sent = self.callback("btn_tours:it", lang="it", real_chain=True)
        self.assertIn("Seleziona", sent["text"])
        _, sent = self.callback("btn_cat:cusco:it", lang="it", real_chain=True)
        self.assertIn("Maras - Moray", sent["text"])
        self.assertIn("Mezza giornata", sent["text"])
        self.assertIn("Scrivi", sent["text"])


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    unittest.main()
