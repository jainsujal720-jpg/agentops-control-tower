"""Temporary document extraction and review helpers for the local prototype."""

from __future__ import annotations

import re
from pathlib import PurePath
from typing import Any

from agentops_api.demo_data import load_demo_bundle
from agentops_api.review_engine import review_case

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_EXTRACTED_CHARACTERS = 120_000
MAX_CLAUSES = 300


class DocumentInputError(ValueError):
    """Raised for unsupported, unreadable, or oversized procurement documents."""


def extract_text(filename: str, content: bytes) -> tuple[str, str]:
    if len(content) > MAX_UPLOAD_BYTES:
        raise DocumentInputError("File exceeds the 10 MB prototype limit.")
    suffix = PurePath(filename).suffix.lower()
    try:
        if suffix == ".txt":
            text = content.decode("utf-8-sig")
        elif suffix == ".pdf":
            from pypdf import PdfReader
            import io
            reader = PdfReader(io.BytesIO(content))
            text = "\n\n".join(page.extract_text() or "" for page in reader.pages)
            if not text.strip():
                raise DocumentInputError("No selectable text found in the PDF. Scanned PDFs need OCR, which this prototype does not include.")
        elif suffix == ".docx":
            import io
            from docx import Document
            from docx.table import Table
            from docx.text.paragraph import Paragraph

            document = Document(io.BytesIO(content))
            # Walk body blocks in document order. `document.paragraphs` alone
            # silently skips Word tables, where procurement policies often put
            # their actual thresholds and required controls.
            blocks: list[str] = []
            for block in document.iter_inner_content():
                if isinstance(block, Paragraph):
                    value = block.text.strip()
                    if value:
                        blocks.append(value)
                elif isinstance(block, Table):
                    for row in block.rows:
                        cells = [re.sub(r"\s+", " ", cell.text).strip() for cell in row.cells]
                        cells = [value for value in cells if value]
                        if cells:
                            blocks.append(" | ".join(cells))
            text = "\n\n".join(blocks)
        else:
            raise DocumentInputError("Unsupported file type. Upload a PDF, DOCX, or UTF-8 TXT file.")
    except DocumentInputError:
        raise
    except Exception as exc:
        raise DocumentInputError("The document could not be read. Check that it is a valid, unencrypted PDF, DOCX, or UTF-8 TXT file.") from exc
    text = text.replace("\x00", " ").strip()
    if not text:
        raise DocumentInputError("The uploaded document contains no extractable text.")
    if len(text) > MAX_EXTRACTED_CHARACTERS:
        raise DocumentInputError("Extracted text exceeds the 120,000-character review limit. Split the document into smaller parts.")
    # Retain paragraph and numbered-section boundaries where possible. This is
    # intentionally transparent/simple; it is not a legal-grade clause parser.
    parts = [re.sub(r"\s+", " ", part).strip() for part in re.split(r"\n\s*\n|(?=\n\s*(?:\d+(?:\.\d+)*[.)]?|[A-Z]{1,4}-\d+)\s+)", text)]
    parts = [part for part in parts if len(part) >= 20]
    if not parts:
        parts = [re.sub(r"\s+", " ", text)]
    if len(parts) > MAX_CLAUSES:
        raise DocumentInputError(f"Document produced more than {MAX_CLAUSES} text sections. Split the file and review in smaller parts.")
    clauses = []
    for index, part in enumerate(parts, start=1):
        low = part.lower()
        if any(word in low for word in ("liability", "liable", "damages")):
            topic = "Liability cap"
        elif any(word in low for word in ("payment", "invoice", "net ")):
            topic = "Payment terms"
        elif any(word in low for word in ("personal data", "personal information", "process data")):
            topic = "Personal data processing"
        elif any(word in low for word in ("data processing addendum", "dpa")):
            topic = "Data Processing Addendum"
        elif any(word in low for word in ("incident", "security breach", "security event")):
            topic = "Security incident notice"
        elif any(word in low for word in ("renew", "renewal", "term")):
            topic = "Renewal"
        else:
            topic = "Other contract term"
        clauses.append({"clause_id": f"UP-{index:03d}", "topic": topic, "text": part})
    return text, clauses


def review_uploaded_deterministic(
    supplier: str, clauses: list[dict[str, str]], completeness: str = "unknown",
    bundle: dict[str, Any] | None = None,
) -> dict[str, Any]:
    bundle = bundle or load_demo_bundle()
    case = {
        "case_id": "UPLOAD",
        "contract": {"supplier": supplier or "Uploaded supplier", "clauses": clauses, "completeness": completeness},
        "policy_document_ids": [policy["document_id"] for policy in bundle["policies"] if policy.get("status") == "active"],
    }
    bundle["cases_document"] = {"cases": [case]}
    result = review_case("UPLOAD", bundle)
    result["source_clause_count"] = len(clauses)
    result["document_completeness"] = completeness
    result["rationale"] += " The uploaded text was segmented heuristically; verify section boundaries and document completeness."
    return result
