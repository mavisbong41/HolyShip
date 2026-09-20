from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.app.api.deps import get_session, get_settings_dep
from backend.app.api.schemas import (
    ClassificationOut,
    EmailListItem,
    EmailOut,
    HumanReviewOut,
    IncomingEmailIn,
    SyncReportOut,
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

router = APIRouter()


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
    svc = SyncService(
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
    incoming = IncomingEmailPayload(
        external_message_id=payload.external_message_id,
        sender=payload.sender,
        recipients=payload.recipients,
        subject=payload.subject,
        body=payload.body,
        attachments=[
            IncomingAttachmentInput(
                filename=a.filename,
                source_reference=a.source_reference,
                content_type=a.content_type,
                external_attachment_id=a.external_attachment_id,
            )
            for a in payload.attachments
        ],
    )
    message: EmailMessage = map_incoming_payload(incoming)

    svc = SyncService(
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
    outcome = svc.sync_one(message)

    return {
        "external_message_id": outcome.external_message_id,
        "status": outcome.status,
        "error": outcome.error,
    }
