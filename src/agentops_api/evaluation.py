"""Offline evaluation utilities for the synthetic review benchmark."""

from __future__ import annotations

from collections import Counter
from typing import Any

from agentops_api.review_engine import review_case


def _prf(true_positive: int, false_positive: int, false_negative: int) -> dict[str, float]:
    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def _citation_check(case: dict[str, Any], policies: list[dict[str, Any]], result: dict[str, Any]) -> tuple[int, int]:
    contract_text = {
        clause["clause_id"]: clause["text"]
        for clause in case["contract"].get("clauses", [])
    }
    supplied_ids = set(case.get("policy_document_ids", []))
    policy_text = {
        clause["clause_id"]: (policy["document_id"], clause["text"])
        for policy in policies
        if policy.get("document_id") in supplied_ids
        for clause in policy.get("clauses", [])
    }
    checked = valid = 0
    for finding in result["findings"]:
        for evidence in finding.get("contract_evidence", []):
            checked += 1
            valid += evidence.get("clause_id") in contract_text and contract_text.get(evidence.get("clause_id")) == evidence.get("text")
        for evidence in finding.get("policy_evidence", []):
            checked += 1
            source = policy_text.get(evidence.get("clause_id"))
            valid += source is not None and source == (evidence.get("document_id"), evidence.get("text"))
    return checked, int(valid)


def evaluate_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    """Compare reviewer outputs with labels, without exposing labels to review_case."""
    cases = bundle["cases_document"]["cases"]
    policies = bundle["policies"]
    matched_dispositions = 0
    escalation_counts = Counter()
    expected_findings: set[tuple[str, str]] = set()
    actual_findings: set[tuple[str, str]] = set()
    expected_evidence: set[tuple[str, str]] = set()
    actual_evidence: set[tuple[str, str]] = set()
    case_results = []
    citations_checked = citations_valid = 0
    human_gate_passed = 0

    for case in cases:
        case_id = case["case_id"]
        expected = case["expected"]
        # Pass a label-free copy to the reviewer to preserve the evaluation boundary.
        review_bundle = {
            "policies": policies,
            "cases_document": {
                "cases": [
                    {key: value for key, value in candidate.items() if key != "expected"}
                    for candidate in cases
                ]
            },
        }
        actual = review_case(case_id, review_bundle)
        expected_disposition = expected["disposition"]
        disposition_correct = actual["disposition"] == expected_disposition
        matched_dispositions += int(disposition_correct)

        expected_escalate = bool(expected["requires_escalation"])
        actual_escalate = bool(actual["requires_escalation"])
        if expected_escalate and actual_escalate:
            escalation_counts["tp"] += 1
        elif actual_escalate:
            escalation_counts["fp"] += 1
        elif expected_escalate:
            escalation_counts["fn"] += 1
        else:
            escalation_counts["tn"] += 1

        expected_types = {item["issue_type"] for item in expected.get("findings", [])}
        actual_types = {item["issue_type"] for item in actual["findings"]}
        expected_statuses = {item["evidence_status"] for item in expected.get("findings", [])}
        actual_statuses = {item["evidence_status"] for item in actual["findings"]}
        expected_findings.update((case_id, issue) for issue in expected_types)
        actual_findings.update((case_id, issue) for issue in actual_types)
        expected_evidence.update((case_id, status) for status in expected_statuses)
        actual_evidence.update((case_id, status) for status in actual_statuses)
        checked, valid = _citation_check(case, policies, actual)
        citations_checked += checked
        citations_valid += valid
        human_gate_passed += int(actual.get("human_final_decision_required") is True)
        case_results.append({
            "case_id": case_id,
            "expected_disposition": expected_disposition,
            "actual_disposition": actual["disposition"],
            "disposition_correct": disposition_correct,
            "expected_issue_types": sorted(expected_types),
            "actual_issue_types": sorted(actual_types),
            "expected_evidence_statuses": sorted(expected_statuses),
            "actual_evidence_statuses": sorted(actual_statuses),
            "citations_checked": checked,
            "citations_valid": valid,
            "human_final_decision_required": actual.get("human_final_decision_required"),
        })

    true_positive = len(expected_findings & actual_findings)
    false_positive = len(actual_findings - expected_findings)
    false_negative = len(expected_findings - actual_findings)
    n = len(cases)
    escalation = _prf(
        escalation_counts["tp"], escalation_counts["fp"], escalation_counts["fn"]
    )
    finding_metrics = _prf(true_positive, false_positive, false_negative)
    evidence_metrics = _prf(
        len(expected_evidence & actual_evidence),
        len(actual_evidence - expected_evidence),
        len(expected_evidence - actual_evidence),
    )
    return {
        "dataset_version": bundle["cases_document"].get("dataset_version", "unknown"),
        "synthetic": bundle["cases_document"].get("synthetic") is True,
        "evaluation_scope": "offline deterministic baseline on labeled fictional cases",
        "case_count": n,
        "disposition_accuracy": matched_dispositions / n if n else 0.0,
        "disposition_correct_count": matched_dispositions,
        "escalation": {
            **escalation,
            "true_positive": escalation_counts["tp"],
            "false_positive": escalation_counts["fp"],
            "false_negative": escalation_counts["fn"],
            "true_negative": escalation_counts["tn"],
        },
        "finding_type_micro": {
            **finding_metrics,
            "true_positive": true_positive,
            "false_positive": false_positive,
            "false_negative": false_negative,
        },
        "evidence_status_micro": {
            **evidence_metrics,
            "true_positive": len(expected_evidence & actual_evidence),
            "false_positive": len(actual_evidence - expected_evidence),
            "false_negative": len(expected_evidence - actual_evidence),
            "categories": ["confirmed_conflict", "missing_from_supplied_text", "requirement_not_established"],
        },
        "citation_validity": {
            "checked": citations_checked,
            "valid": citations_valid,
            "rate": citations_valid / citations_checked if citations_checked else 1.0,
        },
        "human_review_gate": {
            "passed_cases": human_gate_passed,
            "all_cases_passed": human_gate_passed == n,
        },
        "cases": case_results,
        "interpretation_limit": (
            "Seven fictional cases are a prototype benchmark, not evidence of production accuracy or legal compliance. No real customer contracts were included."
        ),
    }
