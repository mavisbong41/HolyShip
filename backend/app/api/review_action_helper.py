from backend.app.api.product_schemas import ProductReviewOverride, ProductReviewAction

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
