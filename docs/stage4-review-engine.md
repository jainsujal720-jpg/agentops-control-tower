# Stage 4 — Contract review engine

## What this stage builds

The review engine compares structured contract clauses with machine-readable controls attached to supplied policy clauses. It returns a recommendation and findings with exact contract and policy evidence. The API exposes the fictional cases for a demo and accepts a case ID to run a review.

## Why policy controls are structured

Policy prose is preserved because a reviewer needs to read the source. The numeric or conditional requirement used by the baseline is separately stored as a small JSON control, such as minimum_months: 12 or maximum_hours: 72. That makes the first pass predictable and testable. The control is an explicit encoding of our fictional policy; it is not legal interpretation by an LLM.

## API endpoints

| Method and route | Input | Purpose |
|---|---|---|
| GET /demo/cases | None | Lists case IDs and fictional suppliers without revealing scenario or expected labels |
| POST /reviews | {"case_id":"C03"} | Runs the policy baseline on one fictional case |

POST /reviews returns:

- the recommendation: approve, negotiate, or escalate;
- whether escalation is required;
- an explicit human_final_decision_required: true;
- issue type, severity, action, and rationale for each finding;
- contract and policy clause IDs plus the exact source text for each citation.

The API validates the request shape with a typed request model. An unknown case ID returns HTTP 404. The OpenAPI page at /docs documents the request and response schemas for people and API clients.

## Decision flow

1. Load the requested fictional contract and only the policy documents listed for that case.
2. Apply only controls marked active and whose stated conditions apply.
3. Compare payment rule results. If supplied active policies disagree for this contract, report a policy-source conflict and escalate.
4. Check the liability period, whether a required data addendum is present, incident-notice deadline, and renewal limits.
5. Attach citations by copying the exact source clause IDs and text from the inputs.
6. If any finding requires escalation, return escalate; otherwise return negotiate when an allowed exception needs approval; return approve only when no issue was found.
7. Require a human to make the final procurement decision in every case.

The expected labels live alongside the test data for evaluation, but review_case() never reads them. Tests run the engine with those labels removed as a leakage check.

## Known limits

- The engine reviews supplied clause text; it does not read PDFs, OCR scans, or identify clauses in a complete contract.
- It recognizes the structured fictional controls used by this test set. This is not a universal contract interpreter.
- The system does not call an LLM in this stage. A model adapter may later help extract clauses or handle language outside these rules, but it must be evaluated against this baseline and keep evidence and human-review safeguards.
- These fictional policies are not legal advice or evidence of real procurement compliance.

## Local tests

Run:

    python3 scripts/check_demo_data.py
    python3 -m unittest discover -s tests -p 'test_stage*.py' -v

The current regression suite checks all seven labeled outcomes, verifies exact evidence references and evidence-status categories, confirms that the engine can run without expected labels, tests the conflicting-policy and ambiguous-language safeguards, and covers stronger liability and incident-deadline examples. C07 was added in Stage 7 to exercise all three evidence categories.
