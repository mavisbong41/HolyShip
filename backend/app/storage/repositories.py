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
        candidate_scores: dict | None = None,
        evidence: dict | None = None,
        confidence: float | None = None,
        status: str = "OPEN",
        document_id: UUID | None = None,
        field_name: str | None = None,
    ) -> HumanReviewCaseRecord:
        record = HumanReviewCaseRecord(
            email_id=email_id,
            document_id=document_id,
            field_name=field_name,
            reason_code=reason_code,
            reason_text=reason_text,
            candidate_scores=candidate_scores or {},
            evidence=evidence or {},
            confidence=confidence,
            status=status,
        )
        self.session.add(record)
        self.session.flush()
        return record


class DocumentRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, document_id: UUID) -> DocumentRecord | None:
        return self.session.get(
            DocumentRecord,
            document_id,
            options=[
                selectinload(DocumentRecord.extractions).selectinload(DocumentExtractionRecord.fields)
            ],
        )

    def list_by_email_id(self, email_id: UUID) -> list[DocumentRecord]:
        return list(
            self.session.scalars(
                select(DocumentRecord)
                .where(DocumentRecord.email_id == email_id)
                .options(
                    selectinload(DocumentRecord.extractions).selectinload(DocumentExtractionRecord.fields)
                )
                .order_by(DocumentRecord.created_at.asc())
            ).all()
        )

    def create(
        self,
        *,
        email_id: UUID,
        attachment_id: UUID | None,
        document_type: str,
        format: str,
        filename: str,
        source_reference: str,
    ) -> DocumentRecord:
        record = DocumentRecord(
            email_id=email_id,
            attachment_id=attachment_id,
            document_type=document_type,
            format=format,
            filename=filename,
            source_reference=source_reference,
        )
        self.session.add(record)
        self.session.flush()
        return record


class DocumentExtractionRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, extraction_id: UUID) -> DocumentExtractionRecord | None:
        return self.session.get(
            DocumentExtractionRecord,
            extraction_id,
            options=[selectinload(DocumentExtractionRecord.fields)],
        )

    def get_latest_by_document_id(self, document_id: UUID) -> DocumentExtractionRecord | None:
        return self.session.scalar(
            select(DocumentExtractionRecord)
            .where(DocumentExtractionRecord.document_id == document_id)
            .options(selectinload(DocumentExtractionRecord.fields))
            .order_by(DocumentExtractionRecord.created_at.desc())
        )

    def create(
        self,
        *,
        document_id: UUID,
        reader_used: str,
        extraction_status: str = "EXTRACTED",
        extraction_quality: float | None = None,
        raw_text: str = "",
        pages_count: int = 1,
        metadata_json: dict | None = None,
    ) -> DocumentExtractionRecord:
        record = DocumentExtractionRecord(
            document_id=document_id,
            reader_used=reader_used,
            extraction_status=extraction_status,
            extraction_quality=extraction_quality,
            raw_text=raw_text,
            pages_count=pages_count,
            metadata_json=metadata_json or {},
        )
        self.session.add(record)
        self.session.flush()
        return record


class ExtractedFieldRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(
        self,
        *,
        extraction_id: UUID,
        field_name: str,
        raw_value: str | None,
        status: str = "EXTRACTED",
        confidence: float = 1.0,
        evidence: dict | None = None,
        extraction_method: str = "FAST_KEY_VALUE",
    ) -> ExtractedFieldRecord:
        record = ExtractedFieldRecord(
            extraction_id=extraction_id,
            field_name=field_name,
            raw_value=raw_value,
            status=status,
            confidence=confidence,
            evidence=evidence or {},
            extraction_method=extraction_method,
        )
        self.session.add(record)
        self.session.flush()
        return record

