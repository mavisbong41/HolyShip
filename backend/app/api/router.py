from __future__ import annotations

import base64
import binascii
import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.app.api.deps import get_session, get_settings_dep
from backend.app.api.schemas import (
    ClassificationOut,
    EmailListItem,
    EmailOut,
    HumanReviewOut,
    InitialSyncOut,
    IncomingEmailIn,
    SyncReportOut,
    SyncProgressOut,
    SyncRequest,
)
from backend.app.core.config import Settings
from backend.app.ingestion.models import (
    AttachmentMetadata,
    EmailMessage,
    IncomingAttachmentInput,
    IncomingEmailPayload,
)
from backend.app.ingestion.sources import (
    IncomingApiSource,
    OrganizerHttpSource,
    StaticBundleSource,
    map_incoming_payload,
)
from backend.app.storage.database import SessionLocal
from backend.app.storage.models import (
    ClassificationResultRecord,
    EmailMessageRecord,
    HumanReviewCaseRecord,
    ProcessingEventRecord,
    utcnow,
)
from backend.app.resolution.runtime import get_configured_resolution_executor_factory
from backend.app.discrepancy.service import DiscrepancyConflictError, DiscrepancyService
from backend.app.review.service import HumanReviewService, ReviewConflictError
from backend.app.sync.service import SyncService
from backend.app.api.analytics_helper import get_human_review_analytics, get_human_review_reconciliation
from backend.app.api.product_queries import (
    get_email_detail,
    get_human_review as get_product_human_review,
    get_product_discrepancy_detail,
    get_product_summary,
    get_product_sync_status,
    list_email_queue,
    list_human_reviews as list_product_human_reviews,
    list_processing_events,
    list_product_discrepancies,
)
from backend.app.ai_review.service import AIReviewService
from backend.app.api.product_schemas import (
    AIAssistantAskIn,
    AIAssistantResponseOut,
    AISuggestionAcceptIn,
    AISuggestionApplyEditedIn,
    AISuggestionDismissIn,
    CategoryOverrideIn,
    ComparisonReadiness,
    DiscrepancyAcknowledgeIn,
    DiscrepancyOverrideIn,
    DiscrepancyPage,
    DiscrepancyRecompareIn,
    DiscrepancyResolveIn,
    EmailQueuePage,
    HumanReviewAnalytics,
    HumanReviewPage,
    HumanReviewReconciliation,
    ProductDiscrepancyDetail,
    ProductEmailDetail,
    ProductEvent,
    ProductIncomingOut,
    OutlookLifecycleReconcileIn,
    OutlookLifecycleReconcileOut,
    ProductEmailLifecycle,
    ProductReprocessOut,
    ProductReplyWorkflow,
    ProductReview,
    ProductSyncStatus,
    ProductSummary,
    ReplyGenerateIn,
    ReplyRefineIn,
    ReplySendIn,
    ReplySummaryIn,
    ReviewClaimIn,
    ReviewDismissIn,
    ReviewOverrideIn,
    ReviewResolveIn,
)

router = APIRouter()


def _reprocess_source(
    record: EmailMessageRecord,
    settings: Settings,
) -> tuple[EmailMessage, object]:
    attachments = [
        AttachmentMetadata(
            filename=attachment.filename,
            source_reference=attachment.source_reference,
            content_type=attachment.content_type,
            external_attachment_id=attachment.external_attachment_id,
        )
        for attachment in record.attachments
    ]
    message = EmailMessage(
        external_message_id=record.external_message_id,
        source_type=record.source_type,
        sender=record.sender,
        recipients=list(record.recipients or []),
        subject=record.subject,
        body=record.body,
        received_at=record.received_at,
        attachments=attachments,
        source_metadata=dict(record.source_metadata or {}),
        content_hash=record.content_hash,
    )
    if record.source_type == "STATIC_BUNDLE":
        return message, StaticBundleSource(settings.resolved_bundle_path)
    if record.source_type == "ORGANIZER_HTTP":
        base_url = (record.source_metadata or {}).get("base_url")
        if not base_url:
            raise ValueError("ORGANIZER_HTTP record has no persisted provider base URL")
        return message, OrganizerHttpSource(
            base_url,
            timeout_seconds=settings.organizer_http_timeout_seconds,
            retry_policy=settings.retry_policy,
        )
    # Incoming and Graph messages can be reclassified safely. Attachment
    # reprocessing will fail closed if the original source did not persist
    # content bytes; it must never fabricate a document result.
    return message, IncomingApiSource(
        IncomingEmailPayload(
            external_message_id=message.external_message_id,
            sender=message.sender,
            recipients=message.recipients,
            subject=message.subject,
            body=message.body,
            received_at=message.received_at,
            attachments=[
                IncomingAttachmentInput(
                    filename=item.filename,
                    source_reference=item.source_reference,
                    content_type=item.content_type,
                    external_attachment_id=item.external_attachment_id,
                )
                for item in attachments
            ],
            source_metadata=message.source_metadata,
        )
    )


def _build_sync_service(session: Session, settings: Settings) -> SyncService:
    return SyncService(
        session,
        confidence_threshold=settings.classification_threshold,
        margin_threshold=settings.classification_margin_threshold,
        max_workers=settings.sync_max_workers,
        session_factory=SessionLocal,
        retry_max_attempts=settings.retry_max_attempts,
        semantic_resolver_timeout_seconds=settings.semantic_resolver_timeout_seconds,
        extraction_max_workers=settings.extraction_max_workers,
        ocr_timeout_seconds=settings.ocr_timeout_seconds,
        ocr_max_calls=settings.ocr_max_calls,
        ocr_max_concurrent_calls=settings.ocr_max_concurrent_calls,
        ocr_tesseract_cmd=settings.ocr_tesseract_cmd,
        resolution_executor_factory=get_configured_resolution_executor_factory(settings),
    )


# ---------------------------------------------------------------------------
# GET /api/health
# ---------------------------------------------------------------------------

@router.get("/health")
def health():
    return {"ok": True, "service": "HolyShip Batch 1"}


# ---------------------------------------------------------------------------
# POST /api/sync
# ---------------------------------------------------------------------------

@router.post("/sync", response_model=SyncReportOut)
def sync(
    body: SyncRequest = SyncRequest(),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
):
    """
    Pull emails from the organizer source and classify them.

    source="static"  → reads from ORGANIZER_BUNDLE_PATH (default)
    source="http"    → reads from organizer Docker HTTP server
    """
    svc = _build_sync_service(session, settings)

    if body.source == "http":
        if not body.organizer_http_url:
            raise HTTPException(
                status_code=422,
                detail="organizer_http_url is required when source=http",
            )
        email_source = OrganizerHttpSource(
            body.organizer_http_url,
            timeout_seconds=settings.organizer_http_timeout_seconds,
            retry_policy=settings.retry_policy,
        )
    else:
        email_source = StaticBundleSource(settings.resolved_bundle_path)

    report = svc.sync(email_source, force=body.force)
    return SyncReportOut(
        total=report.total,
        ingested=report.ingested,
        skipped=report.skipped,
        classified=report.classified,
        human_review=report.human_review,
        failed=report.failed,
    )


# ---------------------------------------------------------------------------
# GET /api/emails
# ---------------------------------------------------------------------------

@router.get("/emails", response_model=list[EmailListItem])
def list_emails(
    skip: int = 0,
    limit: int = 100,
    session: Session = Depends(get_session),
):
    """List ingested emails (newest first, paginated)."""
    rows = session.scalars(
        select(EmailMessageRecord)
        .options(selectinload(EmailMessageRecord.attachments))
        .order_by(EmailMessageRecord.created_at.desc())
        .offset(skip)
        .limit(limit)
    ).all()

    return [
        EmailListItem(
            id=r.id,
            external_message_id=r.external_message_id,
            source_type=r.source_type,
            sender=r.sender,
            subject=r.subject,
            processing_status=r.processing_status,
            received_at=r.received_at,
            created_at=r.created_at,
            attachment_count=len(r.attachments),
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# GET /api/emails/{id}
# ---------------------------------------------------------------------------

@router.get("/emails/{email_id}", response_model=EmailOut)
def get_email(
    email_id: uuid.UUID,
    session: Session = Depends(get_session),
):
    record = session.get(
        EmailMessageRecord,
        email_id,
        options=[selectinload(EmailMessageRecord.attachments)],
    )
    if not record:
        raise HTTPException(status_code=404, detail="Email not found")
    return record


# ---------------------------------------------------------------------------
# GET /api/emails/{id}/classification
# ---------------------------------------------------------------------------

@router.get("/emails/{email_id}/classification", response_model=ClassificationOut)
def get_email_classification(
    email_id: uuid.UUID,
    session: Session = Depends(get_session),
):
    """Return the latest classification result for an email."""
    result = session.scalar(
        select(ClassificationResultRecord)
        .where(ClassificationResultRecord.email_id == email_id)
        .order_by(ClassificationResultRecord.created_at.desc())
    )
    if not result:
        raise HTTPException(
            status_code=404,
            detail="No classification result found for this email",
        )
    return result


# ---------------------------------------------------------------------------
# GET /api/human-review
# ---------------------------------------------------------------------------

@router.get("/human-review", response_model=list[HumanReviewOut])
def list_human_review(
    status: str | None = None,
    skip: int = 0,
    limit: int = 100,
    session: Session = Depends(get_session),
):
    """List human review cases, optionally filtered by status (OPEN / RESOLVED)."""
    q = select(HumanReviewCaseRecord).order_by(HumanReviewCaseRecord.created_at.desc())
    if status:
        q = q.where(HumanReviewCaseRecord.status == status.upper())
    rows = session.scalars(q.offset(skip).limit(limit)).all()
    return list(rows)


# ---------------------------------------------------------------------------
# GET /api/human-review/{id}
# ---------------------------------------------------------------------------

@router.get("/human-review/{review_id}", response_model=HumanReviewOut)
def get_human_review(
    review_id: uuid.UUID,
    session: Session = Depends(get_session),
):
    record = session.get(HumanReviewCaseRecord, review_id)
    if not record:
        raise HTTPException(status_code=404, detail="Human review case not found")
    return record


# ---------------------------------------------------------------------------
# POST /api/email/incoming
# ---------------------------------------------------------------------------

@router.post("/email/incoming", response_model=dict)
def receive_incoming_email(
    payload: IncomingEmailIn,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
):
    """
    Accept a newly arriving email (webhook / manual submission).
    Runs EXACTLY the same classification pipeline as the batch sync.
    """
    attachment_contents: dict[str, bytes] = {}
    incoming_attachments: list[IncomingAttachmentInput] = []
    for attachment in payload.attachments:
        source_reference = attachment.source_reference or attachment.filename
        if attachment.content_base64 is not None:
            max_encoded_length = 4 * ((settings.max_attachment_bytes + 2) // 3)
            if len(attachment.content_base64) > max_encoded_length:
                raise HTTPException(
                    status_code=413,
                    detail=(
                        "Attachment content exceeds the configured "
                        f"{settings.max_attachment_bytes}-byte limit"
                    ),
                )
            try:
                content = base64.b64decode(
                    attachment.content_base64,
                    validate=True,
                )
            except (binascii.Error, ValueError) as exc:
                raise HTTPException(
                    status_code=422,
                    detail=f"Invalid base64 attachment content for {attachment.filename}",
                ) from exc
            if len(content) > settings.max_attachment_bytes:
                raise HTTPException(
                    status_code=413,
                    detail=(
                        "Attachment content exceeds the configured "
                        f"{settings.max_attachment_bytes}-byte limit"
                    ),
                )
            attachment_contents[source_reference] = content
        incoming_attachments.append(
            IncomingAttachmentInput(
                filename=attachment.filename,
                source_reference=source_reference,
                content_type=attachment.content_type,
                external_attachment_id=attachment.external_attachment_id,
            )
        )

    incoming = IncomingEmailPayload(
        external_message_id=payload.external_message_id,
        sender=payload.sender,
        recipients=payload.recipients,
        subject=payload.subject,
        body=payload.body,
        attachments=incoming_attachments,
    )
    message: EmailMessage = map_incoming_payload(incoming)

    svc = _build_sync_service(session, settings)
    outcome = svc.sync_one(
        message,
        IncomingApiSource(incoming, attachment_contents=attachment_contents),
    )

    return {
        "external_message_id": outcome.external_message_id,
        "status": outcome.status,
        "error": outcome.error,
    }


# ---------------------------------------------------------------------------
# Product-facing v1 API
# ---------------------------------------------------------------------------

@router.get(
    "/v1/emails",
    response_model=EmailQueuePage,
    summary="List the dashboard email queue",
)
def product_email_queue(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    status: str | None = Query(None),
    category: str | None = Query(None),
    comparison_readiness: ComparisonReadiness | None = Query(None),
    needs_review: bool | None = Query(None),
    review_status: Literal["OPEN", "IN_REVIEW", "RESOLVED", "DISMISSED"] | None = Query(None),
    comparison_state: Literal["COMPLETED", "BLOCKED"] | None = Query(None),
    has_mismatch: bool | None = Query(None),
    search: str | None = Query(None, min_length=1, max_length=200),
    received_from: datetime | None = Query(None),
    received_to: datetime | None = Query(None),
    lifecycle_status: Literal["ACTIVE", "DELETED", "ARCHIVED"] | None = Query(None),
    session: Session = Depends(get_session),
):
    valid_statuses = {
        "NEW", "QUEUED", "CLASSIFYING", "CLASSIFIED", "AWAITING_DOCUMENTS",
        "RETRIEVING_ATTACHMENTS", "EXTRACTING", "COMPARING", "COMPLETED", "BLOCKED", "FAILED",
    }
    valid_categories = {
        "document_comparison", "new_si_request", "invoice_query", "general_message", "spam",
    }
    if status is not None and status not in valid_statuses:
        raise HTTPException(status_code=422, detail="Unsupported processing status")
    if category is not None and category not in valid_categories:
        raise HTTPException(status_code=422, detail="Unsupported email category")
    if received_from and received_to and received_from > received_to:
        raise HTTPException(status_code=422, detail="received_from must not be after received_to")
    return list_email_queue(
        session,
        skip=skip,
        limit=limit,
        status=status,
        category=category,
        comparison_readiness=comparison_readiness,
        needs_review=needs_review,
        review_status=review_status,
        comparison_state=comparison_state,
        has_mismatch=has_mismatch,
        search=search,
        received_from=received_from,
        received_to=received_to,
        lifecycle_status=lifecycle_status,
    )


@router.get(
    "/v1/summary",
    response_model=ProductSummary,
    summary="Return persisted dashboard counts",
)
def product_summary(session: Session = Depends(get_session)):
    return get_product_summary(session)


@router.get(
    "/v1/sync/status",
    response_model=ProductSyncStatus,
    summary="Return Outlook lifecycle synchronisation status",
)
def product_sync_status(session: Session = Depends(get_session)):
    return get_product_sync_status(session)


@router.get(
    "/v1/emails/{email_id}/detail",
    response_model=ProductEmailDetail,
    summary="Return a unified product email detail",
)
def product_email_detail(
    email_id: uuid.UUID,
    session: Session = Depends(get_session),
):
    detail = get_email_detail(session, email_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Email not found")
    return detail


@router.get(
    "/v1/emails/{email_id}",
    response_model=ProductEmailDetail,
    summary="Return the unified product email detail",
)
def product_email_detail_alias(
    email_id: uuid.UUID,
    session: Session = Depends(get_session),
):
    return product_email_detail(email_id, session)


def _email_or_404(session: Session, email_id: uuid.UUID) -> EmailMessageRecord:
    record = session.get(EmailMessageRecord, email_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Email not found")
    return record


def _append_outlook_event(
    session: Session,
    record: EmailMessageRecord,
    reason_code: str,
    *,
    details: dict | None = None,
) -> None:
    metadata = dict(record.source_metadata or {})
    events = list(metadata.get("outlook_events") or [])
    events.append(
        {
            "reason_code": reason_code,
            "created_at": utcnow().isoformat(),
            "details": details or {},
        }
    )
    metadata["outlook_events"] = events[-50:]
    record.source_metadata = metadata
    session.add(
        ProcessingEventRecord(
            email_id=record.id,
            old_status=record.processing_status,
            new_status=record.processing_status,
            reason_code=reason_code,
        )
    )


def _workflow_payload(record: EmailMessageRecord, **updates) -> ProductReplyWorkflow:
    metadata = dict(record.source_metadata or {})
    workflow = dict(metadata.get("outlook_workflow") or {})
    workflow.update(updates)
    workflow["updated_at"] = utcnow().isoformat()
    metadata["outlook_workflow"] = workflow
    record.source_metadata = metadata
    return ProductReplyWorkflow(email_id=record.id, **workflow)


def _product_lifecycle(record: EmailMessageRecord) -> ProductEmailLifecycle:
    return ProductEmailLifecycle(
        lifecycle_status=record.lifecycle_status,
        outlook_read_state=record.outlook_read_state,
        outlook_categories=list(record.outlook_categories or []),
        outlook_folder_id=record.outlook_folder_id,
        outlook_archived=record.outlook_archived,
        last_outlook_sync_at=record.last_outlook_sync_at,
        outlook_sync_error=record.outlook_sync_error,
        deleted_at=record.deleted_at,
        restored_at=record.restored_at,
    )


def _append_lifecycle_event(
    session: Session,
    record: EmailMessageRecord,
    reason_code: str,
    *,
    details: dict | None = None,
) -> None:
    session.add(
        ProcessingEventRecord(
            email_id=record.id,
            old_status=record.processing_status,
            new_status=record.processing_status,
            reason_code=reason_code,
        )
    )
    metadata = dict(record.source_metadata or {})
    events = list(metadata.get("outlook_events") or [])
    events.append(
        {
            "reason_code": reason_code,
            "created_at": utcnow().isoformat(),
            "details": details or {},
        }
    )
    metadata["outlook_events"] = events[-50:]
    record.source_metadata = metadata


def _find_lifecycle_record(
    session: Session,
    payload: OutlookLifecycleReconcileIn,
) -> EmailMessageRecord | None:
    if payload.email_id:
        return session.get(EmailMessageRecord, payload.email_id)
    if not payload.external_message_id:
        return None
    return session.scalar(
        select(EmailMessageRecord).where(
            EmailMessageRecord.source_type == payload.source_type,
            EmailMessageRecord.external_message_id == payload.external_message_id,
        )
    )


@router.post(
    "/v1/outlook/reconcile",
    response_model=OutlookLifecycleReconcileOut,
    summary="Reconcile Outlook email lifecycle state into HolyShip",
)
def product_outlook_reconcile(
    payload: OutlookLifecycleReconcileIn,
    session: Session = Depends(get_session),
):
    record = _find_lifecycle_record(session, payload)
    if record is None:
        raise HTTPException(status_code=404, detail="Email not found for Outlook reconciliation")

    now = utcnow()
    previous_lifecycle = record.lifecycle_status
    changed_reasons: list[str] = []

    if payload.lifecycle_status:
        requested = payload.lifecycle_status
        if requested == "DELETED":
            record.lifecycle_status = "DELETED"
            record.deleted_at = record.deleted_at or now
            if previous_lifecycle != "DELETED":
                changed_reasons.append("OUTLOOK_EMAIL_DELETED")
            else:
                changed_reasons.append("OUTLOOK_LIFECYCLE_RECONCILED")
        elif requested == "RESTORED":
            record.lifecycle_status = "ACTIVE"
            record.outlook_sync_error = None
            if previous_lifecycle == "DELETED":
                record.restored_at = now
                changed_reasons.append("OUTLOOK_EMAIL_RESTORED")
            else:
                changed_reasons.append("OUTLOOK_LIFECYCLE_RECONCILED")
        elif requested == "ARCHIVED":
            record.lifecycle_status = "ARCHIVED"
            record.outlook_archived = True
            if previous_lifecycle != "ARCHIVED":
                changed_reasons.append("OUTLOOK_EMAIL_ARCHIVED")
            else:
                changed_reasons.append("OUTLOOK_LIFECYCLE_RECONCILED")
        elif requested == "ACTIVE":
            record.lifecycle_status = "ACTIVE"
            record.outlook_archived = bool(payload.outlook_archived) if payload.outlook_archived is not None else False
            if previous_lifecycle == "DELETED":
                record.restored_at = now
                changed_reasons.append("OUTLOOK_EMAIL_RESTORED")
            else:
                changed_reasons.append("OUTLOOK_LIFECYCLE_RECONCILED")

    if payload.outlook_read_state and payload.outlook_read_state != record.outlook_read_state:
        record.outlook_read_state = payload.outlook_read_state
        changed_reasons.append("OUTLOOK_READ_STATE_SYNCED")
    if payload.outlook_categories is not None:
        categories = [item.strip() for item in payload.outlook_categories if item.strip()]
        if categories != list(record.outlook_categories or []):
            record.outlook_categories = categories
            changed_reasons.append("OUTLOOK_CATEGORY_SYNCED")
    if payload.outlook_folder_id is not None and payload.outlook_folder_id != record.outlook_folder_id:
        record.outlook_folder_id = payload.outlook_folder_id
        changed_reasons.append("OUTLOOK_FOLDER_SYNCED")
    if payload.outlook_archived is not None and payload.outlook_archived != record.outlook_archived:
        record.outlook_archived = payload.outlook_archived
        if payload.outlook_archived and record.lifecycle_status == "ACTIVE":
            record.lifecycle_status = "ARCHIVED"
        elif not payload.outlook_archived and record.lifecycle_status == "ARCHIVED":
            record.lifecycle_status = "ACTIVE"
        changed_reasons.append("OUTLOOK_ARCHIVE_STATE_SYNCED")

    record.last_outlook_sync_at = payload.synced_at or now
    record.outlook_sync_error = payload.sync_error
    if payload.sync_error:
        changed_reasons.append("OUTLOOK_SYNC_FAILED")

    reason_code = changed_reasons[0] if changed_reasons else "OUTLOOK_LIFECYCLE_RECONCILED"
    _append_lifecycle_event(
        session,
        record,
        reason_code,
        details={
            "all_reason_codes": changed_reasons or [reason_code],
            "actor_name": payload.actor_name,
            "lifecycle_status": record.lifecycle_status,
            "outlook_read_state": record.outlook_read_state,
            "outlook_categories": record.outlook_categories,
            "previous_lifecycle_status": previous_lifecycle,
            "sync_error": bool(payload.sync_error),
        },
    )
    session.commit()
    session.refresh(record)
    return OutlookLifecycleReconcileOut(
        email_id=record.id,
        action=reason_code,
        lifecycle=_product_lifecycle(record),
    )


def _reply_seed_points(detail: ProductEmailDetail) -> list[str]:
    points: list[str] = []
    if detail.comparison:
        if detail.comparison.mismatched_fields:
            fields = ", ".join(detail.comparison.mismatched_fields)
            points.append(f"Acknowledge discrepancy in {fields}.")
        if detail.comparison.unresolved_fields:
            fields = ", ".join(detail.comparison.unresolved_fields)
            points.append(f"Confirm pending review for {fields}.")
        if not detail.comparison.mismatch_found and not detail.comparison.unresolved_fields:
            points.append("Confirm SI and Draft BL fields match.")
    if not points and detail.email.category:
        points.append(f"Acknowledge the {detail.email.category.replace('_', ' ')} request.")
    points.append("State that HolyShip verification has been completed or is being handled.")
    return points[:6]


def _draft_from_points(points: list[str]) -> str:
    body = "\n".join(f"- {point}" for point in points if point.strip())
    return (
        "Dear Customer,\n\n"
        "Thank you for your email. We have reviewed the case in HolyShip.\n\n"
        f"{body}\n\n"
        "We will proceed according to the confirmed review outcome.\n\n"
        "Best regards,\nHolyShip Operations"
    )


@router.patch(
    "/v1/emails/{email_id}/category",
    response_model=ProductEmailDetail,
    summary="Apply a manual category correction from Dashboard or Outlook",
)
def product_email_category_override(
    email_id: uuid.UUID,
    payload: CategoryOverrideIn,
    session: Session = Depends(get_session),
):
    record = _email_or_404(session, email_id)
    existing_count = len(record.classification_results or [])
    classifier_version = f"manual-category-v1-{existing_count + 1}"
    session.add(
        ClassificationResultRecord(
            email_id=record.id,
            category=payload.category,
            confidence=1.0,
            candidate_scores={payload.category: 1.0},
            reason=payload.reason or "Manual category correction from Outlook/Dashboard.",
            reason_code="MANUAL_CATEGORY_OVERRIDE",
            evidence_summary={
                "reviewer_name": payload.reviewer_name,
                "source": "outlook_or_dashboard",
            },
            conflict_detected=False,
            resolved_at_stage="human_override",
            comparison_readiness="UNRESOLVED" if payload.category == "document_comparison" else None,
            classifier_version=classifier_version,
            source_content_hash=record.content_hash,
        )
    )
    _append_outlook_event(
        session,
        record,
        "MANUAL_CATEGORY_OVERRIDE",
        details={"category": payload.category, "reviewer_name": payload.reviewer_name},
    )
    session.commit()
    detail = get_email_detail(session, email_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Email not found")
    return detail


@router.post(
    "/v1/emails/{email_id}/reply/summary",
    response_model=ProductReplyWorkflow,
    summary="Create editable reply summary and key points for an Outlook case",
)
def product_reply_summary(
    email_id: uuid.UUID,
    payload: ReplySummaryIn,
    session: Session = Depends(get_session),
):
    record = _email_or_404(session, email_id)
    detail = get_email_detail(session, email_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Email not found")
    summary = f"{detail.email.subject} — {detail.comparison.message if detail.comparison else 'case reviewed in HolyShip'}"
    key_points = _reply_seed_points(detail)
    workflow = _workflow_payload(
        record,
        status="KEY_POINTS_READY",
        summary=summary,
        key_points=key_points,
        draft=None,
        last_instruction=None,
        sent_at=None,
    )
    _append_outlook_event(session, record, "REPLY_KEY_POINTS_CREATED", details={"reviewer_name": payload.reviewer_name})
    session.commit()
    return workflow


@router.post(
    "/v1/emails/{email_id}/reply/generate",
    response_model=ProductReplyWorkflow,
    summary="Generate an editable reply draft from approved key points",
)
def product_reply_generate(
    email_id: uuid.UUID,
    payload: ReplyGenerateIn,
    session: Session = Depends(get_session),
):
    record = _email_or_404(session, email_id)
    points = [point.strip() for point in payload.key_points if point.strip()]
    if not points:
        detail = get_email_detail(session, email_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="Email not found")
        points = _reply_seed_points(detail)
    workflow = _workflow_payload(
        record,
        status="DRAFT_READY",
        key_points=points,
        draft=_draft_from_points(points),
    )
    _append_outlook_event(session, record, "REPLY_DRAFT_GENERATED", details={"reviewer_name": payload.reviewer_name})
    session.commit()
    return workflow


@router.post(
    "/v1/emails/{email_id}/reply/refine",
    response_model=ProductReplyWorkflow,
    summary="Refine an editable reply draft after user instruction",
)
def product_reply_refine(
    email_id: uuid.UUID,
    payload: ReplyRefineIn,
    session: Session = Depends(get_session),
):
    record = _email_or_404(session, email_id)
    instruction = payload.instruction.strip()
    refined = payload.draft.strip()
    if "short" in instruction.lower() or "concise" in instruction.lower():
        refined = "\n".join(line for line in refined.splitlines() if line.strip())[:1200]
    else:
        refined = f"{refined}\n\nNote: {instruction}"
    workflow = _workflow_payload(
        record,
        status="DRAFT_REFINED",
        draft=refined,
        last_instruction=instruction,
    )
    _append_outlook_event(session, record, "REPLY_DRAFT_REFINED", details={"reviewer_name": payload.reviewer_name})
    session.commit()
    return workflow


@router.post(
    "/v1/emails/{email_id}/reply/send",
    response_model=ProductReplyWorkflow,
    summary="Record explicit human-confirmed Outlook reply send",
)
def product_reply_send(
    email_id: uuid.UUID,
    payload: ReplySendIn,
    session: Session = Depends(get_session),
):
    record = _email_or_404(session, email_id)
    sent_at = utcnow()
    workflow = _workflow_payload(
        record,
        status="SENT",
        draft=payload.final_message,
        sent_at=sent_at.isoformat(),
    )
    _append_outlook_event(session, record, "REPLY_SENT_CONFIRMED", details={"reviewer_name": payload.reviewer_name})
    session.commit()
    return workflow


@router.get(
    "/v1/human-review-analytics",
    response_model=HumanReviewAnalytics,
    summary="Get human review analytics",
)
def product_human_review_analytics(session: Session = Depends(get_session)):
    return get_human_review_analytics(session)

@router.get(
    "/v1/human-review-reconciliation",
    response_model=HumanReviewReconciliation,
    summary="Get persisted Human Review reconciliation diagnostics",
)
def product_human_review_reconciliation(session: Session = Depends(get_session)):
    return get_human_review_reconciliation(session)


@router.get(
    "/v1/human-review",
    response_model=HumanReviewPage,
    summary="List reviewer-ready cases",
)
def product_human_review_queue(
    status: Literal["OPEN", "IN_REVIEW", "RESOLVED", "DISMISSED"] | None = Query(None),
    reason: str | None = Query(None, max_length=80),
    reviewer: str | None = Query(None, max_length=255),
    search: str | None = Query(None, min_length=1, max_length=200),
    active_only: bool = Query(True),
    sort: Literal["priority", "age", "oldest", "newest"] | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    session: Session = Depends(get_session),
):
    return list_product_human_reviews(
        session,
        status=status,
        reason=reason,
        reviewer=reviewer,
        search=search,
        active_only=active_only,
        sort=sort,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/v1/human-review/{review_id}",
    response_model=ProductReview,
    summary="Return reviewer-ready case detail",
)
def product_human_review_detail(
    review_id: uuid.UUID,
    session: Session = Depends(get_session),
):
    review = get_product_human_review(session, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Human review case not found")

    return review


def _review_mutation_response(session: Session, review_id: uuid.UUID) -> ProductReview:
    session.commit()
    # Mutation endpoints return the database truth, including newly appended
    # overrides/actions, even when the request-scoped identity map previously
    # loaded the review graph.
    session.expire_all()
    review = get_product_human_review(session, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Human review case not found")

    return review


def _run_review_mutation(operation):
    try:
        return operation()
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ReviewConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/v1/human-review/{review_id}/claim",
    response_model=ProductReview,
    summary="Claim an open Human Review case",
)
def product_human_review_claim(
    review_id: uuid.UUID,
    payload: ReviewClaimIn,
    session: Session = Depends(get_session),
):
    _run_review_mutation(
        lambda: HumanReviewService(session).claim(
            review_id,
            reviewer_name=payload.reviewer_name,
        )
    )
    return _review_mutation_response(session, review_id)


@router.post(
    "/v1/human-review/{review_id}/overrides",
    response_model=ProductReview,
    summary="Add or replace an immutable Human Review field override",
)
def product_human_review_override(
    review_id: uuid.UUID,
    payload: ReviewOverrideIn,
    session: Session = Depends(get_session),
):
    _run_review_mutation(
        lambda: HumanReviewService(session).add_override(
            review_id,
            document_side=payload.document_side,
            field_name=payload.field,
            corrected_value=payload.corrected_value,
            corrected_canonical_value=payload.corrected_canonical_value,
            reviewer_name=payload.reviewer_name,
            note=payload.note,
        )
    )
    return _review_mutation_response(session, review_id)


@router.post(
    "/v1/human-review/{review_id}/resolve",
    response_model=ProductReview,
    summary="Resolve a Human Review case by creating a new comparison version",
)
def product_human_review_resolve(
    review_id: uuid.UUID,
    payload: ReviewResolveIn,
    session: Session = Depends(get_session),
):
    _run_review_mutation(
        lambda: HumanReviewService(session).resolve_and_recompare(
            review_id,
            reviewer_name=payload.reviewer_name,
            notes=payload.notes,
        )
    )
    return _review_mutation_response(session, review_id)


@router.post(
    "/v1/human-review/{review_id}/dismiss",
    response_model=ProductReview,
    summary="Dismiss a Human Review case without fabricating completion",
)
def product_human_review_dismiss(
    review_id: uuid.UUID,
    payload: ReviewDismissIn,
    session: Session = Depends(get_session),
):
    _run_review_mutation(
        lambda: HumanReviewService(session).dismiss(
            review_id,
            reviewer_name=payload.reviewer_name,
            reason=payload.reason,
            notes=payload.notes,
        )
    )
    return _review_mutation_response(session, review_id)


@router.post(
    "/v1/human-review/{review_id}/ai/ask",
    response_model=AIAssistantResponseOut,
    summary="Ask a grounded question to the AI Review Assistant",
)
def product_human_review_ai_ask(
    review_id: uuid.UUID,
    payload: AIAssistantAskIn,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
):
    try:
        svc = AIReviewService(session, settings)
        response, suggestion, provider_name, provider_model = svc.ask(review_id, payload.question)
        session.commit()
        return AIAssistantResponseOut(
            message=response.message,
            mode=response.mode,
            suggestion=response.suggestion.model_dump() if response.suggestion else None,
            suggestion_id=suggestion.id if suggestion else None,
            provider_name=provider_name,
            provider_model=provider_model,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/v1/human-review/{review_id}/ai/suggestions/{suggestion_id}/accept",
    response_model=ProductReview,
    summary="Accept an AI suggestion and trigger recomparison",
)
def product_human_review_ai_accept(
    review_id: uuid.UUID,
    suggestion_id: uuid.UUID,
    payload: AISuggestionAcceptIn,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
):
    _run_review_mutation(
        lambda: AIReviewService(session, settings).accept(
            review_id,
            suggestion_id,
            reviewer_label=payload.reviewer_label,
        )
    )
    return _review_mutation_response(session, review_id)


@router.post(
    "/v1/human-review/{review_id}/ai/suggestions/{suggestion_id}/apply-edited",
    response_model=ProductReview,
    summary="Edit and apply an AI suggestion then trigger recomparison",
)
def product_human_review_ai_apply_edited(
    review_id: uuid.UUID,
    suggestion_id: uuid.UUID,
    payload: AISuggestionApplyEditedIn,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
):
    _run_review_mutation(
        lambda: AIReviewService(session, settings).apply_edited(
            review_id,
            suggestion_id,
            reviewer_value=payload.value,
            reviewer_label=payload.reviewer_label,
            note=payload.note,
        )
    )
    return _review_mutation_response(session, review_id)


@router.post(
    "/v1/human-review/{review_id}/ai/suggestions/{suggestion_id}/dismiss",
    response_model=ProductReview,
    summary="Dismiss an AI suggestion without altering case status",
)
def product_human_review_ai_dismiss(
    review_id: uuid.UUID,
    suggestion_id: uuid.UUID,
    payload: AISuggestionDismissIn,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
):
    _run_review_mutation(
        lambda: AIReviewService(session, settings).dismiss(
            review_id,
            suggestion_id,
            reviewer_label=payload.reviewer_label,
        )
    )
    return _review_mutation_response(session, review_id)


@router.get(
    "/v1/events",
    response_model=list[ProductEvent],
    summary="Poll persisted email processing updates",
)
def product_events(
    email_id: uuid.UUID | None = Query(None),
    since: datetime | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    session: Session = Depends(get_session),
):
    return list_processing_events(session, email_id=email_id, since=since, limit=limit)


@router.post(
    "/v1/sync/initial",
    response_model=InitialSyncOut,
    summary="Process the configured initial inbox backlog",
)
def product_initial_sync(
    body: SyncRequest = SyncRequest(),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
):
    report = sync(body=body, session=session, settings=settings)
    processed = report.ingested + report.skipped + report.failed
    total = report.total
    return InitialSyncOut(
        job_id=uuid.uuid4(),
        progress=SyncProgressOut(
            total=total,
            processed=processed,
            percent=100.0 if total == 0 else min(100.0, processed / total * 100.0),
            ingested=report.ingested,
            skipped=report.skipped,
            failed=report.failed,
        ),
        **report.model_dump(),
    )


@router.post(
    "/v1/ingestion/email",
    response_model=ProductIncomingOut,
    summary="Ingest one simulated or generic inbound email",
)
def product_incoming_email(
    payload: IncomingEmailIn,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
):
    return receive_incoming_email(payload=payload, session=session, settings=settings)


@router.post(
    "/v1/emails/{email_id}/reprocess",
    response_model=ProductReprocessOut,
    summary="Reprocess a technical failure",
)
def product_reprocess_email(
    email_id: uuid.UUID,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
):
    record = session.get(EmailMessageRecord, email_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Email not found")
    if record.processing_status != "FAILED":
        raise HTTPException(status_code=409, detail="Only FAILED emails can be reprocessed")
    try:
        message, source = _reprocess_source(record, settings)
    except (FileNotFoundError, KeyError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=f"Reprocess source unavailable: {exc}") from exc
    outcome = _build_sync_service(session, settings).sync_one(
        message,
        source,
        force=True,
    )
    return ProductReprocessOut(
        email_id=record.id,
        status=outcome.status,
        external_message_id=outcome.external_message_id,
    )


# ---------------------------------------------------------------------------
# Confirmed Discrepancies API
# ---------------------------------------------------------------------------


@router.get(
    "/v1/discrepancies",
    response_model=DiscrepancyPage,
    summary="List confirmed discrepancy cases (genuine MISMATCH results)",
)
def get_discrepancies(
    status: str | None = Query(default=None, description="Filter by resolution status: ALL, OPEN, ACKNOWLEDGED, RESOLVED"),
    search: str | None = Query(default=None, description="Search subject, sender, or external message ID"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_session),
):
    try:
        return list_product_discrepancies(
            session,
            status=status,
            search=search,
            skip=skip,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get(
    "/v1/discrepancies/{discrepancy_id}",
    response_model=ProductDiscrepancyDetail,
    summary="Get full details of a confirmed discrepancy case",
)
def get_discrepancy(
    discrepancy_id: uuid.UUID,
    session: Session = Depends(get_session),
):
    detail = get_product_discrepancy_detail(session, discrepancy_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Confirmed discrepancy case not found")
    return detail


def _discrepancy_mutation_response(
    session: Session,
    comparison_id: uuid.UUID,
    not_found_msg: str = "Confirmed discrepancy case not found",
) -> ProductDiscrepancyDetail:
    session.commit()
    session.expire_all()
    detail = get_product_discrepancy_detail(session, comparison_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=not_found_msg)
    return detail


@router.post(
    "/v1/discrepancies/{discrepancy_id}/acknowledge",
    response_model=ProductDiscrepancyDetail,
    summary="Acknowledge a confirmed discrepancy without changing comparison truth",
)
def acknowledge_discrepancy(
    discrepancy_id: uuid.UUID,
    payload: DiscrepancyAcknowledgeIn = DiscrepancyAcknowledgeIn(),
    session: Session = Depends(get_session),
):
    try:
        DiscrepancyService(session).acknowledge(
            discrepancy_id,
            operator_name=payload.operator_name,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DiscrepancyConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return _discrepancy_mutation_response(session, discrepancy_id, "Confirmed discrepancy case not found after update")


@router.post(
    "/v1/discrepancies/{discrepancy_id}/resolve",
    response_model=ProductDiscrepancyDetail,
    summary="Mark a confirmed discrepancy operationally resolved without altering comparison truth",
)
def resolve_discrepancy(
    discrepancy_id: uuid.UUID,
    payload: DiscrepancyResolveIn = DiscrepancyResolveIn(),
    session: Session = Depends(get_session),
):
    try:
        DiscrepancyService(session).resolve(
            discrepancy_id,
            operator_name=payload.operator_name,
            notes=payload.notes,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DiscrepancyConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return _discrepancy_mutation_response(session, discrepancy_id, "Confirmed discrepancy case not found after update")


@router.post(
    "/v1/discrepancies/{discrepancy_id}/override",
    response_model=ProductDiscrepancyDetail,
    summary="Add a field extraction correction for a discrepancy case",
)
def override_discrepancy_field(
    discrepancy_id: uuid.UUID,
    payload: DiscrepancyOverrideIn,
    session: Session = Depends(get_session),
):
    try:
        DiscrepancyService(session).add_override(
            discrepancy_id,
            document_side=payload.document_side,
            field_name=payload.field_name,
            corrected_value=payload.corrected_value,
            reviewer_name=payload.reviewer_name,
            note=payload.note,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DiscrepancyConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return _discrepancy_mutation_response(session, discrepancy_id, "Confirmed discrepancy case not found after override")


@router.post(
    "/v1/discrepancies/{discrepancy_id}/recompare",
    response_model=ProductDiscrepancyDetail,
    summary="Re-run deterministic comparison using effective canonical values",
)
def recompare_discrepancy(
    discrepancy_id: uuid.UUID,
    payload: DiscrepancyRecompareIn = DiscrepancyRecompareIn(),
    session: Session = Depends(get_session),
):
    try:
        recompared = DiscrepancyService(session).recompare(
            discrepancy_id,
            reviewer_name=payload.reviewer_name,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DiscrepancyConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return _discrepancy_mutation_response(session, recompared.id, "Comparison result not found after recomparison")
