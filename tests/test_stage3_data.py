import copy
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from agentops_api.demo_data import load_demo_bundle, validate_demo_bundle  # noqa: E402


class DemoDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = load_demo_bundle()
        cls.cases = {
            case["case_id"]: case
            for case in cls.bundle["cases_document"]["cases"]
        }

    def test_all_seven_labeled_cases_are_valid(self) -> None:
        self.assertEqual(validate_demo_bundle(self.bundle), [])
        self.assertEqual(set(self.cases), {"C01", "C02", "C03", "C04", "C05", "C06", "C07"})

    def test_scenarios_cover_expected_decision_types(self) -> None:
        labels = {case["expected"]["disposition"] for case in self.cases.values()}
        self.assertEqual(labels, {"approve", "negotiate", "escalate"})
        self.assertEqual(self.cases["C01"]["expected"]["disposition"], "approve")
        self.assertEqual(self.cases["C02"]["expected"]["disposition"], "negotiate")
        self.assertTrue(all(self.cases[c]["expected"]["requires_escalation"] for c in ["C03", "C04", "C05", "C06"]))
        c07_statuses = {item["evidence_status"] for item in self.cases["C07"]["expected"]["findings"]}
        self.assertEqual(c07_statuses, {
            "confirmed_conflict", "missing_from_supplied_text", "requirement_not_established"
        })

    def test_conflicting_policy_case_cites_both_sources(self) -> None:
        case = self.cases["C05"]
        finding = case["expected"]["findings"][0]
        self.assertEqual(set(case["policy_document_ids"]), {"POL-STANDARD-1.0", "POL-FINANCE-DATA-2.0"})
        self.assertEqual(set(finding["policy_clause_ids"]), {"STD-PAYMENT-01", "FIN-DATA-PAYMENT-01"})

    def test_ambiguous_notice_case_escalates_instead_of_assuming_deadline(self) -> None:
        case = self.cases["C06"]
        self.assertEqual(case["expected"]["disposition"], "escalate")
        self.assertIn("Do not assume", case["expected"]["findings"][0]["rationale"])

    def test_validator_detects_broken_evidence_reference(self) -> None:
        broken = copy.deepcopy(self.bundle)
        broken["cases_document"]["cases"][1]["expected"]["findings"][0]["contract_clause_ids"] = ["MISSING-CLAUSE"]

        errors = validate_demo_bundle(broken)

        self.assertTrue(any("unknown contract clause MISSING-CLAUSE" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
