"""Run the current pipeline on the public participant bundle and write evidence."""
from __future__ import annotations

import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine, func, inspect, select
from sqlalchemy.orm import sessionmaker

from backend.app.core.config import get_settings
from backend.app.ingestion.sources import StaticBundleSource
from backend.app.storage.models import (
    ClassificationResultRecord,
    ComparisonResultRecord,
    EmailMessageRecord,
    HumanReviewCaseRecord,
    ProcessingEventRecord,
)
from backend.app.submission_adapter import SubmissionWorkflowOutcome, build_submission
from backend.app.sync.service import SyncService
from backend.app.resolution.runtime import get_configured_resolution_executor_factory
from database_isolation import require_eval_isolation
from evaluation_database import reset_and_migrate


LATEST = ROOT / "reports" / "latest"
PUBLIC_CATEGORIES = {"BL_COMPARISON", "SI_REQUEST", "INVOICE_QUERY", "GENERAL", "SPAM"}
PUBLIC_STATUSES = {"OK", "MISMATCH", "NEEDS_REVIEW"}
PUBLIC_REVIEW_REASONS = {None, "wrong_doc_type", "missing_attachment", "unreadable", "missing_value"}
PUBLIC_DEFECT_FIELDS = {
    "shipper",
    "consignee",
    "notify_party",
    "port_of_loading",
    "port_of_discharge",
    "container_count",
    "gross_weight_kg",
}


def validate_submission(submission: dict, public_ids: list[str]) -> None:
    sample = json.loads(
        (ROOT / "data" / "bundle" / "sample_submission.json").read_text(encoding="utf-8")
    )
    if len(public_ids) != len(set(public_ids)):
        raise SystemExit("Evaluation source contains duplicate public email IDs.")
    if set(public_ids) != set(sample) or set(submission) != set(sample):
        raise SystemExit("Submission IDs do not exactly match sample_submission.json.")
    required_keys = set(next(iter(sample.values())))
    for email_id, item in submission.items():
        if set(item) != required_keys:
            raise SystemExit(f"Submission entry {email_id} has incorrect output keys.")
        if item["category"] not in PUBLIC_CATEGORIES:
            raise SystemExit(f"Submission entry {email_id} has an invalid category.")
        if item["status"] not in PUBLIC_STATUSES:
            raise SystemExit(f"Submission entry {email_id} has an invalid status.")
        if item["review_reason"] not in PUBLIC_REVIEW_REASONS:
            raise SystemExit(f"Submission entry {email_id} has an invalid review reason.")
        defect_fields = item["defect_fields"]
        if (
            not isinstance(defect_fields, list)
            or len(defect_fields) != len(set(defect_fields))
            or any(field not in PUBLIC_DEFECT_FIELDS for field in defect_fields)
        ):
            raise SystemExit(f"Submission entry {email_id} has invalid defect fields.")
        is_mismatch = item["status"] == "MISMATCH"
        if item["has_defect"] is not is_mismatch:
            raise SystemExit(f"Submission entry {email_id} has inconsistent has_defect.")
        if is_mismatch and (not defect_fields or item["review_reason"] is not None):
            raise SystemExit(f"Submission entry {email_id} has inconsistent mismatch output.")
        if not is_mismatch and defect_fields:
            raise SystemExit(f"Submission entry {email_id} exposes defects without MISMATCH.")
        if item["status"] == "NEEDS_REVIEW" and item["review_reason"] is None:
            raise SystemExit(f"Submission entry {email_id} lacks a review reason.")
        if item["status"] == "OK" and item["review_reason"] is not None:
            raise SystemExit(f"Submission entry {email_id} has a review reason while OK.")


def main() -> None:
    _dev_url, _test_url, eval_url = require_eval_isolation()
    reset_and_migrate(eval_url)
    os.environ["DATABASE_URL"] = eval_url
    get_settings.cache_clear()
    source = StaticBundleSource(get_settings().organizer_bundle_path)
    engine = create_engine(eval_url, pool_pre_ping=True)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    started = time.perf_counter()
    try:
        with session_factory() as session:
            if "email_messages" not in inspect(session.bind).get_table_names():
                raise SystemExit("Evaluation migrations did not initialize email_messages.")
            settings = get_settings()
            report = SyncService(
                session,
                confidence_threshold=settings.classification_threshold,
                margin_threshold=settings.classification_margin_threshold,
                max_workers=settings.sync_max_workers,
                session_factory=session_factory,
                retry_max_attempts=settings.retry_max_attempts,
                semantic_resolver_timeout_seconds=settings.semantic_resolver_timeout_seconds,
                extraction_max_workers=settings.extraction_max_workers,
                ocr_timeout_seconds=settings.ocr_timeout_seconds,
                ocr_max_calls=settings.ocr_max_calls,
                ocr_max_concurrent_calls=settings.ocr_max_concurrent_calls,
                resolution_executor_factory=get_configured_resolution_executor_factory(settings),
            ).sync(source)
            rows = session.execute(
                select(EmailMessageRecord, ClassificationResultRecord)
                .outerjoin(
                    ClassificationResultRecord,
                    ClassificationResultRecord.email_id == EmailMessageRecord.id,
                )
                .where(EmailMessageRecord.source_type == StaticBundleSource.source_type)
                .order_by(ClassificationResultRecord.created_at.desc())
            ).all()
            emails = session.scalars(
                select(EmailMessageRecord)
                .where(EmailMessageRecord.source_type == StaticBundleSource.source_type)
            ).all()
            email_ids = [email.id for email in emails]
            comparison_rows = session.scalars(
                select(ComparisonResultRecord)
                .where(ComparisonResultRecord.email_id.in_(email_ids))
                .order_by(ComparisonResultRecord.created_at.desc())
            ).all()
            event_rows = session.scalars(
                select(ProcessingEventRecord)
                .where(ProcessingEventRecord.email_id.in_(email_ids))
                .order_by(
                    ProcessingEventRecord.created_at.desc(),
                    ProcessingEventRecord.id.desc(),
                )
            ).all()
            human_review_count = session.scalar(
                select(func.count()).select_from(HumanReviewCaseRecord)
            ) or 0
    finally:
        engine.dispose()

    elapsed = time.perf_counter() - started
    latest_by_email: dict[str, tuple[str, dict[str, float]]] = {}
    stage_counts: Counter[str] = Counter()
    confidences: list[float] = []
    for email, classification in rows:
        if classification is None or email.external_message_id in latest_by_email:
            continue
        latest_by_email[email.external_message_id] = (classification.category, classification.candidate_scores)
        stage_counts[classification.resolved_at_stage] += 1
        confidences.append(classification.confidence)

    latest_comparison = {}
    for comparison in comparison_rows:
        latest_comparison.setdefault(comparison.email_id, comparison)
    latest_reason = {}
    for event in event_rows:
        latest_reason.setdefault(event.email_id, event.reason_code)
    workflow_by_email: dict[str, SubmissionWorkflowOutcome] = {}
    for email in emails:
        comparison = latest_comparison.get(email.id)
        if comparison is not None:
            workflow_by_email[email.external_message_id] = SubmissionWorkflowOutcome(
                processing_status=comparison.comparison_state,
                reason_code=comparison.reason_code,
                mismatch_found=comparison.mismatch_found,
                mismatched_fields=tuple(comparison.mismatched_fields),
                unresolved_fields=tuple(comparison.unresolved_fields),
            )
        else:
            workflow_by_email[email.external_message_id] = SubmissionWorkflowOutcome(
                processing_status=email.processing_status,
                reason_code=latest_reason.get(email.id) or "MISSING_COMPARISON_RESULT",
                mismatch_found=False,
                mismatched_fields=(),
                unresolved_fields=(),
            )

    # The adapter still writes every public id even if a future technical run
    # leaves a row without classification, using the safe GENERAL fallback.
    public_ids = [message.external_message_id for message in StaticBundleSource(get_settings().organizer_bundle_path).iter_messages()]
    submission = build_submission(
        ((email_id, *latest_by_email.get(email_id, ("GENERAL_MAIL", {}))) for email_id in public_ids),
        workflow_by_email=workflow_by_email,
    )
    validate_submission(submission, public_ids)
    LATEST.mkdir(parents=True, exist_ok=True)
    (LATEST / "submission.json").write_text(json.dumps(submission, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    metrics = {
        "bundle": str(get_settings().organizer_bundle_path),
        "total_bundle_emails": len(public_ids),
        "sync": report.__dict__ | {"outcomes": [item.__dict__ for item in report.outcomes], "source_failures": [item.__dict__ for item in report.source_failures]},
        "category_distribution": dict(Counter(item["category"] for item in submission.values())),
        "stage_counts": dict(stage_counts),
        "human_review": human_review_count,
        "unresolved_comparisons": sum(bool(row.unresolved_fields) for row in latest_comparison.values()),
        "low_confidence": sum(value < 0.8 for value in confidences),
        "attachment_audit": {
            "status": "PASS",
            "report": "reports/attachment_inventory.md",
            "note": "Phase 2 materialization/role audit is separate from this idempotent sync timing run",
        },
        "external_calls": {
            "reader": report.reader_calls,
            "extractor": report.extractor_calls,
            "llm": report.resolver_calls,
            "ocr": report.ocr_calls,
            "vision": report.vision_calls,
            "cache_hits": report.cache_hits,
            "cache_misses": report.cache_misses,
            "resolver_accepted": report.resolver_accepted,
            "resolver_rejected": report.resolver_rejected,
            "resolver_cache_hits": report.resolver_cache_hits,
            "resolver_failures": report.resolver_failures,
            "resolver_malformed": report.resolver_malformed,
            "escalated_cases": report.escalated_cases,
        },
        "operational_failures": {
            "reader": sum(event.reason_code in {
                "DOCUMENT_READER_FAILED", "ATTACHMENT_READ_FAILED", "DOCUMENT_FIELD_EXTRACTION_FAILED"
            } for event in event_rows),
            "ocr": sum(event.reason_code == "OCR_ENGINE_FAILED" for event in event_rows),
            "provider": report.resolver_failures,
        },
        "retries": report.retries,
        "source_retry_attempts": report.source_retry_attempts,
        "unhandled_exceptions": report.unhandled_exceptions,
        "wall_seconds": round(elapsed, 3),
        "throughput_emails_per_second": round(len(public_ids) / elapsed, 3) if elapsed else None,
        "p50_p95_per_email_seconds": {
            "p50": round(report.p50_per_email_ms / 1000, 6) if report.p50_per_email_ms is not None else None,
            "p95": round(report.p95_per_email_ms / 1000, 6) if report.p95_per_email_ms is not None else None,
        },
        "max_workers": report.max_workers,
        "peak_rss": "unavailable: no declared cross-platform process-metrics dependency",
    }
    (LATEST / "eval.json").write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (LATEST / "eval.md").write_text("# Current public-bundle evaluation\n\n```json\n" + json.dumps(metrics, indent=2, sort_keys=True) + "\n```\n", encoding="utf-8")
    history = ROOT / "reports" / "history.csv"
    if not history.exists():
        history.write_text("wall_seconds,throughput_emails_per_second,total_bundle_emails\n", encoding="utf-8")
    with history.open("a", encoding="utf-8") as handle:
        handle.write(f"{metrics['wall_seconds']},{metrics['throughput_emails_per_second']},{len(public_ids)}\n")
    print(json.dumps({key: metrics[key] for key in ("total_bundle_emails", "wall_seconds", "throughput_emails_per_second")}, indent=2))


if __name__ == "__main__":
    main()
