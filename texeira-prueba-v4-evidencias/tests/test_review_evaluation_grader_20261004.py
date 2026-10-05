"""Check the existing evaluation grader without calling LLM, cloud or databases.

Run via tests/run_isolated.py. Only the pure evaluate_case function is loaded.
"""
import ast
import json
import os
import unittest
from pathlib import Path

if os.environ.get("TEXEIRA_ISOLATED_TEST") != "1":
    raise RuntimeError("Run via tests/run_isolated.py")

ROOT = Path(__file__).resolve().parents[1]
grader_file = ROOT / "tests" / "evaluate_thesis_postest.py"
tree = ast.parse(grader_file.read_text(encoding="utf-8"))
function = next(node for node in tree.body
                if isinstance(node, ast.FunctionDef) and node.name == "evaluate_case")
namespace = {}
exec(compile(ast.Module(body=[function], type_ignores=[]), str(grader_file), "exec"), namespace)
evaluate_case = namespace["evaluate_case"]

bank = json.loads((ROOT / "docs/evaluaciones/BANCO_EVALUACION_ACADEMICA.json").read_text(encoding="utf-8"))
results = json.loads((ROOT / "docs/evaluaciones/RESULTADOS_POSPRUEBA_TESIS_20260921.json").read_text(encoding="utf-8"))


class EvaluationGraderReview(unittest.TestCase):
    def setUp(self):
        self.case = next(row for row in bank["cases"] if row["id"] == "ACAD-EN-03")

    def test_saved_wrong_tour_answer_must_not_pass(self):
        row = next(row for row in results["cases"] if row["id"] == self.case["id"])
        verdict = evaluate_case(self.case, {"response": row["response"]}, 0)
        self.assertEqual(verdict["passed"], 0,
                         "Asked Inka Jungle duration; stored answer discusses Machu Picchu en Tren")

    def test_missing_required_duration_must_not_pass(self):
        verdict = evaluate_case(self.case, {"response":
            "The Inka Jungle trek is an agency tour. Please contact the team for details."}, 0)
        self.assertEqual(verdict["passed"], 0,
                         "The required published fact, 4 days, was never answered")

    def test_correct_published_duration_can_pass(self):
        verdict = evaluate_case(self.case, {"response":
            "The Inka Jungle trek to Machu Picchu has a published itinerary of 4 days."}, 0)
        self.assertEqual(verdict["passed"], 1)


if __name__ == "__main__":
    unittest.main()
