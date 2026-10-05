"""Regression: a documented product can have an undocumented price.

Run through tests/run_isolated.py. Loads only pure grader/test definitions;
does not import the application or contact any provider.
"""
import os
from pathlib import Path
import runpy
import unittest

if os.environ.get("TEXEIRA_ISOLATED_TEST") != "1":
    raise RuntimeError("Run with tests/run_isolated.py")

tests = Path(__file__).resolve().parent
definitions = runpy.run_path(str(tests / "test_review_grader_polarity_20261004.py"),
                            run_name="grader_definitions")
grade = definitions["grade"]
case = definitions["cases"]["ACAD-EN-04"]


class ProductConfirmationReview(unittest.TestCase):
    def test_confirmed_product_with_unconfirmed_price_is_accepted(self):
        answer = ("Choquequirao is a confirmed product documented by Texeira. "
                  "The price is not documented; please confirm it with the agency.")
        verdict = grade(case, {"response": answer}, 0)
        self.assertEqual(verdict["passed"], 1, verdict)

    def test_denied_product_remains_rejected(self):
        answer = "Choquequirao is not a confirmed product and is not documented by Texeira."
        self.assertEqual(grade(case, {"response": answer}, 0)["passed"], 0)


if __name__ == "__main__":
    unittest.main()
