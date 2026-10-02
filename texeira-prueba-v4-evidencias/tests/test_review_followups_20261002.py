"""Check remaining requirements of the existing recommendations/catalog task.

Only run via tests/run_isolated.py; uses temporary data and mock WhatsApp/LLM.
"""
import os
import unittest

if os.environ.get("TEXEIRA_ISOLATED_TEST") != "1":
    raise RuntimeError("Run with tests/run_isolated.py")

import catalog_service
import test_review_recommendations_20261002 as base_review


class FollowupReview(base_review.IndependentReview):
    def test_two_days_excludes_four_day_tours(self):
        text = self.send("Recomiéndame un tour de 2 días")
        self.assertNotIn("4 días", text)

    def test_hiking_rejection_survives_time_followup(self):
        self.send("que tours me recomiendas")
        self.send("no quiero caminatas")
        text = self.send("un día")
        self.assertNotIn("Laguna Humantay", text)
        self.assertNotIn("Montaña de 7 Colores", text)

    def test_duration_clear_is_respected_in_category(self):
        tour = catalog_service.get_tour_by_id("montana-7-colores")
        ok, detail = catalog_service.upsert_tour({**tour, "duration": ""})
        self.assertTrue(ok, detail)
        saved = catalog_service.get_tour_by_id("montana-7-colores")
        self.assertEqual(saved["duration"], "")
        self.assertIn("duration", saved["overridden_fields"])
        text = self.send("categoria cusco")
        mountain_line = next(line for line in text.splitlines() if "Montaña de 7 Colores" in line)
        self.assertNotIn("Full Day", mountain_line)

    def test_duration_edit_is_respected_in_recommendation_filter(self):
        tour = catalog_service.get_tour_by_id("city-tour-cusco")
        ok, detail = catalog_service.upsert_tour({**tour, "duration": "2 días"})
        self.assertTrue(ok, detail)
        text = self.send("recomiéndame un tour de medio día")
        self.assertNotIn("City Tour Cusco", text)


if __name__ == "__main__":
    names = [
        "test_two_days_excludes_four_day_tours",
        "test_hiking_rejection_survives_time_followup",
        "test_duration_clear_is_respected_in_category",
        "test_duration_edit_is_respected_in_recommendation_filter",
    ]
    suite = unittest.TestSuite(FollowupReview(name) for name in names)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
