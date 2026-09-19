"""Comparison readiness is a post-classification decision, not a category."""
from __future__ import annotations

import re

from backend.app.classification.models import ClassificationInput
from backend.app.classification.signals import EmailCategory

READY_FOR_COMPARISON = "READY_FOR_COMPARISON"
AWAITING_DOCUMENTS = "AWAITING_DOCUMENTS"
UNRESOLVED = "UNRESOLVED"

_SI_FIELD_MARKERS = ("shipper", "consignee", "notify party", "port of loading", "port of discharge", "container", "gross weight")
_REQUEST_TO_SEND_BL = re.compile(r"\b(send|provide|revert with|issue)\b.{0,48}\b(draft\s+bl|draft\s+bill\s+of\s+lading)\b", re.I | re.S)
_CHECKING = re.compile(r"\b(check|checking|compare|verify|review)\b", re.I)


def has_dense_si_content(text: str) -> bool:
    lowered = text.lower()
    return sum(marker in lowered for marker in _SI_FIELD_MARKERS) >= 3


def evaluate_readiness(email: ClassificationInput, category: str) -> str | None:
    """Return a readiness state only for final document-comparison emails."""
    if category != EmailCategory.DOCUMENT_COMPARISON.value:
        return None
    text = f"{email.subject}\n{email.body}"
    if email.attachment_count >= 2:
        return READY_FOR_COMPARISON
    if _REQUEST_TO_SEND_BL.search(text) and _CHECKING.search(text) and not has_dense_si_content(text):
        return AWAITING_DOCUMENTS
    return UNRESOLVED
