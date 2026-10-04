# Stage 6 — AI review through RelayGuard / Gateway LLM

## What it adds

Stage 6 adds `POST /reviews/ai`, an explicitly requested model review that routes through the separately running RelayGuard (Gateway LLM) service. The existing `POST /reviews` continues to run the deterministic Stage 4 baseline without contacting a model.

AgentOps identifies the work as a `complex` task and sends one requested fictional contract case plus only the policy documents listed for that case. It does not send expected labels or the other cases. RelayGuard owns model selection, provider credentials, fallback, budget and rate policies. AgentOps records the Gateway's `served_model`, `fallback_used`, routing details, and usage metadata in the AI review response when RelayGuard returns them.

## Structured result and evidence checks

The request includes a JSON Schema for a summary and findings. Each finding must include an evidence status (`confirmed_conflict`, `missing_from_supplied_text`, or `requirement_not_established`), contract/policy clause IDs, severity, action, and rationale. Stage 7 adds prompt rules and document-completeness metadata to support these distinctions. The schema helps keep the response predictable; it does not establish that a claim or citation is correct.

AgentOps validates each returned ID against the clauses supplied for that case. It rejects unsupported or missing citations and attaches exact source text from its own local data. It derives the overall disposition from the validated finding actions and always sets `human_final_decision_required` to true.

## Configuration

Copy `.env.example` to `.env`. Configure `RELAYGUARD_BASE_URL`, the Gateway API key if required by the Gateway, and the tenant and user identity already configured for the Gateway. Do not paste secrets into chat or commit `.env`.

With Docker Desktop on macOS, the default `http://host.docker.internal:8100` lets the AgentOps container reach a Gateway service listening on the Mac's port 8100. If both projects are in a shared Docker network, use the Gateway service name and internal port instead. The Gateway must be running and reachable before requesting an AI review.

`AGENTOPS_TASK_CLASS=complex` asks RelayGuard to apply its configured policy for complex work. RelayGuard, not AgentOps, selects the primary GPT and its fallback GPT. Use RelayGuard's own configuration/dashboard to select those models and review its limits. `RELAYGUARD_API_KEY` is optional only when the local Gateway accepts requests without a key. Never put the OpenAI provider key in AgentOps; keep provider credentials inside RelayGuard.

## Requesting one AI review

After starting both projects and rebuilding AgentOps with this Stage 6 code, request one fictional case explicitly:

```bash
curl -i -X POST http://localhost:8201/reviews/ai \
  -H 'Content-Type: application/json' \
  -d '{"case_id":"C03"}'
```

This route may create a billable model request according to the model configured in RelayGuard. AgentOps' offline tests, data validator, deterministic `/reviews` endpoint, and health checks make no model request.

## Failure handling and limits

- Missing configuration or Gateway errors fail the AI request; AgentOps does not silently return the deterministic result as if it came from a model.
- If RelayGuard itself serves the request through a backup model, the returned `fallback_used` metadata is included in AgentOps' response.
- AgentOps does not make a second direct-provider attempt if RelayGuard is unavailable. This keeps routing, fallback, budget, and provider policy inside one Gateway boundary.
- Unsupported, duplicate, or missing evidence IDs fail validation rather than creating an ungrounded finding.
- Model recommendations are advisory. They do not approve contracts, negotiate with suppliers, or change procurement records.
- At Stage 6, this prototype used fictional, pre-structured clauses. Stage 7 adds heuristic document extraction; it still does not provide legal advice or establish production performance.
