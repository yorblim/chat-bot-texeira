"""Check that batch evidence cannot silently approve failed/pending cases."""
from copy import deepcopy
import json
import unittest

from run_pilot_batch import parse_records, validate_bank


class BatchEvidenceContract(unittest.TestCase):
    def setUp(self):
        self.cases = [dict(id="case-1", inputs=["precio camino inca"],
                           outputs=[dict(response="Synthetic fixture rate")],
                           status="passed", checks=[dict(name="fixture rate", passed=True)])]
        self.summary = dict(total_cases=1, total_messages=1, passed=1,
                            failed=0, pending_review=0)

    def test_valid_assertion_record_is_accepted(self):
        self.assertEqual(validate_bank(self.cases, [self.summary]), [])

    def test_failed_record_is_rejected_even_with_matching_summary(self):
        self.cases[0]["status"] = "failed"
        self.summary.update(passed=0, failed=1)
        self.assertTrue(validate_bank(self.cases, [self.summary]))

    def test_missing_or_failed_checks_cannot_be_approved(self):
        for checks in ([], [dict(name="price", passed=False)], [dict(name="price", passed=1)]):
            with self.subTest(checks=checks):
                case = deepcopy(self.cases[0])
                case["checks"] = checks
                self.assertTrue(validate_bank([case], [self.summary]))

    def test_duplicate_ids_and_summary_mismatches_are_rejected(self):
        self.assertTrue(validate_bank(self.cases * 2, [self.summary]))
        summary = {**self.summary, "passed": 100}
        self.assertTrue(validate_bank(self.cases, [summary]))
        self.assertTrue(validate_bank(self.cases, [self.summary, self.summary]))

    def test_language_exploration_remains_pending(self):
        self.cases[0].update(status="pending_review", reason="No real LLM/human language review")
        self.summary.update(passed=0, pending_review=1)
        self.assertEqual(validate_bank(self.cases, [self.summary]), [])
        self.assertEqual(self.summary["passed"], 0)
        self.cases[0].pop("reason")
        self.assertTrue(validate_bank(self.cases, [self.summary]))

    def test_missing_responses_and_exceptions_cannot_silently_pass(self):
        self.cases[0]["outputs"] = []
        self.assertTrue(validate_bank(self.cases, [self.summary]))
        self.cases[0]["outputs"] = [dict(response="Synthetic fixture rate")]
        self.cases[0]["exception"] = "transport failed"
        self.assertTrue(validate_bank(self.cases, [self.summary]))

    def test_corrupt_json_records_are_reported(self):
        output = "ROBUSTNESS_CASE broken-json\nROBUSTNESS_SUMMARY " + json.dumps(self.summary)
        cases, summaries, errors = parse_records(output)
        self.assertFalse(cases)
        self.assertEqual(summaries, [self.summary])
        self.assertTrue(errors)


if __name__ == "__main__":
    unittest.main(verbosity=2)
