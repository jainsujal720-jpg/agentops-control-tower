# Stage 5 — Baseline evaluation

## Purpose

Stage 4 created a deterministic reviewer. Stage 5 measures its behavior against the seven human-authored labels in the fictional benchmark. The labels are used only by this offline evaluation runner; the reviewer receives a copy of each case with its `expected` field removed.

## Run it

From the project root:

```bash
python3 scripts/evaluate_baseline.py
```

The script first validates the demo data, then prints a JSON report. It makes no network or model-provider calls and does not write to PostgreSQL.

## Metrics

| Metric | Meaning |
|---|---|
| Disposition accuracy | Share of cases where approve / negotiate / escalate matches the expected label |
| Escalation precision | Of cases the baseline escalates, share expected to escalate |
| Escalation recall | Of cases expected to escalate, share the baseline catches |
| Finding-type micro precision / recall / F1 | Agreement on the issue types detected per case, counting findings across the benchmark |
| Evidence-status micro precision / recall / F1 | Agreement on `confirmed_conflict`, `missing_from_supplied_text`, and `requirement_not_established` categories per case |
| Citation validity | Share of returned evidence citations whose IDs resolve to the exact source text supplied to the reviewer |
| Human review gate | Confirms every result still requires a human final decision |

## Baseline result and interpretation

The current seven-case fictional benchmark is expected to produce 100% disposition accuracy, 100% escalation precision and recall, 100% finding-type F1, 100% evidence-status F1, 100% citation validity, and a passed human-review gate. These results verify that the deterministic implementation matches its authored test cases. They are not a claim of production accuracy, broad language coverage, AI model quality, or legal compliance.

The AI-assisted path requires a separate evaluation against independently labeled cases; this report does not evaluate its output. Add independently authored and real-world approved/redacted cases before treating any score as evidence of broader performance. Future product-level measures such as review time saved, reviewer override rate, cost per review, and service latency need representative users; they cannot be inferred from these offline cases.
