"""Independent review of recommendation and catalog regressions.

Run ONLY through tests/run_isolated.py. No real LLM, WhatsApp or production DB.
These assertions express the existing user requirements, not new features.
"""
import os
import unittest

if os.environ.get("TEXEIRA_ISOLATED_TEST") != "1":
    raise RuntimeError("Run with tests/run_isolated.py")

import app
import catalog_service
from test_recommendations_and_schedules import TestRecommendationsAndSchedules


class IndependentReview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        TestRecommendationsAndSchedules.setUpClass()

    def setUp(self):
        self.helper = TestRecommendationsAndSchedules()
        self.helper.setUp()
        self.snapshot = catalog_service.get_all_tours(active_only=False)

    def tearDown(self):
        for tour in self.snapshot:
            ok, detail = catalog_service.upsert_tour(tour)
            self.assertTrue(ok, detail)

    def send(self, text):
        result = self.helper._send(text)
        self.assertEqual(result["status_code"], 200)
        print("\nREVIEW INPUT:", text)
        print("REVIEW RESPONSE:", result["sent_text"])
        return result["sent_text"]

    def test_disabled_tours_are_not_recommended(self):
        for entity_id in ("laguna-humantay", "montana-7-colores"):
            tour = catalog_service.get_tour_by_id(entity_id)
            ok, detail = catalog_service.upsert_tour({**tour, "is_active": False})
            self.assertTrue(ok, detail)
        text = self.send("me gustan los paisajes")
        self.assertNotIn("Laguna Humantay", text)
        self.assertNotIn("Montaña de 7 Colores", text)

    def test_one_day_does_not_return_an_empty_recommendation(self):
        text = self.send("recomiéndame un tour de un día")
        self.assertTrue("•" in text or "?" in text,
                        "Must offer verified options or ask a useful question")

    def test_short_time_and_negative_hiking_preference_are_respected(self):
        text = self.send("Me gustan los paisajes, solo tengo medio día y no quiero caminatas")
        self.assertNotIn("4 días", text)
        self.assertNotIn("Full Day", text)

    def test_advice_for_a_selected_tour_is_not_destination_selection(self):
        text = self.send("¿Qué me recomiendas llevar para Laguna Humantay?")
        self.assertNotIn("estas son nuestras recomendaciones verificadas", text)
        self.assertNotIn("Montaña de 7 Colores", text)

    def test_cleared_schedule_stays_unconfirmed(self):
        tour = catalog_service.get_tour_by_id("montana-7-colores")
        ok, detail = catalog_service.upsert_tour({**tour, "schedule": ""})
        self.assertTrue(ok, detail)
        saved = catalog_service.get_tour_by_id("montana-7-colores")
        self.assertEqual(saved["schedule"], "")
        self.assertIn("schedule", saved["overridden_fields"])
        text = self.send("¿Cuál es el horario de Montaña de 7 Colores?")
        self.assertNotIn("04:30", text)
        self.assertNotIn("17:00", text)

    def test_pending_preference_question_is_not_counted_as_resolved(self):
        result = app.rag_chain("que tours me recomiendas", self.helper.test_uid)
        print("\nREVIEW PREFERENCE RESULT:", result)
        self.assertFalse(result.get("resolved_autonomously"))


if __name__ == "__main__":
    unittest.main(defaultTest="IndependentReview")
