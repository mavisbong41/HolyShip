"""Shared deterministic user-facing semantics for Human Review.

This module is the authoritative presentation contract for Dashboard and Outlook.
Internal reason/status codes remain available for audit/diagnostics, but normal
product UI should consume these semantic fields.
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class ReviewPresentation:
    title: str
    explanation: str
    affected_area: str
    suggested_action: str
    semantic_style: str

REVIEW_STATUS_PRESENTATION = {
    "OPEN": ("Needs review", "This case needs a human decision before processing can continue.", "Human Review", "Open Human Review", "attention"),
    "IN_REVIEW": ("Being reviewed", "A reviewer is currently working on this case.", "Human Review", "Continue review", "attention"),
    "RESOLVED": ("Review completed", "The review decision was applied and the case was re-compared.", "Human Review", "View comparison result", "good"),
    "DISMISSED": ("Review dismissed", "The review was dismissed and no further review action is required.", "Human Review", "View review record", "muted"),
}
PROCESSING_STATUS_PRESENTATION = {
    "AWAITING_DOCUMENTS": ("Waiting for required documents", "HolyShip is waiting for the required shipping document before comparison can begin.", "Documents", "Provide the required document", "info"),
    "FAILED": ("Processing failed", "HolyShip could not finish processing this email.", "Processing", "Retry / Reprocess", "bad"),
    "BLOCKED": ("Needs attention", "Processing cannot continue until the business issue is reviewed.", "Processing", "Open Human Review", "attention"),
    "COMPLETED": ("Completed", "HolyShip finished processing this email.", "Processing", "View result", "good"),
}
REASON_PRESENTATION = {
    "CLASSIFICATION_UNRESOLVED": ("Email type unclear", "HolyShip could not confidently determine what this email is asking for.", "Email intent", "Confirm the email type in Human Review", "attention"),
    "COMPARISON_UNRESOLVED": ("One or more document fields could not be verified", "The SI and BL evidence was not sufficient to determine one or more field values confidently.", "Document fields", "Review the unresolved fields", "attention"),
    "COMPARISON_MISMATCH": ("The SI and BL contain different values", "One or more shipping-document fields do not agree between the SI and BL.", "Document fields", "Review the mismatched fields", "attention"),
    "DOCUMENT_ROLE_UNRESOLVED": ("Document role unclear", "HolyShip could not confidently identify which document is the SI or BL.", "Documents", "Confirm the document roles", "attention"),
    "WRONG_DOCUMENT_TYPE": ("Wrong document type", "The attached file does not appear to be the required shipping document.", "Documents", "Confirm the attached document", "attention"),
    "MISSING_REQUIRED_ATTACHMENT": ("Required shipping document is missing", "A required shipping document is not available for comparison.", "Documents", "Provide the required document", "attention"),
    "UNREADABLE_ATTACHMENT": ("Document could not be read reliably", "The attached document could not be read reliably.", "Documents", "Check or replace the document", "attention"),
    "UNSUPPORTED_ATTACHMENT": ("Document format is unsupported", "HolyShip cannot process the attached document format.", "Documents", "Provide a supported document", "attention"),
    "CORRUPTED_ATTACHMENT": ("Document could not be read", "The attached document appears to be corrupted or invalid.", "Documents", "Replace the document", "attention"),
    "MULTIPLE_CANDIDATES": ("More than one document may match", "More than one document may match the required shipping-document role.", "Documents", "Confirm the correct document", "attention"),
    "READINESS_UNRESOLVED": ("Document readiness unclear", "HolyShip is unsure whether the documents are ready for comparison.", "Documents", "Review document readiness", "attention"),
    "STAGE2_UNRESOLVED": ("Email type unclear (historical)", "HolyShip could not confidently determine what this email is asking for.", "Email intent", "View history", "muted"),
    "OCR_BACKEND_UNAVAILABLE": ("Document processing unavailable", "OCR service is not available in the current environment. Retry after OCR is available.", "Processing", "Retry / Reprocess", "bad"),
}

FIELD_LABELS = {
    "shipper": "Shipper",
    "consignee": "Consignee",
    "notify_party": "Notify Party",
    "port_of_loading": "Port of Loading",
    "port_of_discharge": "Port of Discharge",
    "container_count": "Container Count",
    "gross_weight_kg": "Gross Weight",
}

def present_reason(reason_code: str, *, affected_fields: list[str] | None = None) -> ReviewPresentation:
    base = REASON_PRESENTATION.get(reason_code)
    if base:
        title, explanation, area, action, style = base
        if reason_code in {"COMPARISON_UNRESOLVED", "COMPARISON_MISMATCH"} and affected_fields:
            labels = ", ".join(FIELD_LABELS.get(f, f.replace("_", " ").title()) for f in affected_fields)
            explanation = f"{explanation} Affected fields: {labels}."
        return ReviewPresentation(title, explanation, area, action, style)
    if reason_code in REVIEW_STATUS_PRESENTATION:
        title, explanation, area, action, style = REVIEW_STATUS_PRESENTATION[reason_code]
        return ReviewPresentation(title, explanation, area, action, style)
    title = reason_code.replace("_", " ").title()
    return ReviewPresentation(title, "Technical details are available in the review record.", "Review case", "Open Human Review", "attention")

def present_review_status(status: str) -> ReviewPresentation:
    values = REVIEW_STATUS_PRESENTATION.get(status)
    if values:
        return ReviewPresentation(*values)
    return present_reason(status)

def present_processing_status(status: str) -> ReviewPresentation:
    values = PROCESSING_STATUS_PRESENTATION.get(status)
    if values:
        return ReviewPresentation(*values)
    return ReviewPresentation(status.replace("_", " ").title(), "HolyShip is processing this email.", "Processing", "View email", "neutral")
