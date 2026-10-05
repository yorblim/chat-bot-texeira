"""Negative controls for the existing bank, offline and without application imports.

These tests describe required corrections; they intentionally expose commit
8d4823e's remaining false approvals. Run via tests/run_isolated.py.
"""
import ast
import json
import os
from pathlib import Path
import unittest

if os.environ.get("TEXEIRA_ISOLATED_TEST") != "1":
    raise RuntimeError("Run with tests/run_isolated.py")

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / "tests" / "evaluate_thesis_postest.py"
tree = ast.parse(source.read_text(encoding="utf-8"))
function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "evaluate_case")
namespace = {}
exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), "exec"), namespace)
grade = namespace["evaluate_case"]
evaluations = ROOT / "docs" / "evaluaciones"
bank = json.loads((evaluations / "BANCO_EVALUACION_ACADEMICA.json").read_text(encoding="utf-8"))
cases = {c["id"]: c for c in bank["cases"]}


class GraderPolarityReview(unittest.TestCase):
    def assert_rejected(self, case_id, answer):
        verdict = grade(cases[case_id], {"response": answer}, 0)
        self.assertEqual(verdict["passed"], 0, (case_id, answer, verdict))

    def assert_accepted(self, case_id, answer):
        verdict = grade(cases[case_id], {"response": answer}, 0)
        self.assertEqual(verdict["passed"], 1, (case_id, answer, verdict))

    def test_ticket_included_is_not_proved_excluded_by_unrelated_lunch(self):
        self.assert_rejected("ACAD-EN-02",
                             "Sacred Valley includes the tourist ticket. Lunch is not included.")

    def test_positive_control_ticket_properly_excluded(self):
        self.assert_accepted("ACAD-EN-02",
                             "The Sacred Valley tour includes transport and guide. The tourist ticket is not included.")

    def test_denial_of_documented_product_must_not_pass(self):
        self.assert_rejected("ACAD-EN-04",
                             "Choquequirao is not a confirmed product and is not documented by Texeira.")

    def test_positive_control_documented_product_passes(self):
        self.assert_accepted("ACAD-EN-04",
                             "Choquequirao is a confirmed product documented by Texeira in our portfolio.")

    def test_unrelated_negation_does_not_erase_invented_buffet(self):
        self.assert_rejected("ACAD-ES-01",
                             "Waqra Pukara incluye transporte turístico, guía profesional y almuerzo buffet. No incluye entradas.")

    def test_positive_control_properly_negated_buffet_passes(self):
        self.assert_accepted("ACAD-ES-01",
                             "Waqra Pukara incluye transporte turístico y guía profesional. No incluye almuerzo buffet.")

    def test_recalibration_preserves_original_route_and_operational_flags(self):
        original = json.loads((evaluations / "RESULTADOS_POSPRUEBA_TESIS_20260921.json").read_text(encoding="utf-8"))
        revised = json.loads((evaluations / "RESULTADOS_POSPRUEBA_TESIS_20261004_RECALIBRADO.json").read_text(encoding="utf-8"))
        new = {c["id"]: c for c in revised["cases"]}
        mismatches = []
        for saved in original["cases"]:
            for field in ("route", "resolved_autonomously", "escalated_to_human", "latency_ms"):
                if new[saved["id"]]["eval"][field] != saved["eval"][field]:
                    mismatches.append((saved["id"], field))
        self.assertFalse(mismatches,
                         f"{len(mismatches)} lost metadata fields; first examples: {mismatches[:5]}")


if __name__ == "__main__":
    unittest.main()
