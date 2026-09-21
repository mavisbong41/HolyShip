from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


PRODUCT_CANONICAL_FIELDS = (
    "shipper",
    "consignee",
    "notify_party",
    "port_of_loading",
    "port_of_discharge",
    "container_count",
    "gross_weight_kg",
)

ProductStatus = Literal[
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
ProductCategory = Literal[
    "document_comparison",
    "new_si_request",
    "invoice_query",
    "general_message",
    "spam",
]
ComparisonReadiness = Literal["READY_FOR_COMPARISON", "AWAITING_DOCUMENTS", "UNRESOLVED"]
FieldStatus = Literal["MATCH", "MISMATCH", "UNRESOLVED"]


class ProductEvidence(BaseModel):
    document_id: uuid.UUID | None = None
    document_role: str | None = None
    attachment_id: uuid.UUID | None = None
    filename: str | None = None
    page: int | None = None
    text_span: str | None = None
    source_type: str | None = None
    field: str | None = None
    reason: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class ProductValue(BaseModel):
    raw: Any | None = None
    canonical: Any | None = None
    normalized: Any | None = None


class ProductFieldComparison(BaseModel):
    field: str
    si: ProductValue
    bl: ProductValue
    status: FieldStatus
    reason_code: str
    evidence: list[ProductEvidence] = Field(default_factory=list)


class ProductExtractedField(BaseModel):
    field: str
    raw_label: str | None = None
    raw_value: Any | None = None
    canonical_value: Any | None = None
    status: str
    confidence: float = Field(ge=0.0, le=1.0)
    mapping_method: str | None = None
    extraction_method: str | None = None
    source_location: dict[str, Any] = Field(default_factory=dict)
    evidence: list[ProductEvidence] = Field(default_factory=list)


class ProductAttachment(BaseModel):
    id: uuid.UUID
    filename: str
    content_type: str | None = None
    external_attachment_id: str | None = None
    retrieval_status: str
    retrieval_reason_code: str | None = None
    content_sha256: str | None = None


class ProductDocument(BaseModel):
    id: uuid.UUID
    attachment_id: uuid.UUID | None = None
    filename: str
    role: str
    format: str
    source_reference: str
    routing_outcome: str
    role_confidence: float = Field(ge=0.0, le=1.0)
    role_evidence: dict[str, Any] = Field(default_factory=dict)
    validation_outcome: str
    read_status: str | None = None
    reader_used: str | None = None
    extraction_quality: float | None = None
    failure_reason: str | None = None
    fields: list[ProductExtractedField] = Field(default_factory=list)


class ProductComparison(BaseModel):
    state: Literal["COMPLETED", "BLOCKED"]
    mismatch_found: bool
    mismatched_fields: list[str] = Field(default_factory=list)
    unresolved_fields: list[str] = Field(default_factory=list)
    reason_code: str
    message: str
    fields: list[ProductFieldComparison] = Field(default_factory=list)


class ProductClassification(BaseModel):
    category: ProductCategory
    confidence: float = Field(ge=0.0, le=1.0)
    candidate_scores: dict[str, float] = Field(default_factory=dict)
    reason: str
    reason_code: str
    evidence: list[ProductEvidence] = Field(default_factory=list)
    conflict_detected: bool
    resolved_at_stage: str
    comparison_readiness: ComparisonReadiness | None = None
    classifier_version: str
    created_at: datetime


class ProductResolution(BaseModel):
    attempted: bool = True
    purpose: str
    field: str
    accepted: bool
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    evidence: list[ProductEvidence] = Field(default_factory=list)
    provider_name: str | None = None
    model_name: str | None = None
    resolver_version: str | None = None


class ProductTimelineEvent(BaseModel):
    id: uuid.UUID
    old_status: str | None = None
    new_status: str
    reason_code: str
    created_at: datetime


class ProductEmailSummary(BaseModel):
    id: uuid.UUID
    external_message_id: str
    source_type: str
    sender: str | None = None
    subject: str
    received_at: datetime | None = None
    created_at: datetime
    processing_status: ProductStatus
    attachment_count: int
    category: ProductCategory | None = None
    classification_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    comparison_readiness: ComparisonReadiness | None = None
    comparison_state: str | None = None
    mismatch_count: int = 0
    unresolved_count: int = 0
    needs_review: bool = False
    review_id: uuid.UUID | None = None
    review_status: str | None = None
    review_reason: str | None = None


class EmailQueuePage(BaseModel):
    items: list[ProductEmailSummary]
    total: int
    skip: int
    limit: int


class ProductSummary(BaseModel):
    """Product-level summary metrics.

    Metrics represent the current actionable queue state.
    needs_review_count only counts active actionable human review cases (case_origin=ACTIVE and status in OPEN/IN_REVIEW).
    Legacy historical review records do not increment these counts.
    """
    total_emails: int
    status_counts: dict[str, int]
    needs_review_count: int = Field(description="Number of currently actionable ACTIVE review cases.")
    comparison_ready_count: int
    mismatch_count: int
    unresolved_count: int
    completed_count: int = 0
    awaiting_documents_count: int = 0
    human_review_open_count: int = Field(default=0, description="Number of currently actionable ACTIVE open review cases.")
    failed_count: int = 0
    processing_count: int = 0


class ProductEmailDetail(BaseModel):
    email: ProductEmailSummary
    body: str
    recipients: list[str]
    content_hash: str
    attachments: list[ProductAttachment] = Field(default_factory=list)
    classification: ProductClassification | None = None
    documents: list[ProductDocument] = Field(default_factory=list)
    comparison: ProductComparison | None = None
    timeline: list[ProductTimelineEvent] = Field(default_factory=list)
    review: list["ProductReview"] = Field(default_factory=list)
    resolutions: list[ProductResolution] = Field(default_factory=list)


class ProductReview(BaseModel):
    id: uuid.UUID
    email_id: uuid.UUID
    email: ProductEmailSummary | None = None
    document_id: uuid.UUID | None = None
    field: str | None = None
    reason_code: str
    reason_text: str
    status: str
    case_origin: str = "LEGACY"
    workflow_identity: str | None = None
    source_comparison_id: uuid.UUID | None = None
    reviewer_name: str | None = None
    claimed_at: datetime | None = None
    resolution: str | None = None
    notes: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    evidence: list[ProductEvidence] = Field(default_factory=list)
    comparison: ProductComparison | None = None
    priority: Literal["HIGH", "MEDIUM", "LOW"] = "LOW"
    presentation_title: str | None = None
    human_explanation: str | None = None
    affected_fields: list[str] = Field(default_factory=list)
    affected_area: str | None = None
    suggested_action: str | None = None
    semantic_style: str | None = None
    age_minutes: int = 0
    body: str | None = None
    documents: list[ProductDocument] = Field(default_factory=list)
    overrides: list["ProductReviewOverride"] = Field(default_factory=list)
    actions: list["ProductReviewAction"] = Field(default_factory=list)
    resolutions: list[ProductResolution] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime | None = None
    resolved_at: datetime | None = None


class ProductReviewOverride(BaseModel):
    id: uuid.UUID
    document_side: Literal["SI", "BL"]
    field: str
    original_field_id: uuid.UUID
    corrected_value: Any
    corrected_canonical_value: Any
    reviewer_name: str | None = None
    note: str | None = None
    active: bool
    supersedes_override_id: uuid.UUID | None = None
    created_at: datetime


class ProductReviewAction(BaseModel):
    id: uuid.UUID
    action: str
    actor_name: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ReviewClaimIn(BaseModel):
    reviewer_name: str = Field(min_length=1, max_length=255)


class ReviewOverrideIn(BaseModel):
    document_side: Literal["SI", "BL"]
    field: str
    corrected_value: Any
    corrected_canonical_value: Any | None = None
    reviewer_name: str | None = Field(default=None, min_length=1, max_length=255)
    note: str | None = Field(default=None, max_length=4000)


class ReviewResolveIn(BaseModel):
    reviewer_name: str | None = Field(default=None, min_length=1, max_length=255)
    notes: str | None = Field(default=None, max_length=4000)


class ReviewDismissIn(BaseModel):
    reviewer_name: str | None = Field(default=None, min_length=1, max_length=255)
    reason: str = Field(min_length=1, max_length=80)
    notes: str | None = Field(default=None, max_length=4000)


class HumanReviewPage(BaseModel):
    items: list[ProductReview]
    total: int
    skip: int
    limit: int


class ProductEvent(BaseModel):
    event: Literal["EMAIL_PROCESSING_UPDATED"]
    email_id: uuid.UUID
    status: ProductStatus
    category: ProductCategory | None = None
    mismatch_found: bool = False
    updated_at: datetime
    reason_code: str


class ProductReprocessOut(BaseModel):
    email_id: uuid.UUID
    status: str
    external_message_id: str


class ProductIncomingOut(BaseModel):
    external_message_id: str
    status: str
    error: str | None = None


class HumanReviewReconciliation(BaseModel):
    total_emails: int = 0
    processing_status_counts: dict[str, int] = Field(default_factory=dict)
    active_review_status_counts: dict[str, int] = Field(default_factory=dict)
    historical_review_status_counts: dict[str, int] = Field(default_factory=dict)
    emails_with_mismatch: int = 0
    emails_with_unresolved_fields: int = 0


class HumanReviewAnalytics(BaseModel):
    open_count: int = 0
    in_review_count: int = 0
    resolved_count: int = 0
    dismissed_count: int = 0
    resolved_today_count: int = 0
    average_open_age_minutes: float | None = None
    priority_distribution: dict[str, int] = Field(default_factory=dict)
    reason_distribution: dict[str, int] = Field(default_factory=dict)
    most_reviewed_fields: dict[str, int] = Field(default_factory=dict)
    most_corrected_fields: dict[str, int] = Field(default_factory=dict)
    correction_reasons: dict[str, int] = Field(default_factory=dict)


ProductEmailDetail.model_rebuild()
ProductReview.model_rebuild()
