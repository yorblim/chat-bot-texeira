"""Standard-library contract checks; no imports of app, retrieval or providers."""
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

SCRIPT = Path(__file__).with_name("evaluate_real_rag_batch_20261010.py")
SPEC = importlib.util.spec_from_file_location("real_rag_batch_contract", SCRIPT)
batch = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(batch)


class RunnerContract(unittest.TestCase):
    def test_dry_invocation_is_nonfactual_and_never_uses_client(self):
        class Forbidden:
            def invoke(self, *args, **kwargs):
                raise AssertionError("Network client must not be used")
        auditor = batch.AuditedLlm(client=Forbidden(), live=False, max_calls=1)
        result = auditor.invoke([("system", "context"), ("human", "question")])
        self.assertEqual(result.content, batch.DRY_SENTINEL)
        self.assertEqual(auditor.records[0]["execution"], "nonfactual_dry_sentinel")
        self.assertEqual(auditor.records[0]["input_messages"][-1]["content"], "question")

    def test_budget_is_absolute_and_exhaustion_halts_without_another_call(self):
        auditor = batch.AuditedLlm(max_calls=1)
        auditor.invoke([("human", "first")])
        with self.assertRaises(RuntimeError):
            auditor.invoke([("human", "second")])
        self.assertEqual(len(auditor.records), 1)
        self.assertTrue(auditor.halted)

    def test_provider_failure_is_recorded_and_stops_subsequent_invocation(self):
        class Failure:
            count = 0
            def invoke(self, *args, **kwargs):
                self.count += 1
                raise TimeoutError("SECRET_MUST_NOT_ENTER_REPORT")
        client = Failure()
        pacer = SimpleNamespace(before_call=lambda: None)
        auditor = batch.AuditedLlm(client=client, live=True, pacer=pacer)
        with self.assertRaises(TimeoutError):
            auditor.invoke([("human", "first")])
        with self.assertRaises(RuntimeError):
            auditor.invoke([("human", "second")])
        self.assertEqual(client.count, 1)
        self.assertEqual(auditor.records[0]["status"], "provider_error")
        self.assertNotIn("SECRET_MUST_NOT_ENTER_REPORT", json.dumps(auditor.records))

    def test_quota_pacer_is_bounded_and_uses_reported_completions(self):
        clock = [0.0]
        waits = []
        def sleep(seconds):
            self.assertGreater(seconds, 0)
            self.assertLessEqual(seconds, 60)
            waits.append(seconds)
            clock[0] += seconds
        pacer = batch.CompletionPacer(clock=lambda: clock[0], sleep=sleep, announce=lambda *a, **k: None)
        pacer.after_call(150)
        clock[0] = 11
        pacer.before_call()
        self.assertEqual(waits, [49.0])
        self.assertEqual(pacer.samples, [])

    def test_original_explorations_are_unique_finite_and_selectable(self):
        self.assertEqual(len(batch.CASES), 10)
        self.assertEqual(len({case[0] for case in batch.CASES}), 10)
        self.assertEqual(batch.select_cases(["EXP-148"])[0][0], "EXP-148")
        with self.assertRaises(ValueError):
            batch.select_cases(["FAKE"])
        with self.assertRaises(ValueError):
            batch.AuditedLlm(max_calls=11)

    def test_retrieval_failure_cannot_be_mistaken_for_empty_evidence(self):
        class Failure:
            def invoke(self, query):
                raise OSError("failure")
        audit = batch.AuditedRetriever(Failure())
        with self.assertRaises(OSError):
            audit.invoke("original question")
        self.assertTrue(audit.halted)
        self.assertEqual(audit.records[0]["status"], "retrieval_error")
        self.assertEqual(audit.records[0]["query"], "original question")

    def test_snapshot_preserves_explicit_empty_fields_and_rejects_wrong_activity(self):
        rows = [{"entity_id": eid, "is_active": True, "aliases": [], "includes": "",
                 "overridden_fields": ["includes"]} for eid in batch.ACTIVE_IDS]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "snapshot.json"
            path.write_text(json.dumps(rows), encoding="utf-8")
            loaded = batch.load_snapshot(path)
            self.assertEqual(loaded[0]["includes"], "")
            self.assertEqual(loaded[0]["overridden_fields"], ["includes"])
            rows[0]["is_active"] = False
            path.write_text(json.dumps(rows), encoding="utf-8")
            with self.assertRaises(ValueError):
                batch.load_snapshot(path)

    def test_protected_hashes_include_three_actual_histories_and_formal_registry(self):
        protected = batch.protected_hashes()
        for relative in (
            "docs/evaluaciones/RESULTADOS_POSPRUEBA_TESIS_20260921.json",
            "docs/evaluaciones/INFORME_POSPRUEBA_TESIS_20260921.md",
            "docs/evaluaciones/RESULTADOS_POSPRUEBA_TESIS_20261004_RECALIBRADO.json",
            "docs/REGISTRO_VALIDACION_WHATSAPP_00047.json",
        ):
            expected = str(Path(relative))
            self.assertIn(expected, protected)
            self.assertEqual(len(protected[expected]), 64)


if __name__ == "__main__":
    unittest.main()
