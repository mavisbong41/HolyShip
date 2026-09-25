from __future__ import annotations

from typing import Any
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.app.api.presentation import present_reason
from backend.app.storage.models import (
    ComparisonResultRecord,
    DocumentExtractionRecord,
    DocumentRecord,
    EmailMessageRecord,
    ExtractedFieldRecord,
    HumanReviewCaseRecord,
    HumanReviewEventRecord,
    HumanReviewFieldOverrideRecord,
)


def build_case_context(session: Session, case_id: UUID) -> dict[str, Any]:
    """Assemble minimal, single-case context grounded in persisted database truth."""
    case = session.scalar(
        select(HumanReviewCaseRecord)
        .where(HumanReviewCaseRecord.id == case_id)
        .options(
            selectinload(HumanReviewCaseRecord.email).selectinload(EmailMessageRecord.attachments),
            selectinload(HumanReviewCaseRecord.email).selectinload(EmailMessageRecord.documents).selectinload(DocumentRecord.extractions).selectinload(DocumentExtractionRecord.fields),
            selectinload(HumanReviewCaseRecord.email).selectinload(EmailMessageRecord.classification_results),
            selectinload(HumanReviewCaseRecord.email).selectinload(EmailMessageRecord.comparison_results).selectinload(ComparisonResultRecord.fields),
            selectinload(HumanReviewCaseRecord.overrides),
            selectinload(HumanReviewCaseRecord.events),
        )
    )
    if case is None:
        raise LookupError(f"Human review case {case_id} not found")

    email = case.email
    latest_classification = None
    if email.classification_results:
        human = [row for row in email.classification_results if row.resolved_at_stage == "human_override"]
        latest_classification = sorted(
            human or email.classification_results,
            key=lambda r: (r.created_at, str(r.id)), reverse=True,
        )[0]

    # Find relevant comparison record
    comparison_record = None
    if case.source_comparison_id:
        comparison_record = next(
            (c for c in email.comparison_results if c.id == case.source_comparison_id),
            None,
        )
    if comparison_record is None and email.comparison_results:
        comparison_record = sorted(
            email.comparison_results,
            key=lambda r: (r.created_at, str(r.id)),
            reverse=True,
        )[0]

    # Materialized documents
    documents_info = []
    si_document = None
    bl_document = None
    si_fields_map: dict[str, dict[str, Any]] = {}
    bl_fields_map: dict[str, dict[str, Any]] = {}

    for doc in email.documents:
        doc_role = getattr(doc, "document_type", getattr(doc, "role", "UNKNOWN"))
        latest_ext = sorted(doc.extractions, key=lambda e: (e.created_at, str(e.id)), reverse=True)[0] if doc.extractions else None
        read_status = latest_ext.extraction_status if latest_ext else getattr(doc, "read_status", None)
        doc_data = {
            "id": str(doc.id),
            "filename": doc.filename,
            "role": doc_role,
            "format": doc.format,
            "validation_outcome": doc.validation_outcome,
            "read_status": read_status,
            "routing_outcome": doc.routing_outcome,
        }
        documents_info.append(doc_data)
        if doc_role in ("SI", "SHIPPING_INSTRUCTION"):
            si_document = doc_data
            if latest_ext:
                for f in latest_ext.fields:
                    si_fields_map[f.field_name] = {
                        "raw_label": f.raw_label,
                        "raw_value": f.raw_value,
                        "canonical_value": f.canonical_value,
                        "status": f.status,
                        "confidence": f.confidence,
                        "source_location": f.source_location,
                    }
        elif doc_role in ("DRAFT_BL", "BL"):
            bl_document = doc_data
            if latest_ext:
                for f in latest_ext.fields:
                    bl_fields_map[f.field_name] = {
                        "raw_label": f.raw_label,
                        "raw_value": f.raw_value,
                        "canonical_value": f.canonical_value,
                        "status": f.status,
                        "confidence": f.confidence,
                        "source_location": f.source_location,
                    }

    # Comparison summary & field table
    comparison_info: dict[str, Any] | None = None
    affected_fields: list[str] = []
    if comparison_record:
        fields_list = []
        for f in comparison_record.fields:
            if f.status in ("MISMATCH", "UNRESOLVED"):
                affected_fields.append(f.field_name)
            fields_list.append({
                "field": f.field_name,
                "status": f.status,
                "reason_code": f.reason_code,
                "si_value": si_fields_map.get(f.field_name, {}).get("raw_value"),
                "si_canonical": si_fields_map.get(f.field_name, {}).get("canonical_value"),
                "bl_value": bl_fields_map.get(f.field_name, {}).get("raw_value"),
                "bl_canonical": bl_fields_map.get(f.field_name, {}).get("canonical_value"),
            })
        comparison_info = {
            "id": str(comparison_record.id),
            "state": comparison_record.comparison_state,
            "mismatch_found": comparison_record.mismatch_found,
            "mismatched_fields": comparison_record.mismatched_fields or [],
            "unresolved_fields": comparison_record.unresolved_fields or [],
            "reason_code": comparison_record.reason_code,
            "fields": fields_list,
        }

    # User-friendly presentation
    presentation = present_reason(case.reason_code, affected_fields=affected_fields)

    # Active overrides
    active_overrides = [
        {
            "id": str(ov.id),
            "document_side": ov.document_side,
            "field": ov.field_name,
            "corrected_value": ov.corrected_value,
            "corrected_canonical_value": ov.corrected_canonical_value,
            "reviewer_name": ov.reviewer_name,
            "note": ov.note,
        }
        for ov in sorted(case.overrides, key=lambda r: (r.created_at, str(r.id)))
        if ov.active
    ]

    # Audit events
    events_info = [
        {
            "action": ev.action,
            "actor_name": ev.actor_name,
            "details": ev.details,
            "created_at": ev.created_at.isoformat(),
        }
        for ev in sorted(case.events, key=lambda r: (r.created_at, str(r.id)))
    ]

    return {
        "case_id": str(case.id),
        "email_id": str(email.id),
        "subject": email.subject,
        "sender": email.sender,
        "received_at": email.received_at.isoformat() if email.received_at else None,
        "processing_status": email.processing_status,
        "category": latest_classification.category if latest_classification else None,
        "comparison_readiness": latest_classification.comparison_readiness if latest_classification else None,
        "review_status": case.status,
        "case_origin": case.case_origin,
        "reason_code": case.reason_code,
        "reason_text": case.reason_text,
        "presentation_title": presentation.title,
        "human_explanation": presentation.explanation,
        "affected_area": presentation.affected_area,
        "suggested_action": presentation.suggested_action,
        "affected_fields": affected_fields,
        "documents": documents_info,
        "si_document": si_document,
        "bl_document": bl_document,
        "si_extracted_fields": si_fields_map,
        "bl_extracted_fields": bl_fields_map,
        "comparison": comparison_info,
        "active_overrides": active_overrides,
        "recent_events": events_info,
    }
