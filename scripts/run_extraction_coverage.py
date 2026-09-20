"""Audit deterministic Phase-3 extraction over the public participant bundle."""
from __future__ import annotations

import hashlib
import re
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.classification.adapters import email_message_to_classification_input
from backend.app.classification.pipeline import classify_email
from backend.app.core.config import get_settings
from backend.app.documents.models import DocumentType, UnifiedDocument
from backend.app.documents.readers.composite import CompositeDocumentReader
from backend.app.documents.role_validation import DocumentRoleValidator, RoleValidationOutcome
from backend.app.extraction.extractor import DeterministicDocumentExtractor
from backend.app.extraction.label_mapping import LabelMapper, normalize_label_for_lookup
from backend.app.extraction.models import CANONICAL_FIELDS, DocumentExtractionResult
from backend.app.ingestion.sources import StaticBundleSource


_LABEL_VALUE = re.compile(r"^(?P<label>[^:：]{1,160})\s*[:：]\s*(?P<value>.+)$")


@dataclass(frozen=True)
class AuditDocument:
    document: UnifiedDocument
    content_sha256: str


def _candidate_labels(document: UnifiedDocument):
    for table in document.tables:
        for row in table.rows:
            if len(row) >= 2 and str(row[0]).strip() and str(row[1]).strip():
                yield str(row[0]).strip()
    for line in document.raw_text.splitlines():
        match = _LABEL_VALUE.fullmatch(line.strip())
        if match:
            yield match.group("label").strip()


def _write_reports(
    *,
    elapsed: float,
    role_counts: Counter,
    format_counts: Counter,
    field_counts: dict[str, Counter],
    reason_counts: dict[str, Counter],
    unmapped: Counter,
    unmapped_context: dict[str, set[str]],
    attempts: int,
    computations: int,
    cache_hits: int,
    cache_misses: int,
    failures: int,
    parallel_pairs: int,
) -> None:
    reports = ROOT / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    coverage = [
        "# Phase 3 public extraction coverage",
        "",
        "This audit uses only the public participant bundle. It reports extraction coverage, not accuracy; no reference labels or private ground truth were used.",
        "",
        "## Run summary",
        "",
        f"- Validated SI documents: {role_counts['SI']}",
        f"- Validated BL documents: {role_counts['DRAFT_BL']}",
        f"- Extraction attempts: {attempts}",
        f"- Fresh extraction computations: {computations}",
        f"- Cache hits: {cache_hits}",
        f"- Cache misses: {cache_misses}",
        f"- Extraction failures: {failures}",
        f"- SI/BL pairs started in a bounded two-worker pool: {parallel_pairs}",
        f"- Total extraction wall time: {elapsed:.3f} seconds",
        "- LLM calls: 0",
        "- OCR calls: 0",
        "- Vision calls: 0",
        "",
        "## Format distribution",
        "",
        "| Format | Validated documents |",
        "|---|---:|",
        *(f"| {name} | {count} |" for name, count in sorted(format_counts.items())),
        "",
        "## Canonical field coverage",
        "",
        "| Field | Resolved | Missing | Unresolved | Ambiguous |",
        "|---|---:|---:|---:|---:|",
    ]
    for field in CANONICAL_FIELDS:
        counts = field_counts[field.value]
        coverage.append(
            f"| {field.value} | {counts['RESOLVED']} | {counts['MISSING']} | "
            f"{counts['UNRESOLVED']} | {counts['AMBIGUOUS']} |"
        )
    coverage += ["", "## Missing/unresolved reasons", ""]
    for field in CANONICAL_FIELDS:
        reasons = reason_counts[field.value]
        rendered = ", ".join(f"{reason}={count}" for reason, count in sorted(reasons.items()))
        coverage.append(f"- `{field.value}`: {rendered or 'none'}")
    coverage += [
        "",
        "## Interpretation",
        "",
        "A missing field means no supported public label/value was present in the materialized content. Unresolved and ambiguous rows retain their machine-readable reason from deterministic extraction. Percent accuracy is intentionally not reported because this audit has no reference labels.",
    ]
    (reports / "extraction_coverage.md").write_text(
        "\n".join(coverage) + "\n",
        encoding="utf-8",
    )

    unmapped_report = [
        "# Phase 3 unmapped public labels",
        "",
        "Aggregate candidate labels observed in public, Phase-2-validated SI/BL content. This is audit evidence only and is not loaded by runtime mapping code. No email IDs, expected answers, or filename-based truth appear here.",
        "",
        "| Normalized candidate label | Count | Observed role/format contexts | Why not mapped |",
        "|---|---:|---|---|",
    ]
    for label, count in sorted(unmapped.items(), key=lambda item: (-item[1], item[0])):
        contexts = ", ".join(sorted(unmapped_context[label]))
        safe_label = label.replace("|", "\\|")
        unmapped_report.append(
            f"| {safe_label} | {count} | {contexts} | No exact, approved alias, bilingual, or contextual mapping. |"
        )
    if not unmapped:
        unmapped_report.append("| _none_ | 0 | n/a | No unmapped candidate labels observed. |")
    (reports / "unmapped_labels.md").write_text(
        "\n".join(unmapped_report) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    source = StaticBundleSource(get_settings().organizer_bundle_path)
    reader = CompositeDocumentReader()
    validator = DocumentRoleValidator()
    extractor = DeterministicDocumentExtractor()
    mapper = LabelMapper()
    cache: dict[tuple[str, str], DocumentExtractionResult] = {}
    role_counts: Counter[str] = Counter()
    format_counts: Counter[str] = Counter()
    field_counts = {field.value: Counter() for field in CANONICAL_FIELDS}
    reason_counts = {field.value: Counter() for field in CANONICAL_FIELDS}
    unmapped: Counter[str] = Counter()
    unmapped_context: dict[str, set[str]] = defaultdict(set)
    attempts = computations = cache_hits = cache_misses = failures = parallel_pairs = 0
    started = time.perf_counter()

    for message in source.iter_messages():
        classification = classify_email(email_message_to_classification_input(message))
        if not (
            classification.category == "document_comparison"
            and classification.comparison_readiness == "READY_FOR_COMPARISON"
        ):
            continue

        validated: list[AuditDocument] = []
        for attachment in message.attachments:
            try:
                content = source.get_attachment_content(attachment)
                document = reader.read(
                    content,
                    attachment.filename,
                    attachment.source_reference,
                )
            except Exception:
                continue
            validation = validator.validate(document)
            if not (
                validation.outcome == RoleValidationOutcome.VALID
                and validation.document_type in {DocumentType.SI, DocumentType.DRAFT_BL}
            ):
                continue
            document.document_type = validation.document_type
            validated.append(
                AuditDocument(
                    document=document,
                    content_sha256=hashlib.sha256(content).hexdigest(),
                )
            )
            role_counts[validation.document_type.value] += 1
            format_counts[document.format.value] += 1
            context = f"{validation.document_type.value}/{document.format.value}"
            for raw_label in _candidate_labels(document):
                mapping = mapper.map_label(raw_label)
                if mapping.canonical_field is None and mapping.reason_code == "UNMAPPED_LABEL":
                    normalized = normalize_label_for_lookup(raw_label)
                    if normalized:
                        unmapped[normalized] += 1
                        unmapped_context[normalized].add(context)

        # Only the two valid comparison roles are paired. Extra validated
        # candidates are still audited independently without unbounded work.
        work = validated
        attempts += len(work)
        pending: dict[tuple[str, str], list[AuditDocument]] = defaultdict(list)
        document_results: dict[int, DocumentExtractionResult] = {}
        for item in work:
            key = (item.content_sha256, extractor.version)
            if key in cache:
                cache_hits += 1
                document_results[id(item)] = cache[key]
            elif key in pending:
                cache_hits += 1
                pending[key].append(item)
            else:
                cache_misses += 1
                pending[key].append(item)

        if pending:
            workers = min(2, len(pending))
            if workers == 2:
                parallel_pairs += 1
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {
                    key: pool.submit(extractor.extract, items[0].document)
                    for key, items in pending.items()
                }
                for key, items in pending.items():
                    computations += 1
                    try:
                        result = futures[key].result()
                    except Exception:
                        failures += len(items)
                        continue
                    cache[key] = result
                    for item in items:
                        document_results[id(item)] = result

        for item in work:
            result = document_results.get(id(item))
            if result is None:
                continue
            for field_name, field in result.fields.items():
                field_counts[field_name.value][field.status.value] += 1
                if field.status.value != "RESOLVED":
                    reason_counts[field_name.value][
                        str(field.evidence.get("reason_code", "VALUE_UNRESOLVED"))
                    ] += 1

    elapsed = time.perf_counter() - started
    _write_reports(
        elapsed=elapsed,
        role_counts=role_counts,
        format_counts=format_counts,
        field_counts=field_counts,
        reason_counts=reason_counts,
        unmapped=unmapped,
        unmapped_context=unmapped_context,
        attempts=attempts,
        computations=computations,
        cache_hits=cache_hits,
        cache_misses=cache_misses,
        failures=failures,
        parallel_pairs=parallel_pairs,
    )
    print(
        "extraction coverage: "
        f"SI={role_counts['SI']} BL={role_counts['DRAFT_BL']} attempts={attempts} "
        f"computations={computations} cache_hits={cache_hits} "
        f"cache_misses={cache_misses} failures={failures} wall_seconds={elapsed:.3f}"
    )


if __name__ == "__main__":
    main()
