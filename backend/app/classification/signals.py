from __future__ import annotations

"""
Centralized category signals for Stage 1 classification.

Each entry is a list of patterns (lowercase). A pattern matches if
the entire phrase appears as a contiguous token sequence in the
normalised text (case-insensitive, punctuation-tolerant).

Patterns are weighted: longer / more specific patterns beat shorter ones.
"""

from dataclasses import dataclass, field
from enum import Enum


class EmailCategory(str, Enum):
    DOCUMENT_COMPARISON = "DOCUMENT_COMPARISON"
    NEW_SI_REQUEST      = "NEW_SI_REQUEST"
    INVOICE_QUERY       = "INVOICE_QUERY"
    GENERAL_MAIL        = "GENERAL_MAIL"
    SPAM                = "SPAM"
    UNCERTAIN           = "UNCERTAIN"


@dataclass(frozen=True)
class SignalPattern:
    phrase: str
    weight: float = 1.0


# ---------------------------------------------------------------------------
# Category → signal patterns
# ---------------------------------------------------------------------------
CATEGORY_SIGNALS: dict[EmailCategory, list[SignalPattern]] = {
    EmailCategory.DOCUMENT_COMPARISON: [
        # Very strong: explicit compare/verify SI vs BL
        SignalPattern("compare the attached si and draft bl",   weight=3.0),
        SignalPattern("compare si and bl",                      weight=2.5),
        SignalPattern("compare the si and bl",                  weight=2.5),
        SignalPattern("compare the attached si and bl",         weight=2.5),
        SignalPattern("compare the si and draft bl",            weight=2.5),
        SignalPattern("compare the si and bl draft",            weight=2.5),
        SignalPattern("si and draft bl",                        weight=2.0),
        SignalPattern("shipping instruction and draft bl",      weight=2.0),
        SignalPattern("shipping instruction and draft bill of lading", weight=2.0),
        SignalPattern("verify draft bl",                        weight=2.0),
        SignalPattern("verify the draft bl",                    weight=2.0),
        SignalPattern("validate draft bl",                      weight=2.0),
        SignalPattern("check the details and confirm",          weight=1.8),
        SignalPattern("compare the attached shipping instruction", weight=1.8),
        SignalPattern("check draft bl",                         weight=1.8),
        SignalPattern("review bl against si",                   weight=1.8),
        SignalPattern("bl against the shipping instruction",    weight=1.8),
        SignalPattern("confirm the bl",                         weight=1.5),
        SignalPattern("confirm the draft",                      weight=1.3),
        SignalPattern("check the details",                      weight=1.2),
        SignalPattern("draft bl",                               weight=1.2),
        SignalPattern("draft bill of lading",                   weight=1.2),
        SignalPattern("bill of lading",                         weight=0.8),
        SignalPattern("to confirm docs",                        weight=1.5),
        SignalPattern("confirm docs",                           weight=1.4),
        SignalPattern("bl draft",                               weight=1.0),
    ],
    EmailCategory.NEW_SI_REQUEST: [
        SignalPattern("prepare shipping instruction",           weight=3.0),
        SignalPattern("create shipping instruction",            weight=3.0),
        SignalPattern("submit shipping instruction",            weight=3.0),
        SignalPattern("new shipping instruction",               weight=2.5),
        SignalPattern("create si",                              weight=2.5),
        SignalPattern("prepare si",                             weight=2.5),
        SignalPattern("submit si",                              weight=2.5),
        SignalPattern("new si",                                 weight=2.0),
        SignalPattern("kindly prepare the si",                  weight=2.0),
        SignalPattern("please prepare the si",                  weight=2.0),
        SignalPattern("request bl draft",                       weight=1.5),
        SignalPattern("request bl",                             weight=1.2),
    ],
    EmailCategory.INVOICE_QUERY: [
        SignalPattern("clarify this payment",                   weight=2.5),
        SignalPattern("payment amount",                         weight=2.0),
        SignalPattern("invoice question",                       weight=2.5),
        SignalPattern("billing query",                          weight=2.5),
        SignalPattern("billing question",                       weight=2.5),
        SignalPattern("clarify invoice",                        weight=2.5),
        SignalPattern("invoice charges",                        weight=2.0),
        SignalPattern("commercial invoice",                     weight=1.5),
        SignalPattern("charge",                                 weight=0.8),
        SignalPattern("payment",                                weight=0.8),
        SignalPattern("billing",                                weight=0.8),
        SignalPattern("invoice",                                weight=1.0),
    ],
    EmailCategory.GENERAL_MAIL: [
        SignalPattern("operational update",                     weight=2.5),
        SignalPattern("update summary",                         weight=2.0),
        SignalPattern("outstanding bl",                         weight=1.5),
        SignalPattern("please find attached",                   weight=0.6),
        SignalPattern("please find enclosed",                   weight=0.6),
        SignalPattern("fyi",                                    weight=1.5),
        SignalPattern("for your information",                   weight=1.5),
        SignalPattern("for your reference",                     weight=1.2),
        SignalPattern("kindly action",                          weight=1.2),
        SignalPattern("kindly note",                            weight=0.8),
        SignalPattern("information only",                       weight=1.5),
        SignalPattern("no action required",                     weight=2.0),
    ],
    EmailCategory.SPAM: [
        SignalPattern("congratulations you have won",           weight=5.0),
        SignalPattern("click here to claim",                    weight=5.0),
        SignalPattern("limited time offer",                     weight=4.0),
        SignalPattern("unsubscribe",                            weight=2.0),
        SignalPattern("promotional",                            weight=2.0),
        SignalPattern("advertisement",                          weight=2.0),
        SignalPattern("special offer",                          weight=3.0),
        SignalPattern("free trial",                             weight=3.0),
    ],
}

# Categories that require genuine evidence before routing to Stage 2
# (not just an empty body / placeholder text)
EVIDENCE_REQUIRED_CATEGORIES = {
    EmailCategory.DOCUMENT_COMPARISON,
    EmailCategory.NEW_SI_REQUEST,
    EmailCategory.INVOICE_QUERY,
}
