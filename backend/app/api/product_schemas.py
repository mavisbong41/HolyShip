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
EmailLifecycleStatus = Literal["ACTIVE", "DELETED", "ARCHIVED"]
OutlookReadState = Literal["READ", "UNREAD", "UNKNOWN"]


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
    human_override_value: Any | None = None
    effective_value: Any | None = None


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
    id: uuid.UUID | None = None
    email_id: uuid.UUID | None = None
    state: Literal["COMPLETED", "BLOCKED"]
    mismatch_found: bool
    mismatched_fields: list[str] = Field(default_factory=list)
    unresolved_fields: list[str] = Field(default_factory=list)
    reason_code: str
    message: str
    fields: list[ProductFieldComparison] = Field(default_factory=list)
    resolution_status: str | None = None
    acknowledged_at: datetime | None = None
    acknowledged_by: str | None = None
    resolved_at: datetime | None = None
    resolved_by: str | None = None
    resolution_notes: str | None = None


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


class ProductEmailLifecycle(BaseModel):
    lifecycle_status: EmailLifecycleStatus = "ACTIVE"
    outlook_read_state: OutlookReadState = "UNKNOWN"
    outlook_categories: list[str] = Field(default_factory=list)
    outlook_folder_id: str | None = None
    outlook_archived: bool = False
    last_outlook_sync_at: datetime | None = None
    outlook_sync_error: str | None = None
    deleted_at: datetime | None = None
    restored_at: datetime | None = None


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
    lifecycle: ProductEmailLifecycle = Field(default_factory=ProductEmailLifecycle)


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
    confirmed_discrepancies_count: int = 0
    unresolved_count: int
    completed_count: int = 0
    awaiting_documents_count: int = 0
    human_review_open_count: int = Field(default=0, description="Number of currently actionable ACTIVE open review cases.")
    failed_count: int = 0
    processing_count: int = 0
    deleted_count: int = 0
    unread_count: int = 0
    sync_error_count: int = 0


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
    outlook_workflow: dict[str, Any] = Field(default_factory=dict)
    reply_policy: dict[str, Any] = Field(default_factory=dict)


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
    canonical_reason: str | None = None
    trigger: str | None = None
    stage: str | None = None
    age_minutes: int = 0
    body: str | None = None
    documents: list[ProductDocument] = Field(default_factory=list)
    overrides: list["ProductReviewOverride"] = Field(default_factory=list)
    actions: list["ProductReviewAction"] = Field(default_factory=list)
    resolutions: list[ProductResolution] = Field(default_factory=list)
    ai_suggestions: list["ProductAISuggestion"] = Field(default_factory=list)
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
    ai_suggestion_id: uuid.UUID | None = None
    created_at: datetime


class ProductAISuggestion(BaseModel):
    id: uuid.UUID
    human_review_case_id: uuid.UUID
    mode: str
    message: str
    document_side: str | None = None
    field: str | None = None
    current_value: str | None = None
    suggested_value: str | None = None
    confidence: float | None = None
    reason: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    provider_name: str
    provider_model: str
    status: str
    created_at: datetime


class AIAssistantAskIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class AIAssistantResponseOut(BaseModel):
    message: str
    mode: str
    suggestion: Any | None = None
    suggestion_id: uuid.UUID | None = None
    provider_name: str
    provider_model: str


class AISuggestionAcceptIn(BaseModel):
    reviewer_label: str = Field(min_length=1, max_length=255)


class AISuggestionApplyEditedIn(BaseModel):
    value: str = Field(min_length=1, max_length=1000)
    reviewer_label: str = Field(min_length=1, max_length=255)
    note: str | None = Field(default=None, max_length=4000)


class AISuggestionDismissIn(BaseModel):
    reviewer_label: str = Field(min_length=1, max_length=255)


class ReviewPlanItemCreateIn(BaseModel):
    document_side: Literal["SI", "BL"]
    field: str
    current_value: Any | None = None
    proposed_value: Any
    reason: str = Field(default="", max_length=4000)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    ai_suggestion_id: uuid.UUID | None = None
    status: Literal["PROPOSED", "APPROVED", "REJECTED"] = "PROPOSED"


class ReviewPlanCreateIn(BaseModel):
    created_by: str | None = Field(default=None, max_length=255)
    items: list[ReviewPlanItemCreateIn] = Field(min_length=1, max_length=14)


class ReviewPlanItemUpdateIn(BaseModel):
    status: Literal["APPROVED", "EDITED", "REJECTED"]
    edited_value: Any | None = None


class ReviewPlanConfirmIn(BaseModel):
    confirmed_by: str = Field(min_length=1, max_length=255)


class ReviewPlanActorIn(BaseModel):
    actor_name: str | None = Field(default=None, max_length=255)


class ProductReviewPlanItem(BaseModel):
    id: uuid.UUID
    ai_suggestion_id: uuid.UUID | None = None
    document_side: Literal["SI", "BL"]
    field: str
    current_value: Any | None = None
    proposed_value: Any
    human_edited_value: Any | None = None
    reason: str
    confidence: float | None = None
    action: str
    status: str
    created_at: datetime
    updated_at: datetime


class ProductReviewPlan(BaseModel):
    id: uuid.UUID
    review_case_id: uuid.UUID
    status: str
    created_by: str | None = None
    confirmed_at: datetime | None = None
    confirmed_by: str | None = None
    applied_comparison_id: uuid.UUID | None = None
    error_message: str | None = None
    items: list[ProductReviewPlanItem]
    created_at: datetime
    updated_at: datetime


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


class CategoryOverrideIn(BaseModel):
    category: ProductCategory
    reviewer_name: str | None = Field(default=None, min_length=1, max_length=255)
    reason: str | None = Field(default=None, max_length=4000)


class OutlookLifecycleReconcileIn(BaseModel):
    email_id: uuid.UUID | None = None
    external_message_id: str | None = Field(default=None, min_length=1, max_length=255)
    source_type: str = Field(default="GRAPH", min_length=1, max_length=50)
    lifecycle_status: Literal["ACTIVE", "DELETED", "RESTORED", "ARCHIVED"] | None = None
    outlook_read_state: OutlookReadState | None = None
    outlook_categories: list[str] | None = Field(default=None, max_length=50)
    outlook_folder_id: str | None = Field(default=None, max_length=512)
    outlook_archived: bool | None = None
    sync_error: str | None = Field(default=None, max_length=4000)
    synced_at: datetime | None = None
    actor_name: str | None = Field(default=None, max_length=255)


class OutlookLifecycleReconcileOut(BaseModel):
    email_id: uuid.UUID
    action: str
    lifecycle: ProductEmailLifecycle


class ProductSyncStatus(BaseModel):
    total_emails: int
    active_count: int
    deleted_count: int
    archived_count: int
    unread_count: int
    sync_error_count: int
    last_outlook_sync_at: datetime | None = None


class ProductReplyWorkflow(BaseModel):
    email_id: uuid.UUID
    status: str
    summary: str | None = None
    key_points: list[str] = Field(default_factory=list)
    draft: str | None = None
    last_instruction: str | None = None
    sent_at: datetime | None = None
    send_error: str | None = None
    provider: str | None = None
    idempotency_key: str | None = None
    generation_mode: str | None = None
    ai_audit: dict[str, Any] | None = None
    updated_at: datetime


class ReplySummaryIn(BaseModel):
    reviewer_name: str | None = Field(default=None, min_length=1, max_length=255)


class ReplyGenerateIn(BaseModel):
    key_points: list[str] = Field(default_factory=list, max_length=12)
    reviewer_name: str | None = Field(default=None, min_length=1, max_length=255)


class ReplyRefineIn(BaseModel):
    draft: str = Field(min_length=1, max_length=8000)
    instruction: str = Field(min_length=1, max_length=1000)
    reviewer_name: str | None = Field(default=None, min_length=1, max_length=255)


class ReplySendIn(BaseModel):
    final_message: str = Field(min_length=1, max_length=8000)
    reviewer_name: str | None = Field(default=None, min_length=1, max_length=255)
    confirmed: bool = False
    idempotency_key: str = Field(min_length=8, max_length=120)


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


DiscrepancyStatus = Literal["OPEN", "ACKNOWLEDGED", "RESOLVED"]


class ProductDiscrepancySummary(BaseModel):
    id: uuid.UUID
    email_id: uuid.UUID
    external_message_id: str
    subject: str
    sender: str | None = None
    received_at: datetime | None = None
    created_at: datetime
    mismatch_count: int = 0
    mismatched_fields: list[str] = Field(default_factory=list)
    resolution_status: DiscrepancyStatus = "OPEN"
    acknowledged_at: datetime | None = None
    acknowledged_by: str | None = None
    resolved_at: datetime | None = None
    resolved_by: str | None = None
    resolution_notes: str | None = None
    comparison_state: str = "COMPLETED"


class DiscrepancyPage(BaseModel):
    items: list[ProductDiscrepancySummary]
    total: int
    open_count: int = 0
    acknowledged_count: int = 0
    resolved_count: int = 0
    skip: int
    limit: int


class DiscrepancyOverrideOut(BaseModel):
    id: uuid.UUID
    comparison_result_id: uuid.UUID
    document_side: str
    field_name: str
    original_field_id: uuid.UUID
    corrected_value: Any
    corrected_canonical_value: Any
    reviewer_name: str | None = None
    note: str | None = None
    active: bool = True
    created_at: datetime


class ProductDiscrepancyDetail(BaseModel):
    discrepancy: ProductDiscrepancySummary
    email: ProductEmailSummary
    email_body: str = ""
    comparison: ProductComparison
    mismatched_fields_detail: list[ProductFieldComparison] = Field(default_factory=list)
    attachments: list[ProductAttachment] = Field(default_factory=list)
    documents: list[ProductDocument] = Field(default_factory=list)
    overrides: list[DiscrepancyOverrideOut] = Field(default_factory=list)
    timeline: list[ProductTimelineEvent] = Field(default_factory=list)


class DiscrepancyAcknowledgeIn(BaseModel):
    operator_name: str | None = Field(default=None, max_length=255)


class DiscrepancyResolveIn(BaseModel):
    operator_name: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=4000)


class DiscrepancyOverrideIn(BaseModel):
    document_side: Literal["SI", "BL"]
    field_name: str
    corrected_value: Any
    reviewer_name: str | None = Field(default=None, max_length=255)
    note: str | None = Field(default=None, max_length=4000)


class DiscrepancyRecompareIn(BaseModel):
    reviewer_name: str | None = Field(default=None, max_length=255)


ProductEmailDetail.model_rebuild()
ProductReview.model_rebuild()
ProductDiscrepancyDetail.model_rebuild()
