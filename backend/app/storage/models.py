from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.storage.database import Base


def new_uuid() -> uuid.UUID:
    return uuid.uuid4()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class EmailMessageRecord(TimestampMixin, Base):
    __tablename__ = "email_messages"
    __table_args__ = (
        UniqueConstraint("source_type", "external_message_id", name="uq_email_source_external_id"),
        CheckConstraint("processing_status IN ('NEW','QUEUED','CLASSIFYING','CLASSIFIED','AWAITING_DOCUMENTS','RETRIEVING_ATTACHMENTS','EXTRACTING','COMPARING','COMPLETED','BLOCKED','FAILED')", name="ck_email_processing_status"),
        CheckConstraint("lifecycle_status IN ('ACTIVE','DELETED','ARCHIVED')", name="ck_email_lifecycle_status"),
        CheckConstraint("outlook_read_state IN ('READ','UNREAD','UNKNOWN')", name="ck_email_outlook_read_state"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    external_message_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    sender: Mapped[str | None] = mapped_column(String(512))
    recipients: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    subject: Mapped[str] = mapped_column(Text, nullable=False, default="")
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    processing_status: Mapped[str] = mapped_column(String(50), nullable=False, default="NEW")
    lifecycle_status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE", index=True)
    outlook_read_state: Mapped[str] = mapped_column(String(20), nullable=False, default="UNKNOWN")
    outlook_categories: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    outlook_folder_id: Mapped[str | None] = mapped_column(String(512))
    outlook_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_outlook_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    outlook_sync_error: Mapped[str | None] = mapped_column(Text)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    restored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    attachments: Mapped[list[AttachmentRecord]] = relationship(
        back_populates="email",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    documents: Mapped[list[DocumentRecord]] = relationship(
        back_populates="email",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    processing_jobs: Mapped[list[ProcessingJobRecord]] = relationship(back_populates="email", cascade="all, delete-orphan")
    classification_results: Mapped[list[ClassificationResultRecord]] = relationship(back_populates="email", cascade="all, delete-orphan")
    human_review_cases: Mapped[list[HumanReviewCaseRecord]] = relationship(back_populates="email", cascade="all, delete-orphan")
    processing_events: Mapped[list[ProcessingEventRecord]] = relationship(back_populates="email", cascade="all, delete-orphan")
    comparison_results: Mapped[list[ComparisonResultRecord]] = relationship(
        back_populates="email",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ProcessingEventRecord(Base):
    __tablename__ = "processing_events"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    email_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("email_messages.id", ondelete="CASCADE"), nullable=False, index=True)
    old_status: Mapped[str | None] = mapped_column(String(50))
    new_status: Mapped[str] = mapped_column(String(50), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    email: Mapped[EmailMessageRecord] = relationship(back_populates="processing_events")


class IngestionCheckpointRecord(TimestampMixin, Base):
    """Durable state for one source polling stream.

    Organizer HTTP currently has no incremental cursor. The checkpoint records
    the last completely listed poll for audit/restart visibility; the email
    identity and content-hash state remains the authoritative dedupe guard.
    """

    __tablename__ = "ingestion_checkpoints"
    __table_args__ = (
        UniqueConstraint("source_key", name="uq_ingestion_checkpoint_source_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    source_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    last_successful_poll_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_external_id: Mapped[str | None] = mapped_column(String(255))
    last_seen_content_hash: Mapped[str | None] = mapped_column(String(64))
    poll_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error_code: Mapped[str | None] = mapped_column(String(80))
    last_error_message: Mapped[str | None] = mapped_column(Text)
    cursor_value: Mapped[str | None] = mapped_column(Text)
    cursor_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class AttachmentRecord(Base):
    __tablename__ = "attachments"
    __table_args__ = (
        UniqueConstraint(
            "email_id",
            "source_reference",
            name="uq_attachment_email_source_reference",
        ),
        CheckConstraint(
            "retrieval_status IN ('NOT_RETRIEVED','MATERIALIZED','FAILED')",
            name="ck_attachment_retrieval_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    email_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("email_messages.id", ondelete="CASCADE"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(255))
    source_reference: Mapped[str] = mapped_column(Text, nullable=False)
    external_attachment_id: Mapped[str | None] = mapped_column(String(512))
    content_sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    retrieval_status: Mapped[str] = mapped_column(String(50), nullable=False, default="NOT_RETRIEVED")
    retrieval_reason_code: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    email: Mapped[EmailMessageRecord] = relationship(back_populates="attachments")
    document: Mapped[DocumentRecord | None] = relationship(back_populates="attachment", uselist=False)


class ProcessingJobRecord(TimestampMixin, Base):
    __tablename__ = "processing_jobs"
    __table_args__ = (
        UniqueConstraint(
            "email_id",
            "job_type",
            "source_content_hash",
            name="uq_processing_job_email_type_content",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    email_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("email_messages.id", ondelete="CASCADE"), nullable=False, index=True)
    job_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING")
    error_message: Mapped[str | None] = mapped_column(Text)
    source_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    source_content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    attempt_count: Mapped[int] = mapped_column(nullable=False, default=0)

    email: Mapped[EmailMessageRecord] = relationship(back_populates="processing_jobs")


class ClassificationResultRecord(Base):
    __tablename__ = "classification_results"
    __table_args__ = (
        UniqueConstraint(
            "email_id",
            "source_content_hash",
            "classifier_version",
            name="uq_classification_email_content_version",
        ),
        CheckConstraint(
            "category IN ('document_comparison','new_si_request','invoice_query','general_message','spam')",
            name="ck_classification_category",
        ),
        CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="ck_classification_confidence",
        ),
        CheckConstraint(
            "comparison_readiness IS NULL OR comparison_readiness IN ('READY_FOR_COMPARISON','AWAITING_DOCUMENTS','UNRESOLVED')",
            name="ck_classification_readiness",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    email_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("email_messages.id", ondelete="CASCADE"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    candidate_scores: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    reason_code: Mapped[str] = mapped_column(String(80), nullable=False, default="CLASSIFICATION_RESOLVED")
    evidence_summary: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    conflict_detected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    resolved_at_stage: Mapped[str] = mapped_column(String(50), nullable=False)
    comparison_readiness: Mapped[str | None] = mapped_column(String(50))
    classifier_version: Mapped[str] = mapped_column(String(80), nullable=False, default="batch1-rule-v1")
    source_content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    email: Mapped[EmailMessageRecord] = relationship(back_populates="classification_results")


class DocumentRecord(TimestampMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint(
            "attachment_id",
            "content_sha256",
            name="uq_document_attachment_content",
        ),
        CheckConstraint(
            "routing_outcome IN ('SI_FOUND','BL_FOUND','MULTIPLE_CANDIDATES','MISSING_REQUIRED_ATTACHMENT','UNSUPPORTED_ATTACHMENT','CORRUPTED_ATTACHMENT','UNREADABLE_ATTACHMENT','WRONG_DOCUMENT_TYPE','ROLE_INCONCLUSIVE','LEGACY_UNCLASSIFIED')",
            name="ck_document_routing_outcome",
        ),
        CheckConstraint(
            "validation_outcome IN ('VALID','WRONG_DOCUMENT_TYPE','INCONCLUSIVE')",
            name="ck_document_validation_outcome",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    email_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("email_messages.id", ondelete="CASCADE"), nullable=False, index=True)
    attachment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("attachments.id", ondelete="CASCADE"), nullable=True, index=True)
    document_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # SI | DRAFT_BL | OTHER | UNKNOWN
    format: Mapped[str] = mapped_column(String(50), nullable=False)  # PLAIN_TEXT | PDF_TEXT | DOCX | XLSX | SCANNED_PDF | IMAGE | UNKNOWN
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    source_reference: Mapped[str] = mapped_column(Text, nullable=False)
    routing_outcome: Mapped[str] = mapped_column(String(50), nullable=False, default="LEGACY_UNCLASSIFIED")
    role_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    role_evidence: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    validation_outcome: Mapped[str] = mapped_column(String(50), nullable=False, default="INCONCLUSIVE")
    parse_duration_ms: Mapped[float | None] = mapped_column(Float)
    content_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    email: Mapped[EmailMessageRecord] = relationship(back_populates="documents")
    attachment: Mapped[AttachmentRecord | None] = relationship(back_populates="document")
    extractions: Mapped[list[DocumentExtractionRecord]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class DocumentExtractionRecord(TimestampMixin, Base):
    __tablename__ = "document_extractions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    reader_used: Mapped[str] = mapped_column(String(80), nullable=False)  # PlainTextReader | PdfTextReader | DocxReader | XlsxReader | OcrReader | VisionReader
    extraction_status: Mapped[str] = mapped_column(String(50), nullable=False, default="EXTRACTED")  # EXTRACTED | FAILED | PARTIAL | UNREADABLE
    extraction_quality: Mapped[float | None] = mapped_column(Float)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    pages_count: Mapped[int] = mapped_column(nullable=False, default=1)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    extractor_version: Mapped[str] = mapped_column(String(80), nullable=False, default="materialization-v1")

    document: Mapped[DocumentRecord] = relationship(back_populates="extractions")
    fields: Mapped[list[ExtractedFieldRecord]] = relationship(
        back_populates="extraction",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ExtractionCacheRecord(TimestampMixin, Base):
    """Durable, versioned pointer to one complete extraction payload."""

    __tablename__ = "extraction_cache"
    __table_args__ = (
        UniqueConstraint(
            "content_sha256",
            "extractor_version",
            name="uq_extraction_cache_content_version",
        ),
        UniqueConstraint(
            "source_extraction_id",
            name="uq_extraction_cache_source_extraction",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    extractor_version: Mapped[str] = mapped_column(String(80), nullable=False)
    source_extraction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_extractions.id", ondelete="CASCADE"),
        nullable=False,
    )


class ExtractedFieldRecord(Base):
    __tablename__ = "extracted_fields"
    __table_args__ = (
        UniqueConstraint("extraction_id", "field_name", name="uq_extracted_field_extraction_name"),
        CheckConstraint(
            "field_name IN ('shipper','consignee','notify_party','port_of_loading','port_of_discharge','container_count','gross_weight_kg')",
            name="ck_extracted_field_name",
        ),
        CheckConstraint(
            "status IN ('RESOLVED','MISSING','UNRESOLVED','AMBIGUOUS')",
            name="ck_extracted_field_status",
        ),
        CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="ck_extracted_field_confidence",
        ),
        CheckConstraint(
            "mapping_method IS NULL OR mapping_method IN ('exact_label','alias_dictionary','bilingual_label_normalization','contextual_business_rule','table_structure','llm_resolved')",
            name="ck_extracted_field_mapping_method",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    extraction_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("document_extractions.id", ondelete="CASCADE"), nullable=False, index=True)
    field_name: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    raw_label: Mapped[str | None] = mapped_column(Text)
    raw_value: Mapped[str | None] = mapped_column(Text)
    raw_value_json: Mapped[object | None] = mapped_column(JSONB)
    canonical_value: Mapped[object | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="MISSING")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    evidence: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    source_location: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    mapping_method: Mapped[str | None] = mapped_column(String(80))
    extraction_method: Mapped[str] = mapped_column(String(80), nullable=False, default="DETERMINISTIC_ONE_PASS")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    extraction: Mapped[DocumentExtractionRecord] = relationship(back_populates="fields")


class ComparisonResultRecord(TimestampMixin, Base):
    __tablename__ = "comparison_results"
    __table_args__ = (
        UniqueConstraint(
            "email_id",
            "si_extraction_id",
            "bl_extraction_id",
            "comparison_version",
            name="uq_comparison_identity_version",
        ),
        CheckConstraint(
            "comparison_state IN ('COMPLETED','BLOCKED')",
            name="ck_comparison_result_state",
        ),
        CheckConstraint(
            "resolution_status IS NULL OR resolution_status IN ('OPEN','ACKNOWLEDGED','RESOLVED')",
            name="ck_comparison_resolution_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    email_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("email_messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    si_extraction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_extractions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    bl_extraction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_extractions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    review_case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("human_review_cases.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    supersedes_comparison_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("comparison_results.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    comparison_version: Mapped[str] = mapped_column(String(80), nullable=False)
    comparison_state: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    mismatch_found: Mapped[bool] = mapped_column(Boolean, nullable=False)
    all_fields_definite: Mapped[bool] = mapped_column(Boolean, nullable=False)
    mismatched_fields: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    unresolved_fields: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    reason_code: Mapped[str] = mapped_column(String(80), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    resolution_status: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    email: Mapped[EmailMessageRecord] = relationship(back_populates="comparison_results")
    fields: Mapped[list[FieldComparisonRecord]] = relationship(
        back_populates="comparison_result",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    overrides: Mapped[list[HumanReviewFieldOverrideRecord]] = relationship(
        back_populates="comparison_result",
        cascade="all, delete-orphan",
        passive_deletes=True,
        foreign_keys="HumanReviewFieldOverrideRecord.comparison_result_id",
    )


class FieldComparisonRecord(Base):
    __tablename__ = "field_comparisons"
    __table_args__ = (
        UniqueConstraint(
            "comparison_result_id",
            "field_name",
            name="uq_field_comparison_result_name",
        ),
        CheckConstraint(
            "field_name IN ('shipper','consignee','notify_party','port_of_loading','port_of_discharge','container_count','gross_weight_kg')",
            name="ck_field_comparison_name",
        ),
        CheckConstraint(
            "status IN ('MATCH','MISMATCH','UNRESOLVED')",
            name="ck_field_comparison_status",
        ),
        CheckConstraint(
            "comparison_layer IN ('PRECONDITION','L0','L1','L2')",
            name="ck_field_comparison_layer",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    comparison_result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("comparison_results.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    si_field_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("extracted_fields.id", ondelete="CASCADE"),
        nullable=False,
    )
    bl_field_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("extracted_fields.id", ondelete="CASCADE"),
        nullable=False,
    )
    field_name: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    si_raw_value: Mapped[object | None] = mapped_column(JSONB)
    bl_raw_value: Mapped[object | None] = mapped_column(JSONB)
    si_canonical_value: Mapped[object | None] = mapped_column(JSONB)
    bl_canonical_value: Mapped[object | None] = mapped_column(JSONB)
    si_normalized_value: Mapped[object | None] = mapped_column(JSONB)
    bl_normalized_value: Mapped[object | None] = mapped_column(JSONB)
    comparison_layer: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    reason_code: Mapped[str] = mapped_column(String(80), nullable=False)
    evidence: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    comparison_result: Mapped[ComparisonResultRecord] = relationship(back_populates="fields")


class AIResolutionRecord(TimestampMixin, Base):
    """Durable Phase-6 resolver cache and immutable audit payload."""

    __tablename__ = "ai_resolutions"
    __table_args__ = (
        UniqueConstraint("request_hash", name="uq_ai_resolution_request_hash"),
        CheckConstraint(
            "purpose IN ('EXTRACTION','SEMANTIC')",
            name="ck_ai_resolution_purpose",
        ),
        CheckConstraint(
            "field_name IN ('shipper','consignee','notify_party','port_of_loading','port_of_discharge','container_count','gross_weight_kg')",
            name="ck_ai_resolution_field_name",
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_ai_resolution_confidence",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    purpose: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    case_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    field_name: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    source_identity: Mapped[str] = mapped_column(Text, nullable=False)
    provider_name: Mapped[str] = mapped_column(String(80), nullable=False)
    model_name: Mapped[str] = mapped_column(String(160), nullable=False)
    resolver_version: Mapped[str] = mapped_column(String(80), nullable=False)
    prompt_schema_version: Mapped[str] = mapped_column(String(80), nullable=False)
    request_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    response_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    accepted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    validation_reason: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    provider_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class HumanReviewCaseRecord(TimestampMixin, Base):
    __tablename__ = "human_review_cases"
    __table_args__ = (
        CheckConstraint(
            "status IN ('OPEN','IN_REVIEW','RESOLVED','DISMISSED')",
            name="ck_human_review_status",
        ),
        CheckConstraint(
            "case_origin IN ('LEGACY','ACTIVE')",
            name="ck_human_review_case_origin",
        ),
        Index(
            "uq_human_review_active_identity",
            "email_id",
            "reason_code",
            "workflow_identity",
            unique=True,
            postgresql_where=text("status IN ('OPEN','IN_REVIEW')"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    email_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("email_messages.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, index=True)
    source_comparison_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    field_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    reason_code: Mapped[str] = mapped_column(String(80), nullable=False)
    reason_text: Mapped[str] = mapped_column(Text, nullable=False)
    candidate_scores: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    evidence: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    confidence: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="OPEN")
    case_origin: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")
    workflow_identity: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default=lambda: f"manual:{uuid.uuid4()}",
    )
    reviewer_name: Mapped[str | None] = mapped_column(String(255))
    resolution: Mapped[str | None] = mapped_column(String(80))
    notes: Mapped[str | None] = mapped_column(Text)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    email: Mapped[EmailMessageRecord] = relationship(back_populates="human_review_cases")
    overrides: Mapped[list[HumanReviewFieldOverrideRecord]] = relationship(
        back_populates="review_case",
        cascade="all, delete-orphan",
        passive_deletes=True,
        foreign_keys="HumanReviewFieldOverrideRecord.review_case_id",
    )
    events: Mapped[list[HumanReviewEventRecord]] = relationship(
        back_populates="review_case",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    ai_suggestions: Mapped[list[AISuggestionRecord]] = relationship(
        back_populates="review_case",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    review_plans: Mapped[list[ReviewPlanRecord]] = relationship(
        back_populates="review_case",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class HumanReviewFieldOverrideRecord(Base):
    __tablename__ = "human_review_field_overrides"
    __table_args__ = (
        CheckConstraint("num_nonnulls(review_case_id, comparison_result_id) = 1", name="ck_field_override_single_owner"),
        CheckConstraint("document_side IN ('SI','BL')", name="ck_review_override_side"),
        CheckConstraint(
            "field_name IN ('shipper','consignee','notify_party','port_of_loading','port_of_discharge','container_count','gross_weight_kg')",
            name="ck_review_override_field_name",
        ),
        Index(
            "uq_review_override_active_field",
            "review_case_id",
            "document_side",
            "field_name",
            unique=True,
            postgresql_where=text("active AND review_case_id IS NOT NULL"),
        ),
        Index(
            "uq_comparison_override_active_field",
            "comparison_result_id",
            "document_side",
            "field_name",
            unique=True,
            postgresql_where=text("active AND comparison_result_id IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    review_case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("human_review_cases.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    comparison_result_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("comparison_results.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    document_side: Mapped[str] = mapped_column(String(10), nullable=False)
    field_name: Mapped[str] = mapped_column(String(80), nullable=False)
    original_field_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("extracted_fields.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    corrected_value: Mapped[object] = mapped_column(JSONB, nullable=False)
    corrected_canonical_value: Mapped[object] = mapped_column(JSONB, nullable=False)
    reviewer_name: Mapped[str | None] = mapped_column(String(255))
    note: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    supersedes_override_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("human_review_field_overrides.id", ondelete="SET NULL"),
        nullable=True,
    )
    ai_suggestion_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_suggestions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    review_case: Mapped[HumanReviewCaseRecord | None] = relationship(
        back_populates="overrides",
        foreign_keys=[review_case_id],
    )
    comparison_result: Mapped[ComparisonResultRecord | None] = relationship(
        back_populates="overrides",
        foreign_keys=[comparison_result_id],
    )


class HumanReviewEventRecord(Base):
    __tablename__ = "human_review_events"
    __table_args__ = (
        CheckConstraint(
            "action IN ('CASE_CREATED','CASE_OPENED','CASE_CLAIMED','FIELD_OVERRIDE_ADDED','FIELD_OVERRIDE_REPLACED','RESOLVE_REQUESTED','RECOMPARISON_COMPLETED','CASE_RESOLVED','CASE_DISMISSED','AI_ASSISTANT_ASKED','AI_SUGGESTION_CREATED','AI_SUGGESTION_ACCEPTED','AI_SUGGESTION_EDITED','AI_SUGGESTION_DISMISSED')",
            name="ck_human_review_event_action",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    review_case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("human_review_cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    actor_name: Mapped[str | None] = mapped_column(String(255))
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)

    review_case: Mapped[HumanReviewCaseRecord] = relationship(back_populates="events")


class AISuggestionRecord(Base):
    __tablename__ = "ai_suggestions"
    __table_args__ = (
        CheckConstraint(
            "mode IN ('EXPLANATION_ONLY','ACTIONABLE_SUGGESTION','INSUFFICIENT_EVIDENCE')",
            name="ck_ai_suggestion_mode",
        ),
        CheckConstraint(
            "document_side IS NULL OR document_side IN ('SI','BL')",
            name="ck_ai_suggestion_side",
        ),
        CheckConstraint(
            "field IS NULL OR field IN ('shipper','consignee','notify_party','port_of_loading','port_of_discharge','container_count','gross_weight_kg')",
            name="ck_ai_suggestion_field",
        ),
        CheckConstraint(
            "status IN ('PENDING','ACCEPTED','EDITED_APPLIED','DISMISSED')",
            name="ck_ai_suggestion_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    human_review_case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("human_review_cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    mode: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    document_side: Mapped[str | None] = mapped_column(String(10), nullable=True)
    field: Mapped[str | None] = mapped_column(String(80), nullable=True)
    current_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_refs: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    provider_name: Mapped[str] = mapped_column(String(80), nullable=False, default="disabled")
    provider_model: Mapped[str] = mapped_column(String(160), nullable=False, default="none")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)

    review_case: Mapped[HumanReviewCaseRecord] = relationship(back_populates="ai_suggestions")


class ReviewPlanRecord(TimestampMixin, Base):
    __tablename__ = "review_plans"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT','CONFIRMED','APPLIED','APPLY_FAILED','CANCELLED')",
            name="ck_review_plan_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    review_case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("human_review_cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="DRAFT", index=True)
    created_by: Mapped[str | None] = mapped_column(String(255))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_by: Mapped[str | None] = mapped_column(String(255))
    applied_comparison_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("comparison_results.id", ondelete="SET NULL")
    )
    error_message: Mapped[str | None] = mapped_column(Text)

    review_case: Mapped[HumanReviewCaseRecord] = relationship(back_populates="review_plans")
    items: Mapped[list[ReviewPlanItemRecord]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", passive_deletes=True
    )


class ReviewPlanItemRecord(Base):
    __tablename__ = "review_plan_items"
    __table_args__ = (
        CheckConstraint("document_side IN ('SI','BL')", name="ck_review_plan_item_side"),
        CheckConstraint(
            "field_name IN ('shipper','consignee','notify_party','port_of_loading','port_of_discharge','container_count','gross_weight_kg')",
            name="ck_review_plan_item_field",
        ),
        CheckConstraint(
            "status IN ('PROPOSED','APPROVED','EDITED','REJECTED','APPLIED')",
            name="ck_review_plan_item_status",
        ),
        UniqueConstraint("plan_id", "document_side", "field_name", name="uq_review_plan_item_target"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("review_plans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ai_suggestion_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_suggestions.id", ondelete="SET NULL"), index=True
    )
    document_side: Mapped[str] = mapped_column(String(10), nullable=False)
    field_name: Mapped[str] = mapped_column(String(80), nullable=False)
    current_value: Mapped[object | None] = mapped_column(JSONB)
    proposed_value: Mapped[object] = mapped_column(JSONB, nullable=False)
    human_edited_value: Mapped[object | None] = mapped_column(JSONB)
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    confidence: Mapped[float | None] = mapped_column(Float)
    action: Mapped[str] = mapped_column(String(40), nullable=False, default="REPLACE")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PROPOSED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    plan: Mapped[ReviewPlanRecord] = relationship(back_populates="items")


class DataLifecycleRunRecord(Base):
    """Append-only summary for scheduled retention cleanup runs."""

    __tablename__ = "data_lifecycle_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="STARTED", index=True)
    policy: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    summary: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class AuditEventRecord(Base):
    """Append-only audit event for cross-feature business traceability."""

    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    actor_type: Mapped[str] = mapped_column(String(50), nullable=False, default="SYSTEM", index=True)
    actor_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)

