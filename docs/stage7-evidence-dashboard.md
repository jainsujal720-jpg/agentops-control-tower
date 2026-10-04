# Stage 7: evidence clarity and document review dashboard

## Product goal

Help a procurement reviewer see what a review actually establishes, what is absent from the supplied text, and what remains uncertain. The interface is a review aid; it does not approve a supplier or replace legal/procurement judgment.

## Evidence-status definitions

| API value | Meaning | Example |
|---|---|---|
| `confirmed_conflict` | Supplied contract/policy evidence directly demonstrates a contradiction or policy-source conflict. | A six-month liability cap against a 12-month policy minimum. |
| `missing_from_supplied_text` | A requirement applies based on supplied facts, but the required clause/document was not found in the reviewed text. It does not prove absence from a complete agreement unless the source is known complete. | Personal-data processing is explicit, but the DPA is not in the submitted excerpt. |
| `requirement_not_established` | The available text does not establish applicability or compliance, or its wording is not measurable. Do not describe it as a proven violation. | “Promptly” does not define whether security notice occurs within 72 hours. |

Every AI finding must include one of the enum values. The API rejects unsupported values and IDs that do not resolve to supplied source clauses. Source text is attached by the server from its input copy, not trusted from model-generated quotations.

## C03 and C07

C03 remains the focused liability-conflict case: its labeled expectation is one confirmed liability conflict. The tightened AI prompt tells the model not to create a finding for every policy topic omitted from an incomplete or unknown-scope excerpt. This is a prompt-level guard, not a guarantee; AI model output still requires review and evaluation.

C07 is a newly added fictional excerpt. It deliberately covers all three statuses:

1. Six-month liability cap: `confirmed_conflict`.
2. Explicit personal-data processing, with no DPA in the excerpt: `missing_from_supplied_text`.
3. Incident notice only “promptly”: `requirement_not_established`.

The deterministic reviewer is evaluated against the human-authored labels with expected labels removed from its input. The offline report measures the rule baseline, not the hosted AI model.

## Dashboard and upload flow

1. Open `/dashboard` on the AgentOps API host.
2. Select a `.pdf`, `.docx`, or UTF-8 `.txt` contract file (maximum 10 MB) and optionally enter the supplier.
3. Optionally select one or more policy documents in the same supported formats. If omitted, the demo uses its bundled fictional policies.
4. Mark completeness as unknown, complete, or excerpt. Default is unknown.
5. Choose local rules baseline or AI-assisted Gateway review. Custom policy files require AI mode; deterministic evaluation only has structured rules for the bundled demo policies.
6. Inspect the disposition, evidence-status badges, exact cited contract/policy passages, extracted sections, model/fallback metadata, and estimated usage when available.

The upload is read into memory, extracted, segmented heuristically, reviewed, and then discarded by this service. There is no upload persistence or review history. PDF extraction requires selectable text; scanned PDF OCR, tables, signature verification, and robust legal clause segmentation are not implemented. Review every extracted section against the original document.

In AI mode, extracted text is sent to the configured RelayGuard/Gateway and selected model. The dashboard warns about this before the request; users must only send data they are allowed to share. Baseline mode makes no model call. The demo API is local and has no user authentication, so it must not be exposed to the public internet.

## Endpoint

`POST /reviews/upload` accepts multipart fields:

- `file`: PDF, DOCX, or TXT contract file.
- `policy_files`: optional repeated PDF, DOCX, or TXT policy files. If present, they replace the bundled demo policies for this review and require `mode=ai`.
- `supplier`: optional display name.
- `mode`: `baseline` or `ai` (default `baseline`).
- `completeness`: `unknown`, `complete`, or `excerpt` (default `unknown`).

The response includes findings and evidence, metadata, `source_clause_count`, `document_completeness`, and `extracted_clauses` for inspection. The service does not return the original uploaded bytes.

## Evaluation and known gaps

The seven-case set is fictional. It is a software regression suite, not evidence of real-world accuracy, legal compliance, fairness, or safe production behavior. No real procurement agreement/policy pair was supplied in this project workspace. Real-world validation needs authorized and redacted contract-policy pairs, expert-reviewed labels, version tracking, and a separate AI model evaluation that checks both finding correctness and evidence-status correctness.

Before production: add auth and tenant isolation, explicit data-retention controls, malware scanning, OCR with confidence reporting, layout-aware extraction, policy selection/versioning, durable audit records, upload rate/size controls at the edge, human disposition capture, model evaluations, and security/privacy review.

## Verification

From the project root:

```bash
python3 scripts/check_demo_data.py
python3 scripts/evaluate_baseline.py
python3 -m unittest discover -s tests -v
```

The API/dashboard tests cover the upload endpoint using a small text fixture. Docker startup additionally verifies multipart and document-reader dependencies are installed from `pyproject.toml`.

## Readable results view update

The dashboard presents a short review summary, severity counts, and findings ordered from critical to low priority. Critical and high findings use red accents, medium findings use amber, and low findings use green. Each finding contains a plain-language next step, while contract and policy citations are collapsed under “Show contract and policy evidence.” Model routing, cost, the model's original summary, and extracted sections are grouped under “Technical details.” These visual priorities are for navigation; they do not replace human judgment or change the review result.

## Review readability and training metadata update

The dashboard now sorts findings from highest to lowest priority, shows concise plain-language meaning and next steps, and keeps the longer model rationale and source evidence collapsed until requested. Model routing, cost, and extracted sections remain under Technical details. Explicit synthetic-training labels are retained in the extraction inspector but excluded from AI contract comparison. The prompt also distinguishes buyer-side approval records from supplier contract promises and asks for separate findings for distinct controls. These changes improve presentation and reduce known demo-data false positives; they do not establish legal accuracy.

## DOCX table extraction fix

DOCX extraction now walks paragraphs and tables in their original body order and includes each table row as plain text. This matters because procurement policies commonly place their thresholds and mandatory controls in tables. The sample supplier agreement's six-month liability cap and the policy's 12-month minimum and 24-hour incident threshold were verified in extracted text. PDF table extraction remains dependent on the text layout exposed by the PDF parser and should be checked in the extracted-text inspector.
