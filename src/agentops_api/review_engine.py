"""Deterministic, evidence-linked procurement policy review baseline.

The review uses contract clauses and policy controls only. It never reads
human-authored expected labels, which remain reserved for offline evaluation.
"""

import re
from typing import Any

from agentops_api.demo_data import load_demo_bundle

_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
}


class ReviewCaseNotFound(LookupError):
    """Raised when the requested fictional case does not exist."""


def _number(value: str) -> int | None:
    return int(value) if value.isdigit() else _NUMBER_WORDS.get(value.lower())


def _topic_clauses(case: dict[str, Any], keyword: str) -> list[dict[str, Any]]:
    return [
        clause for clause in case["contract"]["clauses"]
        if keyword in clause.get("topic", "").lower()
    ]


def _payment_days(text: str) -> int | None:
    for pattern in (r"\bnet\s+(\d+)\b", r"\bwithin\s+(\d+)\s+days\b"):
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def _policy_rules(
    case: dict[str, Any],
    policies: list[dict[str, Any]],
    control_type: str,
    personal_data: bool,
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    supplied_ids = set(case.get("policy_document_ids", []))
    result = []
    for policy in policies:
        if policy.get("document_id") not in supplied_ids or policy.get("status") != "active":
            continue
        for clause in policy.get("clauses", []):
            control = clause.get("control", {})
            if control.get("type") != control_type:
                continue
            if control.get("applies_when", {}).get("processes_personal_data") and not personal_data:
                continue
            result.append((policy, clause))
    return result


def _make_finding(
    case_id: str,
    index: int,
    issue_type: str,
    severity: str,
    action: str,
    rationale: str,
    contract_clauses: list[dict[str, Any]],
    policy_clauses: list[tuple[dict[str, Any], dict[str, Any]]],
) -> dict[str, Any]:
    if issue_type in {
        "liability_cap_below_policy_minimum", "payment_terms_exceed_policy",
        "renewal_term_exceeds_policy", "renewal_opt_out_notice_too_short",
        "incident_notice_exceeds_policy", "policy_source_conflict",
    }:
        evidence_status = "confirmed_conflict"
    elif issue_type in {"required_data_addendum_not_found", "liability_cap_missing"}:
        evidence_status = "missing_from_supplied_text"
    else:
        evidence_status = "requirement_not_established"
    return {
        "finding_id": f"{case_id}-R{index:02d}",
        "issue_type": issue_type,
        "evidence_status": evidence_status,
        "severity": severity,
        "action": action,
        "rationale": rationale,
        "contract_clause_ids": [clause["clause_id"] for clause in contract_clauses],
        "policy_clause_ids": [clause["clause_id"] for _, clause in policy_clauses],
        "contract_evidence": [
            {"clause_id": clause["clause_id"], "text": clause["text"]}
            for clause in contract_clauses
        ],
        "policy_evidence": [
            {
                "document_id": policy["document_id"],
                "document_title": policy["title"],
                "clause_id": clause["clause_id"],
                "text": clause["text"],
            }
            for policy, clause in policy_clauses
        ],
    }


def review_case(case_id: str, bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    """Review one fictional case against its supplied structured policy rules."""
    bundle = bundle or load_demo_bundle()
    policies = bundle["policies"]
    case = next(
        (item for item in bundle["cases_document"]["cases"] if item.get("case_id") == case_id),
        None,
    )
    if case is None:
        raise ReviewCaseNotFound(case_id)

    findings: list[dict[str, Any]] = []

    def add(
        issue_type: str,
        severity: str,
        action: str,
        rationale: str,
        contract_clauses: list[dict[str, Any]],
        policy_clauses: list[tuple[dict[str, Any], dict[str, Any]]],
    ) -> None:
        findings.append(
            _make_finding(
                case_id, len(findings) + 1, issue_type, severity, action,
                rationale, contract_clauses, policy_clauses,
            )
        )

    contract_clauses = case["contract"]["clauses"]
    full_text = " ".join(clause.get("text", "") for clause in contract_clauses).lower()
    personal_data = "personal data" in full_text and "process" in full_text

    # Payment: compare each applicable policy rule's result. If the same term
    # is allowed by one policy and rejected by another, expose the conflict.
    payment_rules = _policy_rules(case, policies, "payment_terms", personal_data)
    for contract_clause in _topic_clauses(case, "payment"):
        days = _payment_days(contract_clause["text"])
        if days is None:
            continue
        outcomes = []
        for policy, clause in payment_rules:
            control = clause["control"]
            if days <= control["maximum_days"]:
                outcome = "within_limit"
            elif control.get("exception") and days <= control["exception"]["maximum_days"]:
                outcome = "exception"
            else:
                outcome = "exceeds_limit"
            outcomes.append((policy, clause, outcome))
        distinct = {outcome for _, _, outcome in outcomes}
        if len(distinct) > 1:
            evidence_contract = [contract_clause]
            if personal_data:
                evidence_contract += _topic_clauses(case, "personal data")
            add(
                "policy_source_conflict", "high", "escalate",
                "The supplied active policies lead to different outcomes for this payment term. Show both sources and ask a policy owner to resolve which rule controls.",
                evidence_contract, [(policy, clause) for policy, clause, _ in outcomes],
            )
        elif distinct == {"exception"}:
            policy, clause, _ = outcomes[0]
            approval = clause["control"]["exception"]["approval_required"]
            add(
                "payment_terms_above_preferred", "medium", "negotiate",
                f"Payment is due after {days} days. Policy permits this exception only with written {approval} approval; otherwise negotiate to the standard limit.",
                [contract_clause], [(policy, clause)],
            )
        elif distinct == {"exceeds_limit"}:
            add(
                "payment_terms_exceed_policy", "high", "escalate",
                f"Payment is due after {days} days, beyond the maximum permitted by the applicable policy.",
                [contract_clause], [(policy, clause) for policy, clause, _ in outcomes],
            )

    # Liability cap: the period in the contract must meet the policy minimum.
    liability_rules = _policy_rules(case, policies, "liability_cap_months", personal_data)
    for policy, policy_clause in liability_rules:
        minimum = policy_clause["control"]["minimum_months"]
        liability_clauses = _topic_clauses(case, "liability")
        if not liability_clauses:
            add(
                "liability_cap_missing", policy_clause["severity"], "escalate",
                "No supplier liability cap was found in the supplied contract clauses.",
                [], [(policy, policy_clause)],
            )
        for contract_clause in liability_clauses:
            matches = re.findall(r"\b([a-z]+|\d+)\s+months?\b", contract_clause["text"], re.IGNORECASE)
            months = _number(matches[0]) if matches else None
            if months is None:
                add(
                    "liability_period_ambiguous", policy_clause["severity"], "escalate",
                    "The liability period is not a clear number of months; ask a human reviewer to verify it.",
                    [contract_clause], [(policy, policy_clause)],
                )
            elif months < minimum:
                add(
                    "liability_cap_below_policy_minimum", "critical", "escalate",
                    f"The contract uses a {months}-month liability period; policy requires at least {minimum} months.",
                    [contract_clause], [(policy, policy_clause)],
                )

    # DPA: detect when personal-data processing is present but the required
    # addendum is absent from the clauses that were supplied for this case.
    dpa_rules = _policy_rules(case, policies, "dpa_required_if_personal_data", personal_data)
    if dpa_rules and not any("data processing addendum" in c["text"].lower() for c in contract_clauses):
        data_clauses = _topic_clauses(case, "personal data")
        if data_clauses:
            add(
                "required_data_addendum_not_found", "high", "escalate",
                "The contract says personal data will be processed, but no Data Processing Addendum appears in the supplied clauses.",
                data_clauses, dpa_rules,
            )

    # Incident notice: never translate vague words such as 'promptly' into a
    # numeric deadline that is not present in the contract.
    incident_rules = _policy_rules(case, policies, "incident_notice_hours", personal_data)
    if incident_rules:
        policy, policy_clause = incident_rules[0]
        maximum = policy_clause["control"]["maximum_hours"]
        incident_clauses = {
            clause["clause_id"]: clause
            for keyword in ("incident", "security")
            for clause in _topic_clauses(case, keyword)
        }
        for contract_clause in incident_clauses.values():
            match = re.search(r"within\s+(\d+)\s+hours?", contract_clause["text"], re.IGNORECASE)
            if not match:
                add(
                    "incident_notice_deadline_ambiguous", "high", "escalate",
                    f"The incident-notice clause has no measurable deadline. Do not assume that 'promptly' means within {maximum} hours.",
                    [contract_clause], [(policy, policy_clause)],
                )
            elif int(match.group(1)) > maximum:
                add(
                    "incident_notice_exceeds_policy", "high", "escalate",
                    f"The contract allows notice after {match.group(1)} hours; policy requires notice within {maximum} hours.",
                    [contract_clause], [(policy, policy_clause)],
                )

    # Renewal limits are applied when the contract supplies a renewal clause.
    renewal_rules = _policy_rules(case, policies, "renewal_terms", personal_data)
    renewal_clauses = _topic_clauses(case, "renewal")
    for policy, policy_clause in renewal_rules:
        control = policy_clause["control"]
        for contract_clause in renewal_clauses:
            terms = re.findall(r"\b([a-z]+|\d+)\s+months?\b", contract_clause["text"], re.IGNORECASE)
            term_lengths = [_number(value) for value in terms]
            if any(value is not None and value > control["maximum_term_months"] for value in term_lengths):
                add(
                    "renewal_term_exceeds_policy", "high", "escalate",
                    f"A renewal term exceeds the policy maximum of {control['maximum_term_months']} months.",
                    [contract_clause], [(policy, policy_clause)],
                )
            notice_days = re.findall(r"\b(\d+)\s+days?\b", contract_clause["text"], re.IGNORECASE)
            if "notice" in contract_clause["text"].lower() and notice_days and min(map(int, notice_days)) < control["minimum_opt_out_notice_days"]:
                add(
                    "renewal_opt_out_notice_too_short", "high", "escalate",
                    f"The opt-out notice is shorter than the policy minimum of {control['minimum_opt_out_notice_days']} days.",
                    [contract_clause], [(policy, policy_clause)],
                )

    if any(item["action"] == "escalate" for item in findings):
        disposition = "escalate"
    elif any(item["action"] == "negotiate" for item in findings):
        disposition = "negotiate"
    else:
        disposition = "approve"
    return {
        "case_id": case_id,
        "supplier": case["contract"].get("supplier", "Unknown supplier"),
        "disposition": disposition,
        "requires_escalation": disposition == "escalate",
        "human_final_decision_required": True,
        "review_mode": "deterministic_policy_baseline",
        "findings": findings,
        "rationale": (
            "No issue was found in the supplied clauses against the applicable structured policy controls."
            if not findings else
            f"{len(findings)} policy finding(s) were generated. A human must make the final procurement decision."
        ),
    }
