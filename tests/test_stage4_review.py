import copy
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from agentops_api.demo_data import load_demo_bundle  # noqa: E402
from agentops_api.review_engine import ReviewCaseNotFound, review_case  # noqa: E402


class ReviewEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = load_demo_bundle()
        cls.cases = {
            case["case_id"]: case
            for case in cls.bundle["cases_document"]["cases"]
        }

    def test_reviews_match_all_seven_labeled_outcomes(self) -> None:
        for case_id, case in self.cases.items():
            with self.subTest(case_id=case_id):
                result = review_case(case_id, self.bundle)
                expected = case["expected"]
                self.assertEqual(result["disposition"], expected["disposition"])
                self.assertEqual(result["requires_escalation"], expected["requires_escalation"])
                self.assertEqual(
                    {finding["issue_type"] for finding in result["findings"]},
                    {finding["issue_type"] for finding in expected["findings"]},
                )
                self.assertEqual(
                    {finding["evidence_status"] for finding in result["findings"]},
                    {finding["evidence_status"] for finding in expected["findings"]},
                )

    def test_expected_labels_are_not_needed_to_run_the_reviewer(self) -> None:
        unlabeled = copy.deepcopy(self.bundle)
        for case in unlabeled["cases_document"]["cases"]:
            case.pop("expected")
        results = [review_case(case_id, unlabeled) for case_id in sorted(self.cases)]
        self.assertEqual(len(results), 7)
        self.assertEqual(results[2]["disposition"], "escalate")

    def test_every_returned_citation_resolves_to_exact_supplied_text(self) -> None:
        for case_id, case in self.cases.items():
            result = review_case(case_id, self.bundle)
            contract_text = {
                clause["clause_id"]: clause["text"]
                for clause in case["contract"]["clauses"]
            }
            supplied_policy_ids = set(case["policy_document_ids"])
            policy_text = {
                clause["clause_id"]: (policy["document_id"], clause["text"])
                for policy in self.bundle["policies"]
                if policy["document_id"] in supplied_policy_ids
                for clause in policy["clauses"]
            }
            for finding in result["findings"]:
                self.assertTrue(finding["contract_clause_ids"])
                self.assertTrue(finding["policy_clause_ids"])
                self.assertEqual(
                    [item["text"] for item in finding["contract_evidence"]],
                    [contract_text[item] for item in finding["contract_clause_ids"]],
                )
                for item in finding["policy_evidence"]:
                    self.assertIn(item["clause_id"], finding["policy_clause_ids"])
                    self.assertEqual(
                        (item["document_id"], item["text"]),
                        policy_text[item["clause_id"]],
                    )

    def test_policy_conflict_cites_both_active_policy_documents(self) -> None:
        result = review_case("C05", self.bundle)
        finding = result["findings"][0]
        self.assertEqual(finding["issue_type"], "policy_source_conflict")
        self.assertEqual(
            {item["document_id"] for item in finding["policy_evidence"]},
            {"POL-STANDARD-1.0", "POL-FINANCE-DATA-2.0"},
        )

    def test_vague_incident_wording_is_escalated_without_inventing_a_deadline(self) -> None:
        result = review_case("C06", self.bundle)
        finding = result["findings"][0]
        self.assertEqual(finding["issue_type"], "incident_notice_deadline_ambiguous")
        self.assertIn("Do not assume", finding["rationale"])

    def test_reviewer_flags_a_more_severe_liability_change(self) -> None:
        changed = copy.deepcopy(self.bundle)
        liability = next(
            clause for clause in changed["cases_document"]["cases"][0]["contract"]["clauses"]
            if clause["topic"] == "Liability cap"
        )
        liability["text"] = "The supplier's aggregate liability is capped at fees paid or payable during the 3 months before the event."

        result = review_case("C01", changed)

        self.assertIn(
            "liability_cap_below_policy_minimum",
            {finding["issue_type"] for finding in result["findings"]},
        )
        self.assertEqual(result["disposition"], "escalate")

    def test_reviewer_flags_incident_deadline_over_72_hours(self) -> None:
        changed = copy.deepcopy(self.bundle)
        incident = next(
            clause for clause in changed["cases_document"]["cases"][0]["contract"]["clauses"]
            if clause["topic"] == "Security incident notice"
        )
        incident["text"] = "The supplier will notify the company within 96 hours of discovery."

        result = review_case("C01", changed)

        self.assertIn(
            "incident_notice_exceeds_policy",
            {finding["issue_type"] for finding in result["findings"]},
        )

    def test_unknown_case_returns_a_clear_domain_error(self) -> None:
        with self.assertRaises(ReviewCaseNotFound):
            review_case("C99", self.bundle)


if __name__ == "__main__":
    unittest.main()
