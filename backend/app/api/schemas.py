from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal, Optional

from pydantic import BaseModel, Field


EmailCategoryValue = Literal[
    "document_comparison",
    "new_si_request",
    "invoice_query",
    "general_message",
    "spam",
]
ComparisonReadinessValue = Literal[
    "READY_FOR_COMPARISON",
    "AWAITING_DOCUMENTS",
    "UNRESOLVED",
]
ProcessingStatusValue = Literal[
    "NEW",
    "QUEUED",
    "CLASSIFYING",
    "CLASSIFIED",
    "AWAITING_DOCUMENTS",
    "RETRIEVING_ATTACHMENTS",
    "EXTRACTING",
    "COMPARING",
    "COMPLETED",
    "BLOCKED",
    "FAILED",
]
ConfidenceValue = Annotated[float, Field(ge=0.0, le=1.0)]


# ---------------------------------------------------------------------------
# Email schemas
# ---------------------------------------------------------------------------

class AttachmentOut(BaseModel):
    id: uuid.UUID
    filename: str
    content_type: Optional[str]
    source_reference: str
    external_attachment_id: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class EmailOut(BaseModel):
    id: uuid.UUID
    external_message_id: str
    source_type: str
    sender: Optional[str]
    recipients: list[str]
    subject: str
    body: str
    received_at: Optional[datetime]
    content_hash: str
    processing_status: ProcessingStatusValue
    created_at: datetime
    updated_at: datetime
    attachments: list[AttachmentOut] = []

    model_config = {"from_attributes": True}


class EmailListItem(BaseModel):
    id: uuid.UUID
    external_message_id: str
    source_type: str
    sender: Optional[str]
    subject: str
    processing_status: ProcessingStatusValue
    received_at: Optional[datetime]
    created_at: datetime
    attachment_count: int = 0

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Classification schemas
# ---------------------------------------------------------------------------

class ClassificationOut(BaseModel):
    id: uuid.UUID
    email_id: uuid.UUID
    category: EmailCategoryValue
    confidence: ConfidenceValue
    candidate_scores: dict[str, float]
    reason: str
    reason_code: str
    evidence_summary: dict[str, Any]
    conflict_detected: bool
    resolved_at_stage: str
    comparison_readiness: Optional[ComparisonReadinessValue]
    classifier_version: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Human review schemas
# ---------------------------------------------------------------------------

class HumanReviewOut(BaseModel):
    id: uuid.UUID
    email_id: uuid.UUID
    reason_code: str
    reason_text: str
    candidate_scores: dict[str, float]
    evidence: dict[str, Any]
    confidence: Optional[float]
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Sync schemas
# ---------------------------------------------------------------------------

class SyncRequest(BaseModel):
    source: str = "static"          # "static" | "http"
    organizer_http_url: Optional[str] = None


class SyncReportOut(BaseModel):
    total: int
    ingested: int
    skipped: int
    classified: int
    human_review: int
    failed: int


class SyncProgressOut(BaseModel):
    """Final progress snapshot for the synchronous initial-sync request."""

    total: int
    processed: int
    percent: float = Field(ge=0.0, le=100.0)
    ingested: int
    skipped: int
    failed: int


class InitialSyncOut(SyncReportOut):
    job_id: uuid.UUID
    status: Literal["COMPLETED"] = "COMPLETED"
    progress: SyncProgressOut


# ---------------------------------------------------------------------------
# Incoming email schema
# ---------------------------------------------------------------------------

class IncomingAttachmentIn(BaseModel):
    filename: str
    source_reference: Optional[str] = None
    content_type: Optional[str] = None
    external_attachment_id: Optional[str] = None
    content_base64: Optional[str] = None


class IncomingEmailIn(BaseModel):
    external_message_id: Optional[str] = None
    sender: Optional[str] = None
    recipients: list[str] = []
    subject: str
    body: str = ""
    attachments: list[IncomingAttachmentIn] = []
