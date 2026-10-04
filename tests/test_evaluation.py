import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from agentops_api.demo_data import load_demo_bundle  # noqa: E402
from agentops_api.evaluation import evaluate_bundle  # noqa: E402


class BaselineEvaluationTests(unittest.TestCase):
    def test_report_measures_disposition_escalation_findings_and_evidence(self) -> None:
        report = evaluate_bundle(load_demo_bundle())

        self.assertEqual(report["case_count"], 7)
        self.assertEqual(report["disposition_accuracy"], 1.0)
        self.assertEqual(report["escalation"]["recall"], 1.0)
        self.assertEqual(report["finding_type_micro"]["f1"], 1.0)
        self.assertEqual(report["citation_validity"]["rate"], 1.0)
        self.assertTrue(report["human_review_gate"]["all_cases_passed"])
        self.assertTrue(report["synthetic"])
        self.assertEqual(report["evidence_status_micro"]["f1"], 1.0)
        c07 = next(case for case in report["cases"] if case["case_id"] == "C07")
        self.assertEqual(set(c07["actual_evidence_statuses"]), {
            "confirmed_conflict", "missing_from_supplied_text", "requirement_not_established"
        })

    def test_evaluation_report_discloses_small_synthetic_sample_limit(self) -> None:
        report = evaluate_bundle(load_demo_bundle())
        self.assertIn("fictional cases", report["interpretation_limit"])


if __name__ == "__main__":
    unittest.main()
