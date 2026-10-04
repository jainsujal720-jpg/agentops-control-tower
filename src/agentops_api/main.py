"""HTTP entry point for the AgentOps Control Tower API."""

from typing import Any, Literal

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from agentops_api import database
from agentops_api.ai_review import AIReviewError, review_case_with_model, review_contract_with_model
from agentops_api.demo_data import load_demo_bundle
from agentops_api.document_review import DocumentInputError, extract_text, review_uploaded_deterministic
from agentops_api.review_engine import ReviewCaseNotFound, review_case


class ReviewRequest(BaseModel):
    case_id: str = Field(
        pattern=r"^C\d{2}$",
        description="One of the fictional evaluation case IDs, such as C03.",
    )


class ContractEvidence(BaseModel):
    clause_id: str
    text: str


class PolicyEvidence(BaseModel):
    document_id: str
    document_title: str
    clause_id: str
    text: str


class ReviewFinding(BaseModel):
    finding_id: str
    issue_type: str
    evidence_status: Literal["confirmed_conflict", "missing_from_supplied_text", "requirement_not_established"]
    severity: Literal["low", "medium", "high", "critical"]
    action: Literal["negotiate", "escalate"]
    rationale: str
    contract_clause_ids: list[str]
    policy_clause_ids: list[str]
    contract_evidence: list[ContractEvidence]
    policy_evidence: list[PolicyEvidence]


class ReviewResponse(BaseModel):
    case_id: str
    supplier: str
    disposition: Literal["approve", "negotiate", "escalate"]
    requires_escalation: bool
    human_final_decision_required: bool
    review_mode: str
    served_model: str | None = None
    fallback_used: bool = False
    gateway_routing: dict[str, Any] | None = None
    usage: dict[str, Any] | None = None
    findings: list[ReviewFinding]
    rationale: str


def create_app() -> FastAPI:
    """Create the API application."""
    application = FastAPI(
        title="AgentOps Control Tower API",
        description="Backend foundation for inspecting and evaluating AI agent workflows.",
        version="0.1.0",
    )

    @application.get("/", tags=["service"])
    def service_info() -> dict[str, str]:
        return {"service": "agentops-control-tower-api", "stage": "6-ai-review"}

    @application.get("/healthz", tags=["operations"])
    def liveness() -> dict[str, str]:
        """Report that the API process can respond; does not check dependencies."""
        return {"status": "ok"}

    @application.get("/readyz", tags=["operations"])
    def readiness() -> dict[str, str]:
        """Report whether the API can reach its required database."""
        if not database.can_connect():
            raise HTTPException(status_code=503, detail="database is not ready")
        return {"status": "ready", "database": "connected"}

    @application.get("/demo/cases", tags=["demo"])
    def list_demo_cases() -> list[dict[str, str]]:
        """List fictional case IDs and suppliers without exposing scenario labels."""
        cases = load_demo_bundle()["cases_document"]["cases"]
        return [
            {
                "case_id": case["case_id"],
                "supplier": case["contract"]["supplier"],
            }
            for case in cases
        ]

    @application.post("/reviews", response_model=ReviewResponse, tags=["reviews"])
    def create_review(request: ReviewRequest) -> dict:
        """Run the deterministic policy baseline on one fictional case."""
        try:
            return review_case(request.case_id)
        except ReviewCaseNotFound as exc:
            raise HTTPException(status_code=404, detail=f"unknown demo case: {request.case_id}") from exc

    @application.post("/reviews/ai", response_model=ReviewResponse, tags=["reviews"])
    def create_ai_review(request: ReviewRequest) -> dict:
        """Run an explicitly requested model review on a fictional case."""
        try:
            return review_case_with_model(request.case_id)
        except ReviewCaseNotFound as exc:
            raise HTTPException(status_code=404, detail=f"unknown demo case: {request.case_id}") from exc
        except AIReviewError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @application.post("/reviews/upload", tags=["reviews"])
    async def review_uploaded_document(
        file: UploadFile = File(...),
        policy_files: list[UploadFile] = File(default=[]),
        supplier: str = Form(default=""),
        mode: Literal["baseline", "ai"] = Form(default="baseline"),
        completeness: Literal["unknown", "complete", "excerpt"] = Form(default="unknown"),
    ) -> dict:
        """Extract a temporary text view and review it; uploaded bytes are not persisted."""
        content = await file.read(10 * 1024 * 1024 + 1)
        try:
            _text, clauses = extract_text(file.filename or "upload", content)
            custom_policies = []
            for index, policy_file in enumerate(policy_files, start=1):
                policy_bytes = await policy_file.read(10 * 1024 * 1024 + 1)
                _policy_text, policy_clauses = extract_text(policy_file.filename or f"policy-{index}.txt", policy_bytes)
                custom_policies.append({
                    "document_id": f"POL-UPLOAD-{index:02d}",
                    "title": policy_file.filename or f"Uploaded policy {index}",
                    "status": "active",
                    "clauses": [
                        {"clause_id": f"POL-UP-{index:02d}-{item['clause_id'].split('-')[-1]}", "text": item["text"], "control": {}}
                        for item in policy_clauses
                    ],
                })
            review_bundle = load_demo_bundle()
            if custom_policies:
                if mode == "baseline":
                    raise HTTPException(status_code=400, detail="Custom policy uploads require AI-assisted mode. The local rules baseline only supports the bundled fictional policies.")
                review_bundle["policies"] = custom_policies
            if mode == "ai":
                result = review_contract_with_model(supplier or file.filename or "Uploaded supplier", clauses, review_bundle, contract_completeness=completeness)
            else:
                result = review_uploaded_deterministic(supplier or file.filename or "Uploaded supplier", clauses, completeness, review_bundle)
            result["uploaded_filename"] = file.filename
            result["policy_documents_used"] = [policy["title"] for policy in (custom_policies or review_bundle["policies"])]
            result["extraction_notice"] = "Text was extracted and segmented heuristically. Verify extracted clauses against the original file; scanned PDF OCR is not supported."
            result["extracted_clauses"] = clauses
            return result
        except DocumentInputError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except AIReviewError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        finally:
            await file.close()
            for policy_file in policy_files:
                await policy_file.close()

    @application.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
    def dashboard() -> str:
        """Serve the small, self-contained local review dashboard."""
        return DASHBOARD_HTML

    return application


DASHBOARD_HTML = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AgentOps Procurement Review</title>
<style>
:root{font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#172235;background:#f4f7fb}*{box-sizing:border-box}body{margin:0}.wrap{max-width:1050px;margin:36px auto;padding:0 20px}.top{background:#10233f;color:white;border-radius:18px;padding:26px 30px}.top h1{margin:0 0 8px;font-size:27px}.top p{margin:0;color:#d1def1;line-height:1.5}.card{background:white;border:1px solid #dce4ef;border-radius:16px;padding:22px;margin-top:18px;box-shadow:0 5px 18px #1c35520a}.grid{display:grid;grid-template-columns:1fr 1fr;gap:15px}label{font-weight:650;font-size:14px;display:block;margin:10px 0 7px}input,select{font:inherit;width:100%;padding:11px;border:1px solid #cbd6e5;border-radius:9px;background:white}button{margin-top:18px;background:#1769e0;color:white;border:0;border-radius:9px;padding:12px 18px;font:inherit;font-weight:650;cursor:pointer}button:disabled{opacity:.6;cursor:wait}.note{background:#fff7df;border:1px solid #f2dc9a;color:#624d10;padding:13px 15px;border-radius:10px;line-height:1.5;font-size:14px;margin-top:14px}.subtle{color:#52647b;font-size:14px;line-height:1.5}.status{padding:6px 10px;border-radius:999px;font-size:12px;font-weight:700;display:inline-block}.confirmed_conflict{background:#fee2e2;color:#9c2525}.missing_from_supplied_text{background:#ffedd5;color:#91520a}.requirement_not_established{background:#e7eafe;color:#3d479b}.resulthead{display:flex;justify-content:space-between;align-items:center;gap:12px}.outcome{padding:7px 11px;border-radius:999px;font-weight:800;font-size:13px;background:#e7f6ec;color:#17633a}.outcome.escalate{background:#fee2e2;color:#9c2525}.outcome.negotiate{background:#fff1d6;color:#80500b}.counts{display:flex;gap:10px;flex-wrap:wrap;margin:16px 0}.count{border-radius:10px;padding:10px 14px;font-size:14px;font-weight:700;background:#eff3f8;color:#34445b}.count.critical,.count.high{background:#fee2e2;color:#9c2525}.count.medium{background:#fff1d6;color:#80500b}.count.low{background:#e7f6ec;color:#17633a}.finding{border:1px solid #e3e9f1;border-left:5px solid #9aa9ba;border-radius:11px;padding:17px;margin:14px 0;background:#fff}.finding.critical,.finding.high{border-left-color:#dc2626}.finding.medium{border-left-color:#e99a12}.finding.low{border-left-color:#26945b}.finding h3{margin:10px 0 6px}.severity{font-weight:800;text-transform:capitalize}.critical .severity,.high .severity{color:#b42318}.medium .severity{color:#9a5b00}.low .severity{color:#187545}.next{background:#f4f7fb;border-radius:8px;padding:11px 13px;margin:12px 0;line-height:1.5}.ev{background:#f7f9fc;border-left:3px solid #a9bbd3;padding:10px 12px;margin:8px 0;white-space:pre-wrap;line-height:1.5;font-size:13px}details{margin-top:12px}details summary{cursor:pointer;font-weight:650;color:#34445b}.meta{font-size:13px;color:#52647b}.hidden{display:none}.error{color:#a32222;font-weight:600}code{background:#f1f4f8;padding:2px 5px;border-radius:4px}@media(max-width:700px){.grid{grid-template-columns:1fr}.wrap{margin:18px auto}.top{padding:21px}}
</style></head><body><main class="wrap">
<header class="top"><h1>AgentOps · Procurement Review</h1><p>Inspect contract evidence, policy references, and how confident the review can be about each issue.</p></header>
<section class="card"><h2>Review a procurement document</h2><p class="subtle">Upload PDF, DOCX, or UTF-8 TXT. The file is processed in memory and not saved by this prototype. PDF must contain selectable text; scanned-image OCR is not included.</p>
<div class="grid"><div><label for="supplier">Supplier (optional)</label><input id="supplier" placeholder="Supplier name"></div><div><label for="mode">Review method</label><select id="mode"><option value="baseline">Rules baseline (local, no model call)</option><option value="ai">AI-assisted via RelayGuard (may incur model cost)</option></select></div><div><label for="completeness">What did you upload?</label><select id="completeness"><option value="unknown">Not sure / excerpt (recommended)</option><option value="complete">Complete contract</option><option value="excerpt">Known excerpt only</option></select></div></div>
<label for="file">Contract or procurement document</label><input id="file" type="file" accept=".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain">
<label for="policies">Company policy documents (optional)</label><input id="policies" type="file" multiple accept=".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain"><p class="subtle">If omitted, the demo compares against its bundled fictional policies. Upload your policies to use AI-assisted review. Custom policies are not supported by the local rules baseline.</p>
<div class="note"><b>Before choosing AI-assisted:</b> extracted contract text will be sent to the configured RelayGuard Gateway and selected model. Use fictional or approved data. The output is a review aid, not a legal decision. A human must verify the source document and make the final decision.</div>
<button id="run">Review document</button><span id="busy" class="subtle"></span><p id="error" class="error"></p></section>
<section id="results" class="card hidden"><div class="resulthead"><h2>Review at a glance</h2><span id="disposition" class="outcome"></span></div><p id="summary" class="subtle"></p><div id="counts" class="counts"></div><div class="note"><b>Important:</b> This is a review aid. Confirm each item against the original contract and policy; a human makes the final decision.</div><div id="findings"></div><details><summary>Technical details</summary><p id="modelsummary" class="subtle"></p><p id="metadata" class="meta"></p><details><summary>Inspect extracted sections</summary><p class="subtle">Extraction and section boundaries can be imperfect. Compare these with the source file.</p><div id="allclauses"></div></details></details></section>
</main><script>
const byId=id=>document.getElementById(id);const escText=(el,text)=>{el.textContent=text??""};
byId('run').addEventListener('click',async()=>{const file=byId('file').files[0];byId('error').textContent='';if(!file){byId('error').textContent='Choose a document first.';return}const fd=new FormData();fd.append('file',file);for(const policy of byId('policies').files)fd.append('policy_files',policy);fd.append('supplier',byId('supplier').value);fd.append('mode',byId('mode').value);fd.append('completeness',byId('completeness').value);byId('run').disabled=true;byId('busy').textContent='Extracting and reviewing…';byId('results').classList.add('hidden');try{const res=await fetch('/reviews/upload',{method:'POST',body:fd});const data=await res.json();if(!res.ok)throw new Error(data.detail||'Review failed');const disposition=byId('disposition');escText(disposition,data.disposition.toUpperCase()+' · HUMAN DECISION REQUIRED');disposition.className='outcome '+data.disposition;escText(byId('modelsummary'),data.rationale);const meta=[`Method: ${data.review_mode}`,`Supplier: ${data.supplier}`,`Text sections: ${data.source_clause_count}`,`Document completeness: ${data.document_completeness}`,`Policies: ${(data.policy_documents_used||[]).join(', ')}`,`Model: ${data.served_model||'not used'}`,`Fallback: ${data.fallback_used?'yes':'no'}`,data.usage?.token_cost_usd!=null?`Estimated model cost: $${data.usage.token_cost_usd}`:null].filter(Boolean).join(' · ');escText(byId('metadata'),meta);const all=byId('allclauses');all.replaceChildren();for(const c of data.extracted_clauses||[]){const d=document.createElement('div');d.className='ev';d.textContent=`${c.clause_id} · ${c.topic}\n${c.text}`;all.append(d)}const host=byId('findings');host.replaceChildren();const counts=byId('counts');counts.replaceChildren();const findings=data.findings||[];escText(byId('summary'),findings.length?`Found ${findings.length} item${findings.length===1?'':'s'} to review. Start with the highest-priority item${findings.length===1?'':'s'} below.`:'No issues were identified in the supplied text. Human review is still required.');for(const level of ['critical','high','medium','low']){const n=findings.filter(f=>f.severity===level).length;if(n){const chip=document.createElement('span');chip.className='count '+level;chip.textContent=`${n} ${level}`;counts.append(chip)}}if(!findings.length){const chip=document.createElement('span');chip.className='count low';chip.textContent='No findings identified';counts.append(chip);const p=document.createElement('p');p.textContent='No issue was identified in the supplied text. This does not by itself prove the contract is compliant.';host.append(p)}const priority={critical:0,high:1,medium:2,low:3};for(const f of [...findings].sort((a,b)=>(priority[a.severity]??2)-(priority[b.severity]??2))){const level=['critical','high','medium','low'].includes(f.severity)?f.severity:'medium';const article=document.createElement('article');article.className='finding '+level;const badge=document.createElement('span');badge.className='status '+f.evidence_status;badge.textContent=({confirmed_conflict:'Confirmed conflict',missing_from_supplied_text:'Not found in supplied text',requirement_not_established:'Needs confirmation'})[f.evidence_status]||f.evidence_status;const h=document.createElement('h3');h.textContent=f.issue_type;const sev=document.createElement('span');sev.className='severity';sev.textContent=level+' priority';h.append(document.createTextNode(' · '),sev);const p=document.createElement('p');p.textContent=f.evidence_status==='confirmed_conflict'?'The contract term conflicts with a stated policy requirement.':f.evidence_status==='missing_from_supplied_text'?'This required item was not found in the supplied documents; it may be in a separate schedule.':'The supplied documents do not establish whether this requirement is met.';const reason=document.createElement('details');const reasonLabel=document.createElement('summary');reasonLabel.textContent='Why was this flagged?';const rationale=document.createElement('p');rationale.textContent=f.rationale;reason.append(reasonLabel,rationale);const next=document.createElement('div');next.className='next';const issue=(f.issue_type||'').toLowerCase();let advice;if(issue.includes('liability')&&f.evidence_status==='confirmed_conflict'){advice='Ask the supplier to raise the cap to the policy minimum, or obtain a documented exception approved by the authorized owner.'}else if(issue.includes('data processing')||issue.includes('dpa')){advice='Request the referenced Data Processing Addendum and confirm it is signed before the supplier accesses personal data.'}else if(issue.includes('incident')){advice='Ask Security to confirm an exact notification deadline that meets policy before approval.'}else if(f.evidence_status==='confirmed_conflict'){advice='Ask Procurement and the policy owner to resolve the conflict before approval.'}else if(f.evidence_status==='missing_from_supplied_text'){advice='Request the referenced clause or schedule and confirm whether it is part of the contract packet.'}else{advice='Ask the named business, Legal, Security, or Privacy owner to confirm this requirement before access or approval.'}next.textContent='Next step: '+advice;const evidence=document.createElement('details');const summary=document.createElement('summary');summary.textContent='Show contract and policy evidence';evidence.append(summary);for(const e of [...(f.contract_evidence||[]).map(x=>['Contract',x.clause_id,x.text]),...(f.policy_evidence||[]).map(x=>['Policy',x.clause_id,x.text])]){const div=document.createElement('div');div.className='ev';div.textContent=`${e[0]} · ${e[1]}\n${e[2]}`;evidence.append(div)}article.append(badge,h,p,next,reason,evidence);host.append(article)}byId('results').classList.remove('hidden')}catch(e){byId('error').textContent=e.message}finally{byId('run').disabled=false;byId('busy').textContent=''}});
</script></body></html>'''


app = create_app()
