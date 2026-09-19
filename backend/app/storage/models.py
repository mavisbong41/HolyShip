from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text, UniqueConstraint
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

    attachments: Mapped[list[AttachmentRecord]] = relationship(
        back_populates="email",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    processing_jobs: Mapped[list[ProcessingJobRecord]] = relationship(back_populates="email", cascade="all, delete-orphan")
    classification_results: Mapped[list[ClassificationResultRecord]] = relationship(back_populates="email", cascade="all, delete-orphan")
    human_review_cases: Mapped[list[HumanReviewCaseRecord]] = relationship(back_populates="email", cascade="all, delete-orphan")


class AttachmentRecord(Base):
    __tablename__ = "attachments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    email_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("email_messages.id", ondelete="CASCADE"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(255))
    source_reference: Mapped[str] = mapped_column(Text, nullable=False)
    external_attachment_id: Mapped[str | None] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    email: Mapped[EmailMessageRecord] = relationship(back_populates="attachments")


class ProcessingJobRecord(TimestampMixin, Base):
    __tablename__ = "processing_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    email_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("email_messages.id", ondelete="CASCADE"), nullable=False, index=True)
    job_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING")
    error_message: Mapped[str | None] = mapped_column(Text)
    source_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    email: Mapped[EmailMessageRecord] = relationship(back_populates="processing_jobs")


class ClassificationResultRecord(Base):
    __tablename__ = "classification_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    email_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("email_messages.id", ondelete="CASCADE"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    candidate_scores: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    evidence_summary: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    conflict_detected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    resolved_at_stage: Mapped[str] = mapped_column(String(50), nullable=False)
    classifier_version: Mapped[str] = mapped_column(String(80), nullable=False, default="batch1-rule-v1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    email: Mapped[EmailMessageRecord] = relationship(back_populates="classification_results")


class HumanReviewCaseRecord(Base):
    __tablename__ = "human_review_cases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    email_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("email_messages.id", ondelete="CASCADE"), nullable=False, index=True)
    reason_code: Mapped[str] = mapped_column(String(80), nullable=False)
    reason_text: Mapped[str] = mapped_column(Text, nullable=False)
    candidate_scores: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    evidence: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    confidence: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="OPEN")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    email: Mapped[EmailMessageRecord] = relationship(back_populates="human_review_cases")

