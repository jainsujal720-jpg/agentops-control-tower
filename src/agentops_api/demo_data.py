"""Load and validate the fictional Stage 3 evaluation data."""

import json
import os
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
# Local development keeps data at the repository root. The Docker image sets
# AGENTOPS_DATA_DIR=/app/data because installed Python packages live elsewhere.
DATA_DIR = Path(os.environ.get("AGENTOPS_DATA_DIR", PROJECT_ROOT / "data"))
POLICY_DIR = DATA_DIR / "policies"
CASES_FILE = DATA_DIR / "evaluation_cases.json"
ALLOWED_DISPOSITIONS = {"approve", "negotiate", "escalate"}
ALLOWED_SEVERITIES = {"low", "medium", "high", "critical"}
ALLOWED_EVIDENCE_STATUSES = {
    "confirmed_conflict", "missing_from_supplied_text", "requirement_not_established"
}


def load_demo_bundle() -> dict[str, Any]:
    """Load policy documents and evaluation cases from the project data folder."""
    policies = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(POLICY_DIR.glob("*.json"))
    ]
    cases_document = json.loads(CASES_FILE.read_text(encoding="utf-8"))
    return {"policies": policies, "cases_document": cases_document}


def validate_demo_bundle(bundle: dict[str, Any]) -> list[str]:
    """Return readable data-integrity errors; an empty list means valid."""
    errors: list[str] = []
    policies = bundle.get("policies", [])
    cases_document = bundle.get("cases_document", {})
    cases = cases_document.get("cases", [])

    policy_docs: dict[str, dict[str, Any]] = {}
    policy_clauses: dict[str, str] = {}
    for policy in policies:
        doc_id = policy.get("document_id")
        if not doc_id:
            errors.append("Every policy must have a document_id.")
            continue
        if doc_id in policy_docs:
            errors.append(f"Duplicate policy document_id: {doc_id}.")
        policy_docs[doc_id] = policy
        for clause in policy.get("clauses", []):
            clause_id = clause.get("clause_id")
            if not clause_id:
                errors.append(f"Policy {doc_id} has a clause without clause_id.")
                continue
            if clause_id in policy_clauses:
                errors.append(f"Duplicate policy clause_id: {clause_id}.")
            policy_clauses[clause_id] = doc_id

    if cases_document.get("synthetic") is not True:
        errors.append("The evaluation dataset must be explicitly marked synthetic.")

    seen_case_ids: set[str] = set()
    for case in cases:
        case_id = case.get("case_id", "<missing>")
        if case_id in seen_case_ids:
            errors.append(f"Duplicate case_id: {case_id}.")
        seen_case_ids.add(case_id)

        supplied_docs = set(case.get("policy_document_ids", []))
        for doc_id in supplied_docs:
            if doc_id not in policy_docs:
                errors.append(f"Case {case_id} references unknown policy document {doc_id}.")

        contract = case.get("contract", {})
        contract_clauses = contract.get("clauses", [])
        contract_clause_ids = [c.get("clause_id") for c in contract_clauses]
        if len(contract_clause_ids) != len(set(contract_clause_ids)):
            errors.append(f"Case {case_id} has duplicate contract clause IDs.")

        expected = case.get("expected", {})
        disposition = expected.get("disposition")
        if disposition not in ALLOWED_DISPOSITIONS:
            errors.append(f"Case {case_id} has invalid disposition {disposition!r}.")
        if expected.get("requires_escalation") is not (disposition == "escalate"):
            errors.append(f"Case {case_id} escalation label conflicts with its disposition.")

        findings = expected.get("findings", [])
        if disposition == "approve" and findings:
            errors.append(f"Case {case_id} is labeled approve but includes expected findings.")
        if disposition in {"negotiate", "escalate"} and not findings:
            errors.append(f"Case {case_id} needs at least one expected finding.")

        for finding in findings:
            finding_id = finding.get("finding_id", "<missing>")
            if finding.get("severity") not in ALLOWED_SEVERITIES:
                errors.append(f"Finding {finding_id} has an invalid severity.")
            if finding.get("evidence_status") not in ALLOWED_EVIDENCE_STATUSES:
                errors.append(f"Finding {finding_id} has an invalid or missing evidence_status.")
            cited_contract_ids = finding.get("contract_clause_ids", [])
            if not cited_contract_ids:
                errors.append(f"Finding {finding_id} has no contract evidence reference.")
            for clause_id in cited_contract_ids:
                if clause_id not in contract_clause_ids:
                    errors.append(f"Finding {finding_id} cites unknown contract clause {clause_id}.")

            cited_policy_ids = finding.get("policy_clause_ids", [])
            if not cited_policy_ids:
                errors.append(f"Finding {finding_id} has no policy evidence reference.")
            for clause_id in cited_policy_ids:
                doc_id = policy_clauses.get(clause_id)
                if doc_id is None:
                    errors.append(f"Finding {finding_id} cites unknown policy clause {clause_id}.")
                elif doc_id not in supplied_docs:
                    errors.append(f"Finding {finding_id} cites policy clause {clause_id} from an unsupplied document.")

    return errors
