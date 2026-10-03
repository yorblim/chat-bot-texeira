"""Verify replacement of an earlier preference, not only accumulation.

Run via tests/run_isolated.py. Uses temporary catalog and simulated WhatsApp.
"""
import os
import unittest

if os.environ.get("TEXEIRA_ISOLATED_TEST") != "1":
    raise RuntimeError("Run with tests/run_isolated.py")

import test_review_recommendations_20261002 as base_review


class PreferenceReplacementReview(base_review.IndependentReview):
    def test_four_days_changed_to_two_days(self):
        self.send("Recomiéndame un tour de 4 días")
        text = self.send("Ahora recomiéndame para 2 días")
        self.assertNotIn("4 días", text)

    def test_one_day_changed_to_two_days_still_offers_matching_tours(self):
        self.send("Recomiéndame un tour de un día")
        text = self.send("Mejor recomiéndame para 2 días")
        self.assertIn("2 días", text)


if __name__ == "__main__":
    names = [
        "test_four_days_changed_to_two_days",
        "test_one_day_changed_to_two_days_still_offers_matching_tours",
    ]
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.TestSuite(PreferenceReplacementReview(name) for name in names)
    )
    raise SystemExit(0 if result.wasSuccessful() else 1)
