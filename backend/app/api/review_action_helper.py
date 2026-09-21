from backend.app.api.product_schemas import (
    ProductAISuggestion,
    ProductReviewAction,
    ProductReviewOverride,
)

def _review_override(row) -> ProductReviewOverride:
    return ProductReviewOverride(
        id=row.id,
        field=row.field_name,
        document_side=row.document_side,
        original_field_id=row.original_field_id,
        corrected_value=row.corrected_value,
        corrected_canonical_value=row.corrected_canonical_value,
        reviewer_name=row.reviewer_name,
        note=row.note,
        active=row.active,
        supersedes_override_id=row.supersedes_override_id,
        ai_suggestion_id=getattr(row, "ai_suggestion_id", None),
        created_at=row.created_at,
    )

def _review_action(row) -> ProductReviewAction:
    return ProductReviewAction(
        id=row.id,
        action=row.action,
        actor_name=row.actor_name,
        details=row.details,
        created_at=row.created_at,
    )

def _review_ai_suggestion(row) -> ProductAISuggestion:
    return ProductAISuggestion(
        id=row.id,
        human_review_case_id=row.human_review_case_id,
        mode=row.mode,
        message=row.message,
        document_side=row.document_side,
        field=row.field,
        current_value=row.current_value,
        suggested_value=row.suggested_value,
        confidence=row.confidence,
        reason=row.reason,
        evidence_refs=row.evidence_refs or [],
        provider_name=row.provider_name,
        provider_model=row.provider_model,
        status=row.status,
        created_at=row.created_at,
    )
