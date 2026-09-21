from __future__ import annotations
from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, selectinload


from backend.app.api import review_helper, review_action_helper
from backend.app.api import analytics_helper
from backend.app.api.product_schemas import HumanReviewAnalytics
from backend.app.api.product_schemas import (
    EmailQueuePage,
    HumanReviewPage,
    ProductAttachment,
    ProductClassification,
    ProductComparison,
    ProductDocument,
    ProductEmailDetail,
    ProductEmailSummary,
    ProductEvent,
    ProductEvidence,
    ProductExtractedField,
    ProductFieldComparison,
    ProductResolution,
    ProductReview,
    ProductSummary,
    ProductTimelineEvent,
    ProductValue,
)
from backend.app.storage.models import (
    AIResolutionRecord,
    AttachmentRecord,
    ClassificationResultRecord,
    ComparisonResultRecord,
    DocumentExtractionRecord,
    DocumentRecord,
    EmailMessageRecord,
    HumanReviewCaseRecord,
    ProcessingEventRecord,
)


CANONICAL_FIELDS = (
    "shipper",
    "consignee",
    "notify_party",
    "port_of_loading",
    "port_of_discharge",
    "container_count",
    "gross_weight_kg",
)


def validate_page(*, skip: int, limit: int) -> tuple[int, int]:
    if skip < 0:
        raise ValueError("skip must be non-negative")
    if limit < 1 or limit > 500:
        raise ValueError("limit must be between 1 and 500")
    return skip, limit


def _ranked(model: Any, *, partition: Any) -> Any:
    return (
        select(
            model,
            func.row_number()
            .over(
                partition_by=partition,
                order_by=[model.created_at.desc(), model.id.desc()],
            )
            .label("rank"),
        )
        .subquery()
    )


def _queue_sources() -> tuple[Any, Any, Any]:
    classification = _ranked(ClassificationResultRecord, partition=ClassificationResultRecord.email_id)
    comparison = _ranked(ComparisonResultRecord, partition=ComparisonResultRecord.email_id)
    # Queue/summary semantics are about current actionable work. Legacy review
    # rows remain available in Human Review history, but must never make an
    # email look actively reviewable.
    review = (
        select(
            HumanReviewCaseRecord,
            func.row_number()
            .over(
                partition_by=HumanReviewCaseRecord.email_id,
                order_by=[HumanReviewCaseRecord.created_at.desc(), HumanReviewCaseRecord.id.desc()],
            )
            .label("rank"),
        )
        .where(HumanReviewCaseRecord.case_origin == "ACTIVE")
        .subquery()
    )
    return classification, comparison, review


def _needs_review_expr(email: Any, comparison: Any, review: Any) -> Any:
    email_status = email.c.processing_status if hasattr(email, "c") else email.processing_status
    return or_(
        and_(review.c.case_origin == "ACTIVE", review.c.status.in_(["OPEN", "IN_REVIEW"])),
        email_status == "BLOCKED",
        comparison.c.comparison_state == "BLOCKED",
    )


def _json_length(column: Any) -> Any:
    return func.coalesce(func.jsonb_array_length(column), 0)


def _queue_statement(
    *,
    status: str | None,
    category: str | None,
    comparison_readiness: str | None,
    needs_review: bool | None,
    review_status: str | None,
    comparison_state: str | None,
    has_mismatch: bool | None,
    search: str | None,
    received_from: datetime | None,
    received_to: datetime | None,
) -> tuple[Any, Any]:
    classification, comparison, review = _queue_sources()
    attachment_count = (
        select(func.count(AttachmentRecord.id))
        .where(AttachmentRecord.email_id == EmailMessageRecord.id)
        .scalar_subquery()
    )
    mismatch_count = _json_length(comparison.c.mismatched_fields)
    unresolved_count = _json_length(comparison.c.unresolved_fields)
    needs_review_value = _needs_review_expr(EmailMessageRecord, comparison, review)
    columns = [
        EmailMessageRecord.id,
        EmailMessageRecord.external_message_id,
        EmailMessageRecord.source_type,
        EmailMessageRecord.sender,
        EmailMessageRecord.subject,
        EmailMessageRecord.received_at,
        EmailMessageRecord.created_at,
        EmailMessageRecord.processing_status,
        attachment_count.label("attachment_count"),
        classification.c.category,
        classification.c.confidence.label("classification_confidence"),
        classification.c.comparison_readiness,
        comparison.c.comparison_state,
        mismatch_count.label("mismatch_count"),
        unresolved_count.label("unresolved_count"),
        needs_review_value.label("needs_review"),
        review.c.status.label("review_status"),
        review.c.reason_code.label("review_reason"),
        review.c.id.label("review_id"),
    ]
    statement = (
        select(*columns)
        .select_from(EmailMessageRecord)
        .outerjoin(
            classification,
            and_(
                classification.c.email_id == EmailMessageRecord.id,
                classification.c.rank == 1,
            ),
        )
        .outerjoin(
            comparison,
            and_(comparison.c.email_id == EmailMessageRecord.id, comparison.c.rank == 1),
        )
        .outerjoin(review, and_(review.c.email_id == EmailMessageRecord.id, review.c.rank == 1))
    )
    filters = []
    if status:
        filters.append(EmailMessageRecord.processing_status == status)
    if category:
        filters.append(classification.c.category == category)
    if comparison_readiness:
        filters.append(classification.c.comparison_readiness == comparison_readiness)
    if review_status:
        filters.append(review.c.status == review_status)
    if comparison_state:
        filters.append(comparison.c.comparison_state == comparison_state)
    if has_mismatch is not None:
        filters.append(comparison.c.mismatch_found.is_(has_mismatch))
    if needs_review is not None:
        filters.append(needs_review_value.is_(needs_review))
    if search:
        pattern = f"%{search}%"
        filters.append(
            or_(
                EmailMessageRecord.subject.ilike(pattern),
                EmailMessageRecord.sender.ilike(pattern),
                EmailMessageRecord.external_message_id.ilike(pattern),
            )
        )
    if received_from:
        filters.append(EmailMessageRecord.received_at >= received_from)
    if received_to:
        filters.append(EmailMessageRecord.received_at <= received_to)
    if filters:
        statement = statement.where(*filters)
    order = (
        EmailMessageRecord.received_at.desc().nullslast(),
        EmailMessageRecord.created_at.desc(),
        EmailMessageRecord.id.desc(),
    )
    return statement.order_by(*order), select(func.count()).select_from(statement.order_by(None).subquery())


def _summary_from_row(row: Any) -> ProductEmailSummary:
    return ProductEmailSummary(
        id=row.id,
        external_message_id=row.external_message_id,
        source_type=row.source_type,
        sender=row.sender,
        subject=row.subject,
        received_at=row.received_at,
        created_at=row.created_at,
        processing_status=row.processing_status,
        attachment_count=int(row.attachment_count or 0),
        category=row.category,
        classification_confidence=row.classification_confidence,
        comparison_readiness=row.comparison_readiness,
        comparison_state=row.comparison_state,
        mismatch_count=int(row.mismatch_count or 0),
        unresolved_count=int(row.unresolved_count or 0),
        needs_review=bool(row.needs_review),
        review_status=row.review_status,
        review_reason=getattr(row, "review_reason", None) or (
            _latest(row.human_review_cases).reason_code if getattr(row, "human_review_cases", None) else None
        ),
        review_id=getattr(row, "review_id", None) or (
            _latest(row.human_review_cases).id if getattr(row, "human_review_cases", None) else None
        ),
    )


def sync_blocked_cases_to_review(session: Session) -> None:
    from backend.app.review.service import HumanReviewService
    from backend.app.storage.repositories import ComparisonResultRepository
    from backend.app.storage.models import ProcessingEventRecord

    blocked_emails = session.scalars(
        select(EmailMessageRecord)
        .where(EmailMessageRecord.processing_status == "BLOCKED")
    ).all()
    if not blocked_emails:
        return

    review_service = HumanReviewService(session)
    comp_repo = ComparisonResultRepository(session)
    for email in blocked_emails:
        # Find the actual blocked event reason from processing events
        blocked_event = session.scalar(
            select(ProcessingEventRecord)
            .where(
                ProcessingEventRecord.email_id == email.id,
                ProcessingEventRecord.new_status == "BLOCKED",
            )
            .order_by(ProcessingEventRecord.created_at.desc())
        )
        source_comparison = comp_repo.get_latest_by_email_id(email.id)
        if blocked_event and blocked_event.reason_code:
            reason = blocked_event.reason_code
        elif source_comparison and source_comparison.reason_code:
            reason = source_comparison.reason_code
        else:
            reason = "COMPARISON_UNRESOLVED"

        existing_case = session.scalar(
            select(HumanReviewCaseRecord).where(
                HumanReviewCaseRecord.email_id == email.id,
                HumanReviewCaseRecord.case_origin == "ACTIVE",
            )
        )
        if existing_case:
            if existing_case.reason_code != reason:
                existing_case.reason_code = reason
                existing_case.reason_text = review_service._reason_text(reason)
        else:
            review_service.ensure_actionable_case(
                email,
                reason_code=reason,
                source_comparison_id=source_comparison.id if source_comparison else None,
                evidence={
                    "comparison_id": str(source_comparison.id) if source_comparison else None,
                },
            )
    session.commit()


def list_email_queue(
    session: Session,
    *,
    skip: int,
    limit: int,
    status: str | None = None,
    category: str | None = None,
    comparison_readiness: str | None = None,
    needs_review: bool | None = None,
    review_status: str | None = None,
    comparison_state: str | None = None,
    has_mismatch: bool | None = None,
    search: str | None = None,
    received_from: datetime | None = None,
    received_to: datetime | None = None,
) -> EmailQueuePage:
    validate_page(skip=skip, limit=limit)
    sync_blocked_cases_to_review(session)
    statement, count_statement = _queue_statement(
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
    rows = session.execute(statement.offset(skip).limit(limit)).all()
    total = int(session.scalar(count_statement) or 0)
    return EmailQueuePage(
        items=[_summary_from_row(row) for row in rows],
        total=total,
        skip=skip,
        limit=limit,
    )


def get_product_summary(session: Session) -> ProductSummary:
    sync_blocked_cases_to_review(session)
    classification, comparison, review = _queue_sources()
    needs_review_value = _needs_review_expr(EmailMessageRecord, comparison, review)
    active_review_count = (
        select(func.count(HumanReviewCaseRecord.id))
        .where(
            HumanReviewCaseRecord.case_origin == "ACTIVE",
            HumanReviewCaseRecord.status.in_(["OPEN", "IN_REVIEW"]),
        )
        .scalar_subquery()
    )
    statement = (
        select(
            func.count(EmailMessageRecord.id).label("total"),
            func.count(EmailMessageRecord.id).filter(
                EmailMessageRecord.processing_status == "BLOCKED"
            ).label("blocked"),
            func.count(EmailMessageRecord.id).filter(
                EmailMessageRecord.processing_status == "FAILED"
            ).label("failed"),
            func.count(EmailMessageRecord.id).filter(
                EmailMessageRecord.processing_status == "COMPLETED"
            ).label("completed"),
            func.count(EmailMessageRecord.id).filter(needs_review_value).label("needs_review"),
            active_review_count.label("active_review_count"),
            func.count(EmailMessageRecord.id).filter(
                classification.c.comparison_readiness == "READY_FOR_COMPARISON"
            ).label("ready"),
            func.count(EmailMessageRecord.id).filter(
                comparison.c.mismatch_found.is_(True)
            ).label("mismatch"),
            func.count(EmailMessageRecord.id).filter(
                _json_length(comparison.c.unresolved_fields) > 0
            ).label("unresolved"),
        )
        .select_from(EmailMessageRecord)
        .outerjoin(classification, and_(classification.c.email_id == EmailMessageRecord.id, classification.c.rank == 1))
        .outerjoin(comparison, and_(comparison.c.email_id == EmailMessageRecord.id, comparison.c.rank == 1))
        .outerjoin(review, and_(review.c.email_id == EmailMessageRecord.id, review.c.rank == 1))
    )
    row = session.execute(statement).one()
    status_rows = session.execute(
        select(EmailMessageRecord.processing_status, func.count(EmailMessageRecord.id))
        .group_by(EmailMessageRecord.processing_status)
    ).all()
    status_counts = {status: int(count) for status, count in status_rows}
    active_open_count = int(row.active_review_count or 0)
    processing_count = sum(
        count for status, count in status_counts.items()
        if status not in {"COMPLETED", "AWAITING_DOCUMENTS", "BLOCKED", "FAILED"}
    )
    return ProductSummary(
        total_emails=int(row.total or 0),
        status_counts=status_counts,
        needs_review_count=int(row.needs_review or 0),
        comparison_ready_count=int(row.ready or 0),
        mismatch_count=int(row.mismatch or 0),
        unresolved_count=int(row.unresolved or 0),
        completed_count=status_counts.get("COMPLETED", 0),
        awaiting_documents_count=status_counts.get("AWAITING_DOCUMENTS", 0),
        human_review_open_count=active_open_count,
        failed_count=status_counts.get("FAILED", 0),
        processing_count=processing_count,
    )


def _latest(rows: Iterable[Any]) -> Any | None:
    return max(rows, key=lambda row: (row.created_at, str(row.id)), default=None)


def _evidence_items(
    payload: Any,
    *,
    field: str | None = None,
    document: DocumentRecord | None = None,
    document_role: str | None = None,
) -> list[ProductEvidence]:
    if not payload:
        return []
    if isinstance(payload, list):
        source_items = payload
    else:
        source_items = [payload]
    result: list[ProductEvidence] = []
    for item in source_items:
        if not isinstance(item, dict):
            item = {"reason": str(item)}
        details = dict(item)
        page = details.pop("page", details.pop("page_number", None))
        text_span = details.pop("text_span", None)
        reason = details.pop("reason", None)
        source_type = details.pop("source_type", None)
        result.append(
            ProductEvidence(
                document_id=document.id if document else None,
                document_role=document_role or (document.document_type if document else None),
                attachment_id=document.attachment_id if document else None,
                filename=document.filename if document else None,
                page=page if isinstance(page, int) else None,
                text_span=text_span if isinstance(text_span, str) else None,
                source_type=source_type if isinstance(source_type, str) else None,
                field=field,
                reason=reason if isinstance(reason, str) else None,
                details=details,
            )
        )
    return result


def _classification(record: ClassificationResultRecord | None) -> ProductClassification | None:
    if record is None:
        return None
    return ProductClassification(
        category=record.category,
        confidence=record.confidence,
        candidate_scores=record.candidate_scores,
        reason=record.reason,
        reason_code=record.reason_code,
        evidence=_evidence_items(record.evidence_summary),
        conflict_detected=record.conflict_detected,
        resolved_at_stage=record.resolved_at_stage,
        comparison_readiness=record.comparison_readiness,
        classifier_version=record.classifier_version,
        created_at=record.created_at,
    )


def _document(document: DocumentRecord) -> ProductDocument:
    extraction = _latest(document.extractions)
    fields = []
    read_status = None
    reader_used = None
    extraction_quality = None
    failure_reason = None
    if extraction is not None:
        read_status = extraction.extraction_status
        reader_used = extraction.reader_used
        extraction_quality = extraction.extraction_quality
        failure_reason = (extraction.metadata_json or {}).get("error")
        by_name = {field.field_name: field for field in extraction.fields}
        for field_name in CANONICAL_FIELDS:
            field_record = by_name.get(field_name)
            if field_record is None:
                continue
            fields.append(
                ProductExtractedField(
                    field=field_record.field_name,
                    raw_label=field_record.raw_label,
                    raw_value=field_record.raw_value_json,
                    canonical_value=field_record.canonical_value,
                    status=field_record.status,
                    confidence=field_record.confidence,
                    mapping_method=field_record.mapping_method,
                    extraction_method=field_record.extraction_method,
                    source_location=field_record.source_location,
                    evidence=_evidence_items(
                        field_record.evidence,
                        field=field_record.field_name,
                        document=document,
                    ),
                )
            )
    return ProductDocument(
        id=document.id,
        attachment_id=document.attachment_id,
        filename=document.filename,
        role=document.document_type,
        format=document.format,
        source_reference=document.source_reference,
        routing_outcome=document.routing_outcome,
        role_confidence=document.role_confidence,
        role_evidence=document.role_evidence,
        validation_outcome=document.validation_outcome,
        read_status=read_status,
        reader_used=reader_used,
        extraction_quality=extraction_quality,
        failure_reason=failure_reason,
        fields=fields,
    )


def _comparison(record: ComparisonResultRecord | None) -> ProductComparison | None:
    if record is None:
        return None
    fields = []
    by_name = {field.field_name: field for field in record.fields}
    for field_name in CANONICAL_FIELDS:
        field_record = by_name.get(field_name)
        if field_record is None:
            continue
        fields.append(
            ProductFieldComparison(
                field=field_name,
                si=ProductValue(
                    raw=field_record.si_raw_value,
                    canonical=field_record.si_canonical_value,
                    normalized=field_record.si_normalized_value,
                ),
                bl=ProductValue(
                    raw=field_record.bl_raw_value,
                    canonical=field_record.bl_canonical_value,
                    normalized=field_record.bl_normalized_value,
                ),
                status=field_record.status,
                reason_code=field_record.reason_code,
                evidence=_evidence_items(field_record.evidence, field=field_name),
            )
        )
    return ProductComparison(
        state=record.comparison_state,
        mismatch_found=record.mismatch_found,
        mismatched_fields=list(record.mismatched_fields or []),
        unresolved_fields=list(record.unresolved_fields or []),
        reason_code=record.reason_code,
        message=record.message,
        fields=fields,
    )


def _resolution(record: AIResolutionRecord) -> ProductResolution:
    response = record.response_json or {}
    return ProductResolution(
        purpose=record.purpose,
        field=record.field_name,
        accepted=record.accepted,
        confidence=record.confidence,
        reason=record.validation_reason,
        evidence=_evidence_items(response.get("evidence")),
        provider_name=record.provider_name,
        model_name=record.model_name,
        resolver_version=record.resolver_version,
    )


def _attachment(record: AttachmentRecord) -> ProductAttachment:
    return ProductAttachment(
        id=record.id,
        filename=record.filename,
        content_type=record.content_type,
        external_attachment_id=record.external_attachment_id,
        retrieval_status=record.retrieval_status,
        retrieval_reason_code=record.retrieval_reason_code,
        content_sha256=record.content_sha256,
    )


def _summary_from_record(
    record: EmailMessageRecord,
    *,
    classification: ClassificationResultRecord | None,
    comparison: ComparisonResultRecord | None,
    review: HumanReviewCaseRecord | None,
) -> ProductEmailSummary:
    mismatch_count = len(comparison.mismatched_fields or []) if comparison else 0
    unresolved_count = len(comparison.unresolved_fields or []) if comparison else 0
    needs_review = bool(
        (
            review
            and review.case_origin == "ACTIVE"
            and review.status in {"OPEN", "IN_REVIEW"}
        )
        or record.processing_status == "BLOCKED"
        or (comparison and comparison.comparison_state == "BLOCKED")
    )
    return ProductEmailSummary(
        id=record.id,
        external_message_id=record.external_message_id,
        source_type=record.source_type,
        sender=record.sender,
        subject=record.subject,
        received_at=record.received_at,
        created_at=record.created_at,
        processing_status=record.processing_status,
        attachment_count=len(record.attachments),
        category=classification.category if classification else None,
        classification_confidence=classification.confidence if classification else None,
        comparison_readiness=classification.comparison_readiness if classification else None,
        comparison_state=comparison.comparison_state if comparison else None,
        mismatch_count=mismatch_count,
        unresolved_count=unresolved_count,
        needs_review=needs_review,
        review_status=review.status if review else None,
        review_reason=review.reason_code if review else None,
        review_id=review.id if review else None,
    )


def _load_email_graph(session: Session, email_id: UUID) -> EmailMessageRecord | None:
    return session.scalar(
        select(EmailMessageRecord)
        .where(EmailMessageRecord.id == email_id)
        .options(
            selectinload(EmailMessageRecord.attachments),
            selectinload(EmailMessageRecord.documents)
            .selectinload(DocumentRecord.extractions)
            .selectinload(DocumentExtractionRecord.fields),
            selectinload(EmailMessageRecord.documents).selectinload(DocumentRecord.attachment),
            selectinload(EmailMessageRecord.classification_results),
            selectinload(EmailMessageRecord.comparison_results).selectinload(ComparisonResultRecord.fields),
            selectinload(EmailMessageRecord.processing_events),
            selectinload(EmailMessageRecord.human_review_cases),
        )
    )


def get_email_detail(session: Session, email_id: UUID) -> ProductEmailDetail | None:
    record = _load_email_graph(session, email_id)
    if record is None:
        return None
    classification_record = _latest(record.classification_results)
    comparison_record = _latest(record.comparison_results)
    review_records = sorted(record.human_review_cases, key=lambda item: (item.created_at, str(item.id)))
    latest_review = _latest(
        [item for item in review_records if item.case_origin == "ACTIVE"]
    )
    resolutions = session.scalars(
        select(AIResolutionRecord)
        .where(AIResolutionRecord.case_id == str(record.id))
        .order_by(AIResolutionRecord.created_at.asc(), AIResolutionRecord.id.asc())
    ).all()
    summary = _summary_from_record(
        record,
        classification=classification_record,
        comparison=comparison_record,
        review=latest_review,
    )
    comparison = _comparison(comparison_record)
    from backend.app.storage.models import (
        AISuggestionRecord,
        HumanReviewEventRecord,
        HumanReviewFieldOverrideRecord,
    )
    review = []
    comparison = _comparison(comparison_record)
    for item in review_records:
        aff_fields = review_helper.compute_affected_fields(item, comparison)
        priority = review_helper.compute_priority(item, aff_fields)
        presentation = review_helper.compute_review_presentation(item, aff_fields)
        human_explanation = presentation.explanation
        age_minutes = review_helper.compute_age_minutes(item.created_at)

        raw_overrides = session.scalars(select(HumanReviewFieldOverrideRecord).where(HumanReviewFieldOverrideRecord.review_case_id == item.id)).all()
        overrides = [review_action_helper._review_override(r) for r in sorted(raw_overrides, key=lambda r: (r.created_at, str(r.id)))]

        raw_events = session.scalars(select(HumanReviewEventRecord).where(HumanReviewEventRecord.review_case_id == item.id)).all()
        actions = [review_action_helper._review_action(e) for e in sorted(raw_events, key=lambda e: (e.created_at, str(e.id)))]

        raw_suggestions = session.scalars(select(AISuggestionRecord).where(AISuggestionRecord.human_review_case_id == item.id)).all()
        ai_suggestions = [review_action_helper._review_ai_suggestion(s) for s in sorted(raw_suggestions, key=lambda s: (s.created_at, str(s.id)))]

        review.append(ProductReview(
            id=item.id,
            email_id=item.email_id,
            document_id=item.document_id,
            field=item.field_name,
            reason_code=item.reason_code,
            reason_text=item.reason_text,
            status=item.status,
            case_origin=item.case_origin,
            workflow_identity=item.workflow_identity,
            source_comparison_id=item.source_comparison_id,
            reviewer_name=item.reviewer_name,
            resolution=item.resolution,
            notes=item.notes,
            confidence=item.confidence,
            evidence=item.evidence.get('evidence', []) if item.evidence else [],
            comparison=comparison,
            priority=priority,
            presentation_title=presentation.title,
            human_explanation=human_explanation,
            affected_fields=aff_fields,
            affected_area=presentation.affected_area,
            suggested_action=presentation.suggested_action,
            semantic_style=presentation.semantic_style,
            canonical_reason=presentation.canonical_reason or presentation.title,
            trigger=presentation.trigger,
            stage=presentation.stage,
            age_minutes=age_minutes,
            overrides=overrides,
            actions=actions,
            resolutions=[_resolution(item_resolution) for item_resolution in resolutions if item_resolution.field_name == item.field_name] if item.field_name else [],
            ai_suggestions=ai_suggestions,
            created_at=item.created_at,
            updated_at=item.updated_at,
            resolved_at=item.resolved_at,
        ))
    return ProductEmailDetail(
        email=summary,
        body=record.body,
        recipients=list(record.recipients or []),
        content_hash=record.content_hash,
        attachments=[_attachment(item) for item in sorted(record.attachments, key=lambda row: (row.created_at, str(row.id)))],
        classification=_classification(classification_record),
        documents=[_document(item) for item in sorted(record.documents, key=lambda row: (row.created_at, str(row.id)))],
        comparison=comparison,
        timeline=[
            ProductTimelineEvent(
                id=item.id,
                old_status=item.old_status,
                new_status=item.new_status,
                reason_code=item.reason_code,
                created_at=item.created_at,
            )
            for item in sorted(record.processing_events, key=lambda row: (row.created_at, str(row.id)))
        ],
        review=review,
        resolutions=[_resolution(item) for item in resolutions],
    )


def list_processing_events(
    session: Session,
    *,
    email_id: UUID | None = None,
    since: datetime | None = None,
    limit: int = 100,
) -> list[ProductEvent]:
    validate_page(skip=0, limit=limit)
    classification, comparison, _ = _queue_sources()
    statement = (
        select(
            ProcessingEventRecord,
            classification.c.category.label("event_category"),
            comparison.c.mismatch_found.label("event_mismatch_found"),
        )
        .outerjoin(
            classification,
            and_(classification.c.email_id == ProcessingEventRecord.email_id, classification.c.rank == 1),
        )
        .outerjoin(
            comparison,
            and_(comparison.c.email_id == ProcessingEventRecord.email_id, comparison.c.rank == 1),
        )
        .order_by(ProcessingEventRecord.created_at.asc(), ProcessingEventRecord.id.asc())
        .limit(limit)
    )
    if email_id:
        statement = statement.where(ProcessingEventRecord.email_id == email_id)
    if since:
        statement = statement.where(ProcessingEventRecord.created_at > since)
    rows = session.execute(statement).all()
    result = []
    for event, category, mismatch_found in rows:
        result.append(
            ProductEvent(
                event="EMAIL_PROCESSING_UPDATED",
                email_id=event.email_id,
                status=event.new_status,
                category=category,
                mismatch_found=bool(mismatch_found) if mismatch_found is not None else False,
                updated_at=event.created_at,
                reason_code=event.reason_code,
            )
        )
    return result


def list_human_reviews(
    session: Session,
    *,
    status: str | None = None,
    reason: str | None = None,
    reviewer: str | None = None,
    search: str | None = None,
    active_only: bool = True,
    sort: str | None = None,
    skip: int = 0,
    limit: int = 100,
) -> HumanReviewPage:
    validate_page(skip=skip, limit=limit)
    sync_blocked_cases_to_review(session)
    statement = (
        select(HumanReviewCaseRecord)
        .options(
            selectinload(HumanReviewCaseRecord.email).selectinload(EmailMessageRecord.attachments),
            selectinload(HumanReviewCaseRecord.email).selectinload(EmailMessageRecord.classification_results),
            selectinload(HumanReviewCaseRecord.email)
            .selectinload(EmailMessageRecord.comparison_results)
            .selectinload(ComparisonResultRecord.fields),
        )
        .order_by(HumanReviewCaseRecord.created_at.desc(), HumanReviewCaseRecord.id.desc())
    )
    if status:
        statement = statement.where(HumanReviewCaseRecord.status == status)
    if reason:
        reason_map = {
            "Missing Required Value": ["COMPARISON_UNRESOLVED"],
            "Wrong Document Type": ["WRONG_DOCUMENT_TYPE", "DOCUMENT_ROLE_UNRESOLVED", "MULTIPLE_CANDIDATES"],
            "Missing Attachment": ["MISSING_REQUIRED_ATTACHMENT", "READINESS_UNRESOLVED"],
            "Unreadable Document": ["UNREADABLE_ATTACHMENT", "CORRUPTED_ATTACHMENT", "UNSUPPORTED_ATTACHMENT"],
        }
        if reason in reason_map:
            statement = statement.where(HumanReviewCaseRecord.reason_code.in_(reason_map[reason]))
        else:
            statement = statement.where(HumanReviewCaseRecord.reason_code == reason)
    if reviewer:
        statement = statement.where(HumanReviewCaseRecord.reviewer_name.ilike(f"%{reviewer}%"))
    if active_only:
        statement = statement.where(HumanReviewCaseRecord.case_origin == "ACTIVE")
    if search:
        pattern = f"%{search}%"
        statement = statement.join(HumanReviewCaseRecord.email).where(
            or_(
                EmailMessageRecord.subject.ilike(pattern),
                EmailMessageRecord.sender.ilike(pattern),
                HumanReviewCaseRecord.reason_text.ilike(pattern),
                HumanReviewCaseRecord.reviewer_name.ilike(pattern),
            )
        )
    rows = session.scalars(statement).all()
    resolutions_by_email: dict[str, list[ProductResolution]] = defaultdict(list)
    email_ids = [row.email_id for row in rows]
    if email_ids:
        resolution_rows = session.scalars(
            select(AIResolutionRecord)
            .where(AIResolutionRecord.case_id.in_([str(email_id) for email_id in email_ids]))
            .order_by(AIResolutionRecord.created_at.asc(), AIResolutionRecord.id.asc())
        ).all()
        by_email_id = {str(email_id): email_id for email_id in email_ids}
        for resolution_row in resolution_rows:
            # The Phase-6 case identity is the owning email UUID.
            if resolution_row.case_id in by_email_id:
                resolutions_by_email[resolution_row.case_id].append(_resolution(resolution_row))
    items = []
    for row in rows:
        email = row.email
        email_classification = _latest(email.classification_results) if email else None
        email_comparison_record = _latest(email.comparison_results) if email else None
        email_summary = (
            _summary_from_record(
                email,
                classification=email_classification,
                comparison=email_comparison_record,
                review=row,
            )
            if email
            else None
        )
        comp = row.evidence.get('comparison') if row.evidence else None
        aff_fields = review_helper.compute_affected_fields(row, _comparison(email_comparison_record))
        priority = review_helper.compute_priority(row, aff_fields)
        presentation = review_helper.compute_review_presentation(row, aff_fields)
        human_explanation = presentation.explanation
        age_minutes = review_helper.compute_age_minutes(row.created_at)

        from backend.app.storage.models import (
            AISuggestionRecord,
            HumanReviewEventRecord,
            HumanReviewFieldOverrideRecord,
        )
        raw_overrides = session.scalars(select(HumanReviewFieldOverrideRecord).where(HumanReviewFieldOverrideRecord.review_case_id == row.id)).all()
        overrides = [review_action_helper._review_override(r) for r in sorted(raw_overrides, key=lambda r: (r.created_at, str(r.id)))]
        raw_events = session.scalars(select(HumanReviewEventRecord).where(HumanReviewEventRecord.review_case_id == row.id)).all()
        actions = [review_action_helper._review_action(e) for e in sorted(raw_events, key=lambda e: (e.created_at, str(e.id)))]
        claimed_at = next((action.created_at for action in actions if action.action == "CASE_CLAIMED"), None)
        raw_suggestions = session.scalars(select(AISuggestionRecord).where(AISuggestionRecord.human_review_case_id == row.id)).all()
        ai_suggestions = [review_action_helper._review_ai_suggestion(s) for s in sorted(raw_suggestions, key=lambda s: (s.created_at, str(s.id)))]

        items.append(ProductReview(
            id=row.id,
            email_id=row.email_id,
            email=email_summary,
            document_id=row.document_id,
            field=row.field_name,
            reason_code=row.reason_code,
            reason_text=row.reason_text,
            status=row.status,
            case_origin=row.case_origin,
            workflow_identity=row.workflow_identity,
            source_comparison_id=row.source_comparison_id,
            reviewer_name=row.reviewer_name,
            claimed_at=claimed_at,
            resolution=row.resolution,
            notes=row.notes,
            confidence=row.confidence,
            evidence=row.evidence.get('evidence', []) if row.evidence else [],
            comparison=comp,
            priority=priority,
            presentation_title=presentation.title,
            human_explanation=human_explanation,
            affected_fields=aff_fields,
            affected_area=presentation.affected_area,
            suggested_action=presentation.suggested_action,
            semantic_style=presentation.semantic_style,
            canonical_reason=presentation.canonical_reason or presentation.title,
            trigger=presentation.trigger,
            stage=presentation.stage,
            age_minutes=age_minutes,
            overrides=overrides,
            actions=actions,
            resolutions=resolutions_by_email.get(str(row.email_id), []),
            ai_suggestions=ai_suggestions,
            created_at=row.created_at,
            updated_at=row.updated_at,
            resolved_at=row.resolved_at,
        ))
    if sort == "priority":
        priority_rank = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        items.sort(
            key=lambda item: (
                priority_rank.get(item.priority, 3),
                -item.created_at.timestamp(),
                str(item.id),
            )
        )
    elif sort in {"age", "oldest"}:
        # Age descending is equivalent to created_at ascending and avoids wall-clock rounding.
        items.sort(key=lambda item: (item.created_at, str(item.id)))
    else:
        # The default and explicit newest ordering are deterministic.
        items.sort(key=lambda item: (item.created_at, str(item.id)), reverse=True)
    total = len(items)
    return HumanReviewPage(items=items[skip : skip + limit], total=total, skip=skip, limit=limit)


def get_human_review(session: Session, review_id: UUID) -> ProductReview | None:
    row = session.get(HumanReviewCaseRecord, review_id)
    if row is None:
        return None
    detail = get_email_detail(session, row.email_id)
    if not detail:
        return None
    for r in detail.review:
        if r.id == review_id:
            r.email = detail.email
            r.documents = detail.documents
            r.body = detail.body
            return r
    return None

def get_human_review_analytics(session: Session) -> HumanReviewAnalytics:
    return analytics_helper.get_human_review_analytics(session)
