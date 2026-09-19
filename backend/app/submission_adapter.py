"""Phase-0 adapter from legacy classification records to the public bundle shape.

This is intentionally a boundary adapter: it does not change the legacy
classifier or persistence model.  Comparison work is not implemented yet, so
legacy document-comparison results are honestly emitted as NEEDS_REVIEW.
"""

from __future__ import annotations

from collections.abc import Iterable
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


def to_submission_entry(category: str, candidate_scores: dict[str, float] | None = None) -> dict[str, Any]:
    """Return a public-contract entry without inventing comparison results.

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

    if public_category == "BL_COMPARISON":
        return {
            "category": public_category,
            "status": "NEEDS_REVIEW",
            "review_reason": "missing_value",
            "defect_fields": [],
            "has_defect": False,
        }
    return {
        "category": public_category,
        "status": "OK",
        "review_reason": None,
        "defect_fields": [],
        "has_defect": False,
    }


def build_submission(rows: Iterable[tuple[str, str, dict[str, float] | None]]) -> dict[str, dict[str, Any]]:
    """Build one entry per public email id, keyed exactly as the bundle requires."""
    return {email_id: to_submission_entry(category, scores) for email_id, category, scores in rows}
