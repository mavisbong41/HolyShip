"""Audit every public-bundle attachment through the Phase-2 materialization path."""
from __future__ import annotations

import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.documents.materialization import PreExtractionOutcome
from backend.app.documents.models import DocumentFormat, DocumentType
from backend.app.documents.readers.composite import CompositeDocumentReader
from backend.app.documents.role_validation import DocumentRoleValidator, RoleValidationOutcome
from backend.app.classification.adapters import email_message_to_classification_input
from backend.app.classification.pipeline import classify_email
from backend.app.ingestion.sources import StaticBundleSource


BUNDLE = ROOT / "data" / "bundle"
REPORT = ROOT / "reports" / "attachment_inventory.md"


@dataclass(frozen=True)
class InventoryRow:
    email_id: str
    filename: str
    format: str
    reader: str
    readable: bool
    text_chars: int
    table_cells: int
    role: str
    validation: str
    outcome: str
    parse_ms: float
    evidence: str


@dataclass(frozen=True)
class EmailAuditRow:
    email_id: str
    category: str
    readiness: str
    attachment_count: int
    phase2_status: str
    reason_code: str


def assess(content: bytes, document, validator: DocumentRoleValidator):
    if document.format == DocumentFormat.UNKNOWN:
        return DocumentType.UNKNOWN, "INCONCLUSIVE", PreExtractionOutcome.UNSUPPORTED_ATTACHMENT.value, document.error_message or "unsupported format"
    if not content:
        return DocumentType.UNKNOWN, "INCONCLUSIVE", PreExtractionOutcome.CORRUPTED_ATTACHMENT.value, "empty attachment"
    if document.extraction_status == "FAILED":
        return DocumentType.UNKNOWN, "INCONCLUSIVE", PreExtractionOutcome.CORRUPTED_ATTACHMENT.value, document.error_message or "reader failed"
    if document.extraction_status in {"UNREADABLE", "PARTIAL"} and not document.raw_text.strip():
        return DocumentType.UNKNOWN, "INCONCLUSIVE", PreExtractionOutcome.UNREADABLE_ATTACHMENT.value, document.error_message or "no readable content"
    validation = validator.validate(document)
    if validation.outcome == RoleValidationOutcome.WRONG_DOCUMENT_TYPE:
        outcome = PreExtractionOutcome.WRONG_DOCUMENT_TYPE
    elif validation.outcome == RoleValidationOutcome.INCONCLUSIVE:
        outcome = PreExtractionOutcome.ROLE_INCONCLUSIVE
    elif validation.document_type == DocumentType.SI:
        outcome = PreExtractionOutcome.SI_FOUND
    else:
        outcome = PreExtractionOutcome.BL_FOUND
    marker_text = ", ".join(validation.markers)
    evidence = validation.evidence + (f"; markers={marker_text}" if marker_text else "")
    return validation.document_type, validation.outcome.value, outcome.value, evidence


def _safe(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def _listed(rows: list[InventoryRow]) -> str:
    return ", ".join(f"`{row.filename}`" for row in rows) if rows else "None."


def main() -> None:
    source = StaticBundleSource(BUNDLE)
    reader = CompositeDocumentReader()
    validator = DocumentRoleValidator()
    rows: list[InventoryRow] = []
    messages = list(source.iter_messages())

    for message in messages:
        for attachment in message.attachments:
            content = source.get_attachment_content(attachment)
            started = time.perf_counter()
            document = reader.read(content, attachment.filename, attachment.source_reference)
            parse_ms = (time.perf_counter() - started) * 1000.0
            role, validation, outcome, evidence = assess(content, document, validator)
            rows.append(
                InventoryRow(
                    email_id=message.external_message_id,
                    filename=attachment.filename,
                    format=document.format.value,
                    reader=document.reader_used,
                    readable=document.extraction_status == "EXTRACTED" and bool(document.raw_text.strip()),
                    text_chars=len(document.raw_text),
                    table_cells=sum(len(row) for table in document.tables for row in table.rows),
                    role=role.value,
                    validation=validation,
                    outcome=outcome,
                    parse_ms=parse_ms,
                    evidence=evidence,
                )
            )

    expected_count = sum(len(message.attachments) for message in messages)
    if len(rows) != expected_count or any(not row.outcome for row in rows):
        raise SystemExit(
            f"Attachment inventory incomplete: rows={len(rows)}, expected={expected_count}"
        )

    by_format = Counter(row.format for row in rows)
    by_outcome = Counter(row.outcome for row in rows)
    groups: dict[str, list[InventoryRow]] = defaultdict(list)
    for row in rows:
        groups[row.outcome].append(row)

    pdf_rows = [row for row in rows if row.filename.lower().endswith(".pdf")]
    docx_rows = [row for row in rows if row.filename.lower().endswith(".docx")]
    xlsx_rows = [row for row in rows if row.filename.lower().endswith(".xlsx")]
    scanned_rows = [row for row in rows if row.format == DocumentFormat.SCANNED_PDF.value]
    corrupt_rows = groups[PreExtractionOutcome.CORRUPTED_ATTACHMENT.value]
    empty_rows = [row for row in corrupt_rows if row.evidence == "empty attachment"]
    wrong_rows = groups[PreExtractionOutcome.WRONG_DOCUMENT_TYPE.value]
    ambiguous_rows = groups[PreExtractionOutcome.ROLE_INCONCLUSIVE.value]
    unsupported_rows = groups[PreExtractionOutcome.UNSUPPORTED_ATTACHMENT.value]

    attachments_by_email: dict[str, list[InventoryRow]] = defaultdict(list)
    for row in rows:
        attachments_by_email[row.email_id].append(row)

    email_rows: list[EmailAuditRow] = []
    for message in messages:
        classification = classify_email(email_message_to_classification_input(message))
        readiness = classification.comparison_readiness or "N/A"
        if classification.category != "document_comparison":
            status, reason = "NOT_ENTERED", "NON_COMPARISON"
        elif readiness == "AWAITING_DOCUMENTS":
            status, reason = "AWAITING_DOCUMENTS", "AWAITING_DOCUMENTS"
        elif readiness == "UNRESOLVED":
            status, reason = "BLOCKED", "READINESS_UNRESOLVED"
        else:
            email_attachments = attachments_by_email[message.external_message_id]
            attachment_outcomes = {row.outcome for row in email_attachments}
            role_counts = Counter(row.role for row in email_attachments)
            precedence = (
                PreExtractionOutcome.WRONG_DOCUMENT_TYPE.value,
                PreExtractionOutcome.UNSUPPORTED_ATTACHMENT.value,
                PreExtractionOutcome.CORRUPTED_ATTACHMENT.value,
                PreExtractionOutcome.UNREADABLE_ATTACHMENT.value,
            )
            reason = next((item for item in precedence if item in attachment_outcomes), "")
            if not reason and (role_counts["SI"] > 1 or role_counts["DRAFT_BL"] > 1):
                reason = PreExtractionOutcome.MULTIPLE_CANDIDATES.value
            if not reason and PreExtractionOutcome.ROLE_INCONCLUSIVE.value in attachment_outcomes:
                reason = "DOCUMENT_ROLE_UNRESOLVED"
            if not reason and (role_counts["SI"] != 1 or role_counts["DRAFT_BL"] != 1):
                reason = PreExtractionOutcome.MISSING_REQUIRED_ATTACHMENT.value
            status = "BLOCKED" if reason else "EXTRACTING"
            reason = reason or "DOCUMENTS_MATERIALIZED"
        email_rows.append(
            EmailAuditRow(
                email_id=message.external_message_id,
                category=classification.category,
                readiness=readiness,
                attachment_count=len(message.attachments),
                phase2_status=status,
                reason_code=reason,
            )
        )

    category_counts = Counter(row.category for row in email_rows)
    readiness_counts = Counter(row.readiness for row in email_rows)
    phase2_counts = Counter((row.phase2_status, row.reason_code) for row in email_rows)

    lines = [
        "# Phase 2 Attachment Inventory",
        "",
        "Generated only from the public participant bundle. No private reference or ground-truth data was read.",
        "",
        f"- Emails inspected: {len(messages)}",
        f"- Attachments inspected: {len(rows)} / {expected_count}",
        "- Defined outcome coverage: 100%",
        "- Unhandled exceptions: 0",
        "",
        "## Aggregate",
        "",
        "### Formats",
        "",
    ]
    lines.extend(f"- `{key}`: {value}" for key, value in sorted(by_format.items()))
    lines.extend(["", "### Outcomes", ""])
    lines.extend(f"- `{key}`: {value}" for key, value in sorted(by_outcome.items()))
    lines.extend(["", "### Category and readiness audit", ""])
    lines.extend(f"- Category `{key}`: {value}" for key, value in sorted(category_counts.items()))
    lines.extend(f"- Readiness `{key}`: {value}" for key, value in sorted(readiness_counts.items()))
    lines.extend(["", "### Phase 2 email outcomes", ""])
    lines.extend(
        f"- `{status}` / `{reason}`: {count}"
        for (status, reason), count in sorted(phase2_counts.items())
    )
    lines.extend(
        [
            "",
            "## Required special-case lists",
            "",
            f"- PDF ({len(pdf_rows)}): {_listed(pdf_rows)}",
            f"- DOCX ({len(docx_rows)}): {_listed(docx_rows)}",
            f"- XLSX ({len(xlsx_rows)}): {_listed(xlsx_rows)}",
            f"- Scanned/image-only ({len(scanned_rows)}): {_listed(scanned_rows)}",
            f"- Corrupt/truncated ({len(corrupt_rows)}): {_listed(corrupt_rows)}",
            f"- Empty/zero-byte ({len(empty_rows)}): {_listed(empty_rows)}",
            f"- Unsupported ({len(unsupported_rows)}): {_listed(unsupported_rows)}",
            f"- Ambiguous role ({len(ambiguous_rows)}): {_listed(ambiguous_rows)}",
            "",
            "## WRONG_DOCUMENT_TYPE decisions",
            "",
        ]
    )
    if wrong_rows:
        lines.extend(
            f"- `{row.email_id}` / `{row.filename}`: {_safe(row.evidence)}"
            for row in wrong_rows
        )
    else:
        lines.append("None.")

    lines.extend(
        [
            "",
            "## Per-attachment evidence",
            "",
            "| Email | Filename | Format | Reader | Readable | Text chars | Table cells | Role | Validation | Outcome | Parse ms | Evidence/anomaly |",
            "|---|---|---|---|---:|---:|---:|---|---|---|---:|---|",
        ]
    )
    for row in rows:
        lines.append(
            f"| {row.email_id} | {_safe(row.filename)} | {row.format} | {row.reader} | "
            f"{'yes' if row.readable else 'no'} | {row.text_chars} | {row.table_cells} | "
            f"{row.role} | {row.validation} | {row.outcome} | {row.parse_ms:.3f} | {_safe(row.evidence)} |"
        )

    lines.extend(
        [
            "",
            "## Per-email Phase 2 gate audit",
            "",
            "This offline corpus audit materializes all public attachments for coverage; the runtime lazy-retrieval invariant is separately proven by the requirement-marked PostgreSQL test.",
            "",
            "| Email | Category | Readiness | Attachments | Phase 2 status | Reason code |",
            "|---|---|---|---:|---|---|",
        ]
    )
    lines.extend(
        f"| {row.email_id} | {row.category} | {row.readiness} | {row.attachment_count} | {row.phase2_status} | {row.reason_code} |"
        for row in email_rows
    )

    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Attachment inventory: PASS ({len(rows)} attachments, {len(wrong_rows)} wrong-type)")


if __name__ == "__main__":
    main()
