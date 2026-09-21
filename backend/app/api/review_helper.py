from datetime import datetime, timezone

from backend.app.api.presentation import present_reason


def compute_affected_fields(row, comparison) -> list[str]:
    if row.field_name:
        return [row.field_name]
    if comparison:
        return sorted(list(set(comparison.mismatched_fields + comparison.unresolved_fields)))
    return []


def compute_priority(row, affected_fields: list[str]) -> str:
    if row.reason_code in {
        "MISSING_REQUIRED_ATTACHMENT", "WRONG_DOCUMENT_TYPE",
        "UNREADABLE_ATTACHMENT", "UNSUPPORTED_ATTACHMENT",
        "CORRUPTED_ATTACHMENT", "MULTIPLE_CANDIDATES",
        "DOCUMENT_ROLE_UNRESOLVED", "READINESS_UNRESOLVED"
    }:
        return "HIGH"
    if len(affected_fields) > 1:
        return "HIGH"
    if "gross_weight_kg" in affected_fields or "container_count" in affected_fields:
        return "MEDIUM"
    return "LOW"


def compute_human_explanation(row, affected_fields: list[str]) -> str:
    return present_reason(row.reason_code, affected_fields=affected_fields).explanation


def compute_review_presentation(row, affected_fields: list[str]):
    return present_reason(row.reason_code, affected_fields=affected_fields)


def compute_age_minutes(created_at: datetime) -> int:
    now = datetime.now(timezone.utc)
    delta = now - created_at
    return max(0, int(delta.total_seconds() / 60))
