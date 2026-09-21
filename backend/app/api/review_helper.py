from datetime import datetime, timezone

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
    code = row.reason_code
    if code == "MISSING_REQUIRED_ATTACHMENT":
        return "Required document is missing. Confirm whether the correct BL has been attached."
    if code == "WRONG_DOCUMENT_TYPE":
        return "Attachment appears to be the wrong document type. Confirm the attached document."
    if code == "UNREADABLE_ATTACHMENT":
        return "The attachment could not be read. Please check if the file is valid."
    if code == "READINESS_UNRESOLVED":
        return "System could not determine if documents are ready. Please review the email intent."
    if code == "COMPARISON_UNRESOLVED":
        fields_str = ", ".join(affected_fields) if affected_fields else "unknown fields"
        return f"Needs Human Review. The following fields could not be determined confidently: {fields_str}."
    if code == "COMPARISON_MISMATCH":
        fields_str = ", ".join(affected_fields) if affected_fields else "unknown fields"
        return f"Needs Human Review. There is a mismatch between the SI and BL for: {fields_str}."
    
    return code.replace("_", " ").title()

def compute_age_minutes(created_at: datetime) -> int:
    now = datetime.now(timezone.utc)
    delta = now - created_at
    return int(delta.total_seconds() / 60)
