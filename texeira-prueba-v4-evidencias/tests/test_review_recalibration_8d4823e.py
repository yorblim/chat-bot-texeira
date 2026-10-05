"""Independent, offline verification of commit 8d4823e.

Run with tests/run_isolated.py. Reuses historical answers; mocks all LLM calls.
Quality reports and the Chroma copy are confined to the runner's temporary state.
"""
import ast
import hashlib
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import unittest

if os.environ.get("TEXEIRA_ISOLATED_TEST") != "1":
    raise RuntimeError("Run with tests/run_isolated.py")

ROOT = Path(__file__).resolve().parents[1]
EVALUATIONS = ROOT / "docs" / "evaluaciones"
source = ROOT / "tests" / "evaluate_thesis_postest.py"
tree = ast.parse(source.read_text(encoding="utf-8"))
function = next(node for node in tree.body
                if isinstance(node, ast.FunctionDef) and node.name == "evaluate_case")
namespace = {}
exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), "exec"), namespace)
grade = namespace["evaluate_case"]


class RecalibrationReview(unittest.TestCase):
    def test_recomputed_historical_results_match_every_case(self):
        old = json.loads((EVALUATIONS / "RESULTADOS_POSPRUEBA_TESIS_20260921.json").read_text(encoding="utf-8"))
        new = json.loads((EVALUATIONS / "RESULTADOS_POSPRUEBA_TESIS_20261004_RECALIBRADO.json").read_text(encoding="utf-8"))
        bank = json.loads((EVALUATIONS / "BANCO_EVALUACION_ACADEMICA.json").read_text(encoding="utf-8"))
        definitions = {case["id"]: case for case in bank["cases"]}
        revised = {case["id"]: case for case in new["cases"]}
        self.assertEqual(len(old["cases"]), 30)
        self.assertEqual(set(revised), set(definitions))
        totals = {key: 0 for key in ("ip", "ff", "ci", "mi", "passed")}
        failed = []
        for saved in old["cases"]:
            current = revised[saved["id"]]
            self.assertEqual(saved["response"], current["response"])
            self.assertEqual(saved["question"], current["question"])
            data = {"response": saved["response"], **{
                key: saved["eval"][key] for key in
                ("route", "resolved_autonomously", "escalated_to_human")}}
            result = grade(definitions[saved["id"]], data, saved["eval"]["latency_ms"])
            for key in totals:
                self.assertEqual(result[key], current["eval"][key], (saved["id"], key))
                totals[key] += result[key]
            self.assertEqual(result["reasons"], current["eval"]["reasons"], saved["id"])
            if not result["passed"]:
                failed.append(saved["id"])
        self.assertEqual(totals, {"ip": 29, "ff": 22, "ci": 30, "mi": 30, "passed": 22})
        self.assertEqual(new["indicators"]["2.4_precision_global_pct"], round(totals["passed"] / 30 * 100, 1))
        print("RECOMPUTED:", totals, "FAILED:", failed)

    def test_original_historical_artifacts_are_unchanged(self):
        for name in ("RESULTADOS_POSPRUEBA_TESIS_20260921.json", "INFORME_POSPRUEBA_TESIS_20260921.md"):
            relative = "texeira-prueba-v4-evidencias/docs/evaluaciones/" + name
            previous = subprocess.run(["git", "show", "06512b1:" + relative], cwd=ROOT,
                                      capture_output=True, check=True).stdout
            self.assertEqual(hashlib.sha256(previous).digest(),
                             hashlib.sha256((EVALUATIONS / name).read_bytes()).digest(), name)

    def test_quality_with_mock_and_temporary_reports(self):
        state = Path(os.environ["TEXEIRA_STATE_DIR"])
        index = ROOT / "chroma_catalogo_20260926_db"
        temporary_index = state / "review-chroma"
        if index.is_dir():
            shutil.copytree(index, temporary_index)
        os.environ["CHROMA_HYBRID_DIR"] = str(temporary_index)
        loaded = runpy.run_path(str(ROOT / "tests" / "test_calidad_whatsapp.py"),
                               run_name="quality_review")
        fn = loaded["test_calidad_whatsapp"]
        fn.__globals__["ROOT_DIR"] = state
        import app
        import database
        import catalog_service
        database.init_db(app.SQLITE_DB_PATH)
        catalog_service.init_catalog_db()
        fn()
        reports = list((state / "docs" / "evaluaciones").glob("test_calidad_whatsapp_*.json"))
        self.assertTrue(reports)
        report = json.loads(reports[0].read_text(encoding="utf-8"))
        self.assertEqual(report["metadata"]["tipo_evaluacion"], "validacion_simulada_de_rutas_con_mock")
        self.assertEqual(len(report["resultados_detallados"]), 13)


if __name__ == "__main__":
    unittest.main()
