"""Isolated adapter from rich internal workflow state to the public bundle shape."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any


_CATEGORY_MAP = {
    "document_comparison": "BL_COMPARISON",
    "new_si_request": "SI_REQUEST",
    "invoice_query": "INVOICE_QUERY",
    "general_message": "GENERAL",
    "spam": "SPAM",
    "DOCUMENT_COMPARISON": "BL_COMPARISON",
    "NEW_SI_REQUEST": "SI_REQUEST",
    "INVOICE_QUERY": "INVOICE_QUERY",
    "GENERAL_MAIL": "GENERAL",
    "SPAM": "SPAM",
}
_PUBLIC_CATEGORIES = frozenset(_CATEGORY_MAP.values())
AWAITING_DOCUMENTS_MAPPING_VALIDATED = False

_REVIEW_REASON_BY_INTERNAL_REASON = {
    "WRONG_DOCUMENT_TYPE": "wrong_doc_type",
    "MISSING_REQUIRED_ATTACHMENT": "missing_attachment",
    "UNREADABLE_ATTACHMENT": "unreadable",
    "CORRUPTED_ATTACHMENT": "unreadable",
    "UNSUPPORTED_ATTACHMENT": "unreadable",
    "DOCUMENT_READER_FAILED": "unreadable",
    "ATTACHMENT_READ_FAILED": "unreadable",
    "DOCUMENT_FIELD_EXTRACTION_FAILED": "unreadable",
    "COMPARISON_UNRESOLVED": "missing_value",
    "READINESS_UNRESOLVED": "missing_value",
    "DOCUMENT_ROLE_UNRESOLVED": "missing_value",
    "MULTIPLE_CANDIDATES": "missing_value",
}


@dataclass(frozen=True)
class SubmissionWorkflowOutcome:
    processing_status: str
    reason_code: str | None
    mismatch_found: bool
    mismatched_fields: tuple[str, ...]
    unresolved_fields: tuple[str, ...]


def to_submission_entry(
    category: str,
    candidate_scores: dict[str, float] | None = None,
    *,
    workflow: SubmissionWorkflowOutcome | None = None,
) -> dict[str, Any]:
    """Compress internal state only at the participant-contract boundary.

    Legacy ``UNCERTAIN`` is accepted only for historical-record export. Its highest-scoring supported candidate is
    used as a temporary baseline category; it is never emitted as a sixth
    public category.
    """
    public_category = _CATEGORY_MAP.get(category)
    if public_category is None:
        scores = candidate_scores or {}
        supported = [
            (_CATEGORY_MAP.get(name), score)
            for name, score in scores.items()
            if _CATEGORY_MAP.get(name) in _PUBLIC_CATEGORIES
        ]
        public_category = max(supported, key=lambda item: item[1])[0] if supported else "GENERAL"

    if public_category != "BL_COMPARISON":
        return {
            "category": public_category,
            "status": "OK",
            "review_reason": None,
            "defect_fields": [],
            "has_defect": False,
        }

    if workflow is not None and workflow.processing_status == "COMPLETED":
        if workflow.unresolved_fields:
            return _needs_review(public_category, "missing_value")
        if workflow.mismatch_found:
            return {
                "category": public_category,
                "status": "MISMATCH",
                "review_reason": None,
                "defect_fields": list(workflow.mismatched_fields),
                "has_defect": True,
            }
        return {
            "category": public_category,
            "status": "OK",
            "review_reason": None,
            "defect_fields": [],
            "has_defect": False,
        }

    if workflow is not None and workflow.processing_status == "AWAITING_DOCUMENTS":
        # The public contract has no awaiting state. Preserve the existing
        # provisional missing-value boundary mapping, but keep it explicitly
        # marked unvalidated until public documentation or organizer feedback
        # establishes an authoritative representation.
        return _needs_review(public_category, "missing_value")

    if workflow is not None:
        review_reason = _REVIEW_REASON_BY_INTERNAL_REASON.get(
            workflow.reason_code or "",
            "missing_value",
        )
        return _needs_review(public_category, review_reason)

    # Backward-compatible export for historical classification-only records.
    return _needs_review(public_category, "missing_value")


def _needs_review(category: str, reason: str) -> dict[str, Any]:
    return {
        "category": category,
        "status": "NEEDS_REVIEW",
        "review_reason": reason,
        "defect_fields": [],
        "has_defect": False,
    }


def build_submission(
    rows: Iterable[tuple[str, str, dict[str, float] | None]],
    workflow_by_email: dict[str, SubmissionWorkflowOutcome] | None = None,
) -> dict[str, dict[str, Any]]:
    """Build one entry per public email id, keyed exactly as the bundle requires."""
    workflows = workflow_by_email or {}
    return {
        email_id: to_submission_entry(
            category,
            scores,
            workflow=workflows.get(email_id),
        )
        for email_id, category, scores in rows
    }
