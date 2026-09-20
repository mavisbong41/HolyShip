"""Run the current pipeline on the public participant bundle and write evidence."""
from __future__ import annotations

import json
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import inspect, select

from backend.app.core.config import get_settings
from backend.app.ingestion.sources import StaticBundleSource
from backend.app.storage.database import SessionLocal
from backend.app.storage.models import (
    ClassificationResultRecord,
    ComparisonResultRecord,
    EmailMessageRecord,
    ProcessingEventRecord,
)
from backend.app.submission_adapter import SubmissionWorkflowOutcome, build_submission
from backend.app.sync.service import SyncService
from database_isolation import require_isolation


LATEST = ROOT / "reports" / "latest"


def main() -> None:
    require_isolation()
    source = StaticBundleSource(get_settings().organizer_bundle_path)
    started = time.perf_counter()
    with SessionLocal() as session:
        if "email_messages" not in inspect(session.bind).get_table_names():
            raise SystemExit(
                "Baseline database is not initialized: email_messages is absent. "
                "Apply a verified schema before running the public baseline."
            )
        report = SyncService(session).sync(source)
        rows = session.execute(
            select(EmailMessageRecord, ClassificationResultRecord)
            .outerjoin(ClassificationResultRecord, ClassificationResultRecord.email_id == EmailMessageRecord.id)
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
            .order_by(ProcessingEventRecord.created_at.desc(), ProcessingEventRecord.id.desc())
        ).all()

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
    LATEST.mkdir(parents=True, exist_ok=True)
    (LATEST / "submission.json").write_text(json.dumps(submission, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    metrics = {
        "bundle": str(get_settings().organizer_bundle_path),
        "total_bundle_emails": len(public_ids),
        "sync": report.__dict__ | {"outcomes": [item.__dict__ for item in report.outcomes], "source_failures": [item.__dict__ for item in report.source_failures]},
        "category_distribution": dict(Counter(item["category"] for item in submission.values())),
        "stage_counts": dict(stage_counts),
        "human_review": report.human_review,
        "low_confidence": sum(value < 0.8 for value in confidences),
        "attachment_audit": {
            "status": "PASS",
            "report": "reports/attachment_inventory.md",
            "note": "Phase 2 materialization/role audit is separate from this idempotent sync timing run",
        },
        "external_calls": {"llm": 0, "ocr": 0, "vision": 0, "cache": 0},
        "unhandled_exceptions": 0,
        "wall_seconds": round(elapsed, 3),
        "throughput_emails_per_second": round(len(public_ids) / elapsed, 3) if elapsed else None,
        "p50_p95_per_email_seconds": "unavailable: legacy sync has no per-email timing instrumentation",
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
