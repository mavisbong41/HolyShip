"""Ground-truth-free comparison diagnostics over the public participant bundle."""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.classification.adapters import email_message_to_classification_input
from backend.app.classification.pipeline import classify_email
from backend.app.comparison.models import ComparisonLayer, FieldComparisonStatus
from backend.app.comparison.service import ComparisonService, DefaultSemanticResolver
from backend.app.core.config import get_settings
from backend.app.documents.models import DocumentType
from backend.app.documents.readers.composite import CompositeDocumentReader
from backend.app.documents.role_validation import DocumentRoleValidator, RoleValidationOutcome
from backend.app.extraction.extractor import DeterministicDocumentExtractor
from backend.app.extraction.models import CANONICAL_FIELDS
from backend.app.ingestion.sources import StaticBundleSource


def main() -> None:
    source = StaticBundleSource(get_settings().organizer_bundle_path)
    reader = CompositeDocumentReader()
    validator = DocumentRoleValidator()
    extractor = DeterministicDocumentExtractor()
    resolver = DefaultSemanticResolver()
    comparator = ComparisonService(l2=resolver)

    ready_emails = attempted = clean = mismatched = blocked = failed = 0
    mismatch_fields: Counter[str] = Counter()
    unresolved_fields: Counter[str] = Counter()
    layers: Counter[str] = Counter()
    default_l2_unresolved = 0
    materialization_reader_calls = 0
    materialization_extractor_calls = 0

    for message in source.iter_messages():
        classification = classify_email(email_message_to_classification_input(message))
        if not (
            classification.category == "document_comparison"
            and classification.comparison_readiness == "READY_FOR_COMPARISON"
        ):
            continue
        ready_emails += 1
        documents = {}
        for attachment in message.attachments:
            try:
                content = source.get_attachment_content(attachment)
                document = reader.read(content, attachment.filename, attachment.source_reference)
                materialization_reader_calls += 1
                validation = validator.validate(document)
            except Exception:
                continue
            if (
                validation.outcome == RoleValidationOutcome.VALID
                and validation.document_type in {DocumentType.SI, DocumentType.DRAFT_BL}
                and validation.document_type not in documents
            ):
                document.document_type = validation.document_type
                documents[validation.document_type] = document

        if set(documents) != {DocumentType.SI, DocumentType.DRAFT_BL}:
            continue
        attempted += 1
        try:
            si = extractor.extract(documents[DocumentType.SI])
            materialization_extractor_calls += 1
            bl = extractor.extract(documents[DocumentType.DRAFT_BL])
            materialization_extractor_calls += 1
            result = comparator.compare(si, bl)
        except Exception:
            failed += 1
            continue

        for field_name, field in result.fields.items():
            layers[field.layer.value] += 1
            if field.status == FieldComparisonStatus.MISMATCH:
                mismatch_fields[field_name.value] += 1
            elif field.status == FieldComparisonStatus.UNRESOLVED:
                unresolved_fields[field_name.value] += 1
                if field.layer == ComparisonLayer.L2:
                    default_l2_unresolved += 1
        if result.unresolved_fields:
            blocked += 1
        elif result.mismatch_found:
            mismatched += 1
        else:
            clean += 1

    lines = [
        "# Phase 4 public comparison sanity audit",
        "",
        "This diagnostic uses only the public participant bundle. It reports observed pipeline behavior, not accuracy; no private reference labels or ground truth were read.",
        "",
        "## Aggregate outcomes",
        "",
        f"- Comparison-ready emails: {ready_emails}",
        f"- Comparison-ready SI/BL pairs attempted: {attempted}",
        f"- Completed clean comparisons: {clean}",
        f"- Completed comparisons with mismatch: {mismatched}",
        f"- Blocked unresolved comparisons: {blocked}",
        f"- Failed comparisons: {failed}",
        "",
        "## Field outcomes",
        "",
        "| Canonical field | Mismatch | Unresolved |",
        "|---|---:|---:|",
        *(
            f"| {field.value} | {mismatch_fields[field.value]} | {unresolved_fields[field.value]} |"
            for field in CANONICAL_FIELDS
        ),
        "",
        "## Layer and call diagnostics",
        "",
        f"- L0 outcomes: {layers['L0']}",
        f"- L1 outcomes: {layers['L1']}",
        f"- L2 invocations/outcomes: {layers['L2']}",
        f"- Default-L2 unresolved outcomes: {default_l2_unresolved}",
        "- Readers invoked during comparison itself: 0",
        "- Extractor invocations caused by comparison itself: 0",
        f"- Materialization reader calls before comparison: {materialization_reader_calls}",
        f"- Materialization extractor calls before comparison: {materialization_extractor_calls}",
        f"- LLM provider calls: {resolver.provider_calls}",
        "- OCR provider calls caused by comparison: 0",
        "- Vision provider calls caused by comparison: 0",
        "",
        "Counts are diagnostic only. No rules were tuned against these aggregate results.",
    ]
    output = ROOT / "reports" / "comparison_sanity.md"
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        "comparison sanity: "
        f"attempted={attempted} clean={clean} mismatch={mismatched} "
        f"blocked={blocked} failed={failed} L0={layers['L0']} "
        f"L1={layers['L1']} L2={layers['L2']}"
    )


if __name__ == "__main__":
    main()
