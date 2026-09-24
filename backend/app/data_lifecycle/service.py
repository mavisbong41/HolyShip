from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import String, cast, delete, func, select, update
from sqlalchemy.orm import Session

from backend.app.core.config import Settings
from backend.app.storage.models import (
    AISuggestionRecord,
    AttachmentRecord,
    AuditEventRecord,
    DataLifecycleRunRecord,
    EmailMessageRecord,
    ExtractionCacheRecord,
    IngestionCheckpointRecord,
    ProcessingEventRecord,
    ProcessingJobRecord,
    utcnow,
)


REDACTED_MARKER = "[REDACTED BY DATA LIFECYCLE POLICY]"


@dataclass(frozen=True)
class DataLifecyclePolicy:
    raw_email_body_days: int
    attachment_days: int
    cache_days: int
    processing_jobs_days: int
    processing_events_days: int
    ai_suggestions_days: int
    ingestion_checkpoints_days: int

    @classmethod
    def from_settings(cls, settings: Settings) -> "DataLifecyclePolicy":
        return cls(
            raw_email_body_days=settings.retention_raw_email_body_days,
            attachment_days=settings.retention_attachment_days,
            cache_days=settings.retention_cache_days,
            processing_jobs_days=settings.retention_processing_jobs_days,
            processing_events_days=settings.retention_processing_events_days,
            ai_suggestions_days=settings.retention_ai_suggestions_days,
            ingestion_checkpoints_days=settings.retention_ingestion_checkpoints_days,
        )

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


class DataLifecycleService:
    """Apply retention rules without purging protected business evidence.

    Protected records include human review history, human overrides,
    classification results, comparison results, and field comparisons. This
    service targets transient records or redacts raw sensitive payloads while
    keeping metadata and audit-relevant rows.
    """

    def __init__(
        self,
        session: Session,
        policy: DataLifecyclePolicy,
        *,
        now: datetime | None = None,
    ) -> None:
        self.session = session
        self.policy = policy
        self.now = now or utcnow()

    def run(self, *, dry_run: bool = True, source: str = "COMMAND") -> DataLifecycleRunRecord:
        run = DataLifecycleRunRecord(
            id=uuid4(),
            started_at=self.now,
            dry_run=dry_run,
            status="STARTED",
            policy=self.policy.as_dict(),
            summary={},
        )
        self.session.add(run)
        self.session.flush()

        try:
            summary = self._build_summary()
            if not dry_run:
                self._apply()
            run.summary = summary
            run.status = "DRY_RUN" if dry_run else "APPLIED"
            run.completed_at = utcnow()
            self._record_audit_event(run, source=source)
            self.session.commit()
        except Exception as exc:
            self.session.rollback()
            run = DataLifecycleRunRecord(
                id=uuid4(),
                started_at=self.now,
                completed_at=utcnow(),
                dry_run=dry_run,
                status="FAILED",
                policy=self.policy.as_dict(),
                summary={},
                error_message=str(exc),
            )
            self.session.add(run)
            self.session.flush()
            self._record_audit_event(run, source=source)
            self.session.commit()
        return run

    def _cutoff(self, days: int) -> datetime:
        return self.now - timedelta(days=days)

    def _build_summary(self) -> dict[str, Any]:
        return {
            "protected_records_preserved": {
                "audit_history": "preserved",
                "human_review_history": "preserved",
                "human_overrides": "preserved",
                "critical_comparison_history": "preserved",
            },
            "delete_candidates": {
                "extraction_cache": self._count_extraction_cache(),
                "processing_jobs": self._count_processing_jobs(),
                "ingestion_checkpoints": self._count_ingestion_checkpoints(),
                "processing_events": self._count_processing_events(),
            },
            "redaction_candidates": {
                "raw_email_bodies": self._count_raw_email_bodies(),
                "attachment_source_references": self._count_attachment_source_references(),
                "ai_suggestion_payloads": self._count_ai_suggestion_payloads(),
            },
        }

    def _count(self, statement) -> int:
        return int(self.session.scalar(statement) or 0)

    def _count_extraction_cache(self) -> int:
        return self._count(
            select(func.count())
            .select_from(ExtractionCacheRecord)
            .where(ExtractionCacheRecord.updated_at < self._cutoff(self.policy.cache_days))
        )

    def _count_processing_jobs(self) -> int:
        return self._count(
            select(func.count())
            .select_from(ProcessingJobRecord)
            .where(ProcessingJobRecord.updated_at < self._cutoff(self.policy.processing_jobs_days))
            .where(ProcessingJobRecord.status.in_(("COMPLETED", "FAILED")))
        )

    def _count_ingestion_checkpoints(self) -> int:
        return self._count(
            select(func.count())
            .select_from(IngestionCheckpointRecord)
            .where(IngestionCheckpointRecord.updated_at < self._cutoff(self.policy.ingestion_checkpoints_days))
        )

    def _count_processing_events(self) -> int:
        return self._count(
            select(func.count())
            .select_from(ProcessingEventRecord)
            .where(ProcessingEventRecord.created_at < self._cutoff(self.policy.processing_events_days))
        )

    def _count_raw_email_bodies(self) -> int:
        return self._count(
            select(func.count())
            .select_from(EmailMessageRecord)
            .where(EmailMessageRecord.created_at < self._cutoff(self.policy.raw_email_body_days))
            .where(EmailMessageRecord.body != "")
            .where(EmailMessageRecord.body != REDACTED_MARKER)
            .where(EmailMessageRecord.processing_status.in_(("COMPLETED", "BLOCKED", "AWAITING_DOCUMENTS", "FAILED")))
        )

    def _count_attachment_source_references(self) -> int:
        return self._count(
            select(func.count())
            .select_from(AttachmentRecord)
            .where(AttachmentRecord.created_at < self._cutoff(self.policy.attachment_days))
            .where(~AttachmentRecord.source_reference.startswith(REDACTED_MARKER))
            .where(AttachmentRecord.retrieval_status.in_(("MATERIALIZED", "FAILED")))
        )

    def _count_ai_suggestion_payloads(self) -> int:
        return self._count(
            select(func.count())
            .select_from(AISuggestionRecord)
            .where(AISuggestionRecord.created_at < self._cutoff(self.policy.ai_suggestions_days))
            .where(AISuggestionRecord.message != REDACTED_MARKER)
            .where(AISuggestionRecord.status.in_(("ACCEPTED", "EDITED_APPLIED", "DISMISSED")))
        )

    def _apply(self) -> None:
        self.session.execute(
            delete(ExtractionCacheRecord).where(
                ExtractionCacheRecord.updated_at < self._cutoff(self.policy.cache_days)
            )
        )
        self.session.execute(
            delete(ProcessingJobRecord)
            .where(ProcessingJobRecord.updated_at < self._cutoff(self.policy.processing_jobs_days))
            .where(ProcessingJobRecord.status.in_(("COMPLETED", "FAILED")))
        )
        self.session.execute(
            delete(IngestionCheckpointRecord).where(
                IngestionCheckpointRecord.updated_at < self._cutoff(self.policy.ingestion_checkpoints_days)
            )
        )
        self.session.execute(
            delete(ProcessingEventRecord).where(
                ProcessingEventRecord.created_at < self._cutoff(self.policy.processing_events_days)
            )
        )
        self.session.execute(
            update(EmailMessageRecord)
            .where(EmailMessageRecord.created_at < self._cutoff(self.policy.raw_email_body_days))
            .where(EmailMessageRecord.body != "")
            .where(EmailMessageRecord.body != REDACTED_MARKER)
            .where(EmailMessageRecord.processing_status.in_(("COMPLETED", "BLOCKED", "AWAITING_DOCUMENTS", "FAILED")))
            .values(body=REDACTED_MARKER, updated_at=datetime.now(timezone.utc))
        )
        self.session.execute(
            update(AttachmentRecord)
            .where(AttachmentRecord.created_at < self._cutoff(self.policy.attachment_days))
            .where(~AttachmentRecord.source_reference.startswith(REDACTED_MARKER))
            .where(AttachmentRecord.retrieval_status.in_(("MATERIALIZED", "FAILED")))
            .values(
                source_reference=func.concat(REDACTED_MARKER, ":", cast(AttachmentRecord.id, String)),
                content_sha256=None,
            )
        )
        self.session.execute(
            update(AISuggestionRecord)
            .where(AISuggestionRecord.created_at < self._cutoff(self.policy.ai_suggestions_days))
            .where(AISuggestionRecord.message != REDACTED_MARKER)
            .where(AISuggestionRecord.status.in_(("ACCEPTED", "EDITED_APPLIED", "DISMISSED")))
            .values(
                message=REDACTED_MARKER,
                current_value=None,
                suggested_value=None,
                reason=None,
                evidence_refs=[],
            )
        )

    def _record_audit_event(self, run: DataLifecycleRunRecord, *, source: str) -> None:
        self.session.add(
            AuditEventRecord(
                event_type="DATA_LIFECYCLE_RUN_RECORDED",
                actor_type="SYSTEM",
                actor_name="HolyShip Data Lifecycle",
                source=source,
                entity_type="DATA_LIFECYCLE_RUN",
                entity_id=run.id,
                metadata_json={
                    "status": run.status,
                    "dry_run": run.dry_run,
                    "policy": run.policy,
                    "summary": run.summary,
                    "error_message": run.error_message,
                },
            )
        )
