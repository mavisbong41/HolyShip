from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.app.ingestion.models import EmailMessage
from backend.app.storage.models import (
    AttachmentRecord,
    ClassificationResultRecord,
    EmailMessageRecord,
    HumanReviewCaseRecord,
    ProcessingJobRecord,
)


class EmailRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_source_external_id(self, source_type: str, external_message_id: str) -> EmailMessageRecord | None:
        return self.session.scalar(
            select(EmailMessageRecord)
            .where(
                EmailMessageRecord.source_type == source_type,
                EmailMessageRecord.external_message_id == external_message_id,
            )
            .options(selectinload(EmailMessageRecord.attachments))
        )

    def get(self, email_id: UUID) -> EmailMessageRecord | None:
        return self.session.get(
            EmailMessageRecord,
            email_id,
            options=[selectinload(EmailMessageRecord.attachments)],
        )

    def upsert_message(self, message: EmailMessage) -> tuple[EmailMessageRecord, bool]:
        existing = self.get_by_source_external_id(message.source_type, message.external_message_id)
        if existing and existing.content_hash == message.content_hash:
            return existing, False

        record = existing or EmailMessageRecord(
            source_type=message.source_type,
            external_message_id=message.external_message_id,
        )
        record.sender = message.sender
        record.recipients = message.recipients
        record.subject = message.subject
        record.body = message.body
        record.received_at = message.received_at
        record.source_metadata = message.source_metadata
        record.content_hash = message.content_hash
        record.attachments = [
            AttachmentRecord(
                filename=attachment.filename,
                content_type=attachment.content_type,
                source_reference=attachment.source_reference,
                external_attachment_id=attachment.external_attachment_id,
            )
            for attachment in message.attachments
        ]
        self.session.add(record)
        self.session.flush()
        return record, True


class ProcessingJobRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, *, email_id: UUID, job_type: str, status: str = "PENDING", source_metadata: dict | None = None) -> ProcessingJobRecord:
        record = ProcessingJobRecord(
            email_id=email_id,
            job_type=job_type,
            status=status,
            source_metadata=source_metadata or {},
        )
        self.session.add(record)
        self.session.flush()
        return record


class ClassificationResultRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(
        self,
        *,
        email_id: UUID,
        category: str,
        confidence: float,
        candidate_scores: dict,
        reason: str,
        evidence_summary: dict,
        conflict_detected: bool,
        resolved_at_stage: str,
        classifier_version: str = "batch1-rule-v1",
    ) -> ClassificationResultRecord:
        record = ClassificationResultRecord(
            email_id=email_id,
            category=category,
            confidence=confidence,
            candidate_scores=candidate_scores,
            reason=reason,
            evidence_summary=evidence_summary,
            conflict_detected=conflict_detected,
            resolved_at_stage=resolved_at_stage,
            classifier_version=classifier_version,
        )
        self.session.add(record)
        self.session.flush()
        return record


class HumanReviewRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(
        self,
        *,
        email_id: UUID,
        reason_code: str,
        reason_text: str,
        candidate_scores: dict,
        evidence: dict,
        confidence: float | None,
        status: str = "OPEN",
    ) -> HumanReviewCaseRecord:
        record = HumanReviewCaseRecord(
            email_id=email_id,
            reason_code=reason_code,
            reason_text=reason_text,
            candidate_scores=candidate_scores,
            evidence=evidence,
            confidence=confidence,
            status=status,
        )
        self.session.add(record)
        self.session.flush()
        return record

