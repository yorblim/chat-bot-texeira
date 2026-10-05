"""Offline regression: attribution to Texeira does not change the price subject."""
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
case = definitions["cases"]["ACAD-EN-04"]


class PriceSubjectReview(unittest.TestCase):
    def test_documented_product_with_price_not_documented_by_agency(self):
        answer = ("Choquequirao is documented by Texeira. "
                  "Its price is not documented by Texeira.")
        verdict = grade(case, {"response": answer}, 0)
        self.assertEqual(verdict["passed"], 1, verdict)

    def test_product_not_documented_by_agency_remains_rejected(self):
        answer = "Choquequirao is not documented by Texeira."
        self.assertEqual(grade(case, {"response": answer}, 0)["passed"], 0)


if __name__ == "__main__":
    unittest.main()
