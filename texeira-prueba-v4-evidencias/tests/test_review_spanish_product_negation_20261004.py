"""Offline Spanish polarity controls for the documented Choquequirao product.

Synthetic translations of the same required fact, with a Spanish language flag.
No app import, provider call, or changes to the historical evaluation bank.
"""
import os
from pathlib import Path
import runpy
import unittest

if os.environ.get("TEXEIRA_ISOLATED_TEST") != "1":
    raise RuntimeError("Run with tests/run_isolated.py")

definitions = runpy.run_path(
    str(Path(__file__).resolve().parent / "test_review_grader_polarity_20261004.py"),
    run_name="grader_definitions")
grade = definitions["grade"]
case = {**definitions["cases"]["ACAD-EN-04"], "language": "es"}


class SpanishProductPolarityReview(unittest.TestCase):
    def assert_grade(self, answer, expected):
        verdict = grade(case, {"response": answer}, 0)
        self.assertEqual(verdict["passed"], expected, (answer, verdict))
        self.assertEqual(verdict["ff"], expected, (answer, verdict))

    def test_agency_denies_offering_documented_product(self):
        self.assert_grade(
            "Choquequirao es un producto documentado, pero Texeira no ofrece Choquequirao.", 0)

    def test_product_confirmation_is_explicitly_denied(self):
        self.assert_grade("Choquequirao no está confirmado como producto de Texeira.", 0)

    def test_documented_product_with_undocumented_price(self):
        self.assert_grade(
            "Choquequirao es un producto confirmado y documentado por Texeira. "
            "Su precio no está documentado por Texeira.", 1)

    def test_documented_product_with_unconfirmed_price(self):
        self.assert_grade(
            "Choquequirao es un producto confirmado y documentado por Texeira. "
            "Su precio no está confirmado.", 1)

    def test_price_of_named_product_is_not_product_subject(self):
        self.assert_grade(
            "Choquequirao está documentado por Texeira. "
            "El precio de Choquequirao no está documentado por Texeira.", 1)

    def test_english_price_of_named_product_is_not_product_subject(self):
        answer = ("Choquequirao is documented by Texeira. "
                  "The price of Choquequirao is not documented by Texeira.")
        english_case = definitions["cases"]["ACAD-EN-04"]
        self.assertEqual(grade(english_case, {"response": answer}, 0)["passed"], 1)

    def test_auxiliary_negation_does_not_hide_later_product_denial(self):
        answer = ("Choquequirao is documented by Texeira. "
                  "The price of Choquequirao is not documented by Texeira. "
                  "However, Choquequirao is not documented as a product.")
        english_case = definitions["cases"]["ACAD-EN-04"]
        self.assertEqual(grade(english_case, {"response": answer}, 0)["passed"], 0)


if __name__ == "__main__":
    unittest.main()
