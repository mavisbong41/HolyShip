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
)
from backend.app.resolution.runtime import get_configured_resolution_executor_factory
from backend.app.sync.service import SyncService
from backend.app.api.product_queries import (
    get_email_detail,
    get_human_review as get_product_human_review,
    get_product_summary,
    list_email_queue,
    list_human_reviews as list_product_human_reviews,
    list_processing_events,
)
from backend.app.api.product_schemas import (
    ComparisonReadiness,
    EmailQueuePage,
    HumanReviewPage,
    ProductEmailDetail,
    ProductEvent,
    ProductIncomingOut,
    ProductReprocessOut,
    ProductReview,
    ProductSummary,
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
        return message, StaticBundleSource(settings.organizer_bundle_path)
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
        email_source = StaticBundleSource(settings.organizer_bundle_path)

    report = svc.sync(email_source)
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
    review_status: Literal["OPEN", "RESOLVED"] | None = Query(None),
    comparison_state: Literal["COMPLETED", "BLOCKED"] | None = Query(None),
    has_mismatch: bool | None = Query(None),
    search: str | None = Query(None, min_length=1, max_length=200),
    received_from: datetime | None = Query(None),
    received_to: datetime | None = Query(None),
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
    )


@router.get(
    "/v1/summary",
    response_model=ProductSummary,
    summary="Return persisted dashboard counts",
)
def product_summary(session: Session = Depends(get_session)):
    return get_product_summary(session)


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


@router.get(
    "/v1/human-review",
    response_model=HumanReviewPage,
    summary="List reviewer-ready cases",
)
def product_human_review_queue(
    status: Literal["OPEN", "RESOLVED"] | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    session: Session = Depends(get_session),
):
    return list_product_human_reviews(session, status=status, skip=skip, limit=limit)


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
