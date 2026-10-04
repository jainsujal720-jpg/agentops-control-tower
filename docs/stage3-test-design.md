# Stage 3 — Fictional data and evaluation cases

## Why this stage comes before the agent

The agent needs a defined set of inputs and expected behaviors. Otherwise, we would be tempted to judge it by whether its answers sound convincing. These cases make it possible to check whether it finds the right issue, cites the right source, and escalates when the evidence does not support a confident decision.

## Data files

- `data/policies/standard-procurement-v1.json`: fictional baseline policy for payment, liability, data processing, incident notice, and renewal terms.
- `data/policies/finance-data-vendor-addendum-v2.json`: a second active policy source that intentionally conflicts with the baseline on data-vendor payment terms and does not define precedence.
- `data/evaluation_cases.json`: seven fictional supplier contracts with human-authored expected dispositions and evidence references. C07 was added later in Stage 7 to cover the three evidence-status categories.

## Scenario matrix

| Case | Skill being tested | Expected disposition | Escalation |
|---|---|---|---|
| C01 | Avoid inventing issues when terms comply | Approve | No |
| C02 | Distinguish an allowed exception from a mandatory violation | Negotiate | No |
| C03 | Detect a numeric liability cap below policy minimum | Escalate | Yes |
| C04 | Report an absent required addendum without inventing contract text | Escalate | Yes |
| C05 | Surface two active, conflicting policy sources without choosing precedence | Escalate | Yes |
| C06 | Avoid treating "promptly" as a known 72-hour deadline | Escalate | Yes |

## Evidence and label rules

1. Every expected finding references at least one contract clause and one policy clause.
2. Cited policy clauses must belong to a policy document supplied with that case.
3. A missing-clause finding cites the contract clause that makes the requirement applicable and the policy clause requiring the missing item; it does not pretend the absent clause exists.
4. `escalate` labels must set `requires_escalation` to true. `approve` labels cannot carry expected findings. Non-approval labels must explain at least one finding.
5. The agent recommends; a human makes every final procurement decision.

The validator catches broken IDs and inconsistent labels before any model is involved. It does not determine whether a policy is legally correct; the fictional labels were intentionally authored for this prototype.

## Local checks

These Stage 3 checks use only the Python standard library, so they can run even in an environment without FastAPI, PostgreSQL, Docker, or network access:

```bash
python3 scripts/check_demo_data.py
python3 -m unittest discover -s tests -p 'test_stage3_data.py' -v
```

The existing Stage 2 API endpoint tests are separate and need the project's development dependencies. Stage 3 does not call a model API or send data anywhere.
