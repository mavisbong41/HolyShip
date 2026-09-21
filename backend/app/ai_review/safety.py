from __future__ import annotations

from typing import Any
from backend.app.ai_review.schema import AIStructuredResponse, ALLOWED_REVIEW_FIELDS

UNSAFE_BLOCK_REASONS = frozenset({
    "MISSING_REQUIRED_ATTACHMENT",
    "WRONG_DOCUMENT_TYPE",
    "UNREADABLE_ATTACHMENT",
    "UNSUPPORTED_ATTACHMENT",
    "CORRUPTED_ATTACHMENT",
    "READINESS_UNRESOLVED",
})


def evaluate_safety_gate(
    context: dict[str, Any],
    response: AIStructuredResponse,
    *,
    confidence_threshold: float = 0.7,
) -> AIStructuredResponse:
    """Ensure actionable suggestions are strictly backed by safe, verified evidence."""
    if response.mode != "ACTIONABLE_SUGGESTION":
        return response

    suggestion = response.suggestion
    if suggestion is None:
        return AIStructuredResponse(
            mode="INSUFFICIENT_EVIDENCE",
            message=response.message or "No actionable suggestion could be formulated.",
            suggestion=None,
        )

    # Check allowed fields
    if suggestion.field not in ALLOWED_REVIEW_FIELDS:
        return AIStructuredResponse(
            mode="EXPLANATION_ONLY",
            message=f"{response.message} Note: Suggestions are only supported for the 7 canonical fields.",
            suggestion=None,
        )

    # Check evidence refs
    if not suggestion.evidence_refs:
        return AIStructuredResponse(
            mode="INSUFFICIENT_EVIDENCE",
            message=f"{response.message} (Actionable suggestion rejected due to lack of source evidence refs).",
            suggestion=None,
        )

    # Check confidence threshold
    if suggestion.confidence < confidence_threshold:
        return AIStructuredResponse(
            mode="EXPLANATION_ONLY",
            message=f"{response.message} (Confidence {suggestion.confidence:.2f} is below the safety threshold of {confidence_threshold:.2f}).",
            suggestion=None,
        )

    # Check case-level unsafe conditions
    reason_code = context.get("reason_code", "")
    if reason_code in UNSAFE_BLOCK_REASONS:
        return AIStructuredResponse(
            mode="EXPLANATION_ONLY",
            message=f"{response.message} No actionable override can be proposed because the case is blocked due to {context.get('presentation_title', reason_code)}.",
            suggestion=None,
        )

    # Check presence of both SI and BL documents
    si_doc = context.get("si_document")
    bl_doc = context.get("bl_document")
    if not si_doc or not bl_doc:
        return AIStructuredResponse(
            mode="EXPLANATION_ONLY",
            message=f"{response.message} Both SI and Draft BL documents must be present to formulate a safe override suggestion.",
            suggestion=None,
        )

    return response
