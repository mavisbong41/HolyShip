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
    DOCUMENT_COMPARISON = "document_comparison"
    NEW_SI_REQUEST      = "new_si_request"
    INVOICE_QUERY       = "invoice_query"
    GENERAL_MESSAGE     = "general_message"
    SPAM                = "spam"


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
        SignalPattern("confirm the bl",                         weight=2.0),
        SignalPattern("confirm draft bl",                       weight=2.0),
        SignalPattern("confirm the draft bl",                   weight=2.0),
        SignalPattern("confirm bl is in order",                 weight=2.2),
        SignalPattern("confirm the bl is in order",             weight=2.5),
        SignalPattern("bl is in order",                         weight=2.0),
        SignalPattern("check the bl",                           weight=1.8),
        SignalPattern("review the bl",                          weight=1.8),
        SignalPattern("verify the bl",                          weight=1.8),
        SignalPattern("confirm the draft",                      weight=1.5),
        SignalPattern("check the details",                      weight=1.2),
        # Action-specific forms supporting comparison / awaiting workflow
        SignalPattern("send the draft bl",                      weight=1.8),
        SignalPattern("send draft bl",                          weight=1.8),
        SignalPattern("provide the draft bl",                   weight=1.8),
        SignalPattern("provide draft bl",                       weight=1.8),
        SignalPattern("issue the draft bl",                     weight=1.8),
        SignalPattern("issue draft bl",                         weight=1.8),
        SignalPattern("bill of lading",                         weight=0.8),
        SignalPattern("to confirm docs",                        weight=1.8),
        SignalPattern("confirm docs",                           weight=1.6),
        SignalPattern("bl draft",                               weight=1.0),
        SignalPattern("check the draft bl against the si",      weight=3.0),
        SignalPattern("draft bl against the si",                weight=2.8),
        SignalPattern("check the draft bl",                     weight=2.5),
        SignalPattern("revert with any discrepancy",            weight=2.2),
    ],
    EmailCategory.NEW_SI_REQUEST: [
        SignalPattern("prepare shipping instruction",           weight=3.0),
        SignalPattern("create shipping instruction",            weight=3.0),
        SignalPattern("submit shipping instruction",            weight=3.0),
        SignalPattern("new shipping instruction",               weight=2.5),
        # Dataset dominant pattern: "Please find Shipping instruction for ..."
        SignalPattern("please find shipping instruction",       weight=2.8),
        SignalPattern("find shipping instruction",              weight=2.5),
        SignalPattern("shipping instruction for",               weight=1.8),
        SignalPattern("request si",                             weight=2.5),
        SignalPattern("si needed",                              weight=2.0),
        SignalPattern("cust si",                                weight=2.0),
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
        SignalPattern("invoice discrepancy",                    weight=2.5),
        SignalPattern("invoice status",                         weight=2.0),
        SignalPattern("commercial invoice",                     weight=1.0),
        SignalPattern("charge",                                 weight=0.8),
        SignalPattern("payment",                                weight=0.8),
        SignalPattern("billing",                                weight=0.8),
        SignalPattern("invoice",                                weight=0.8),
    ],
    EmailCategory.GENERAL_MESSAGE: [
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
        SignalPattern("daily berthing report",                  weight=3.0),
        SignalPattern("berthing report",                        weight=2.5),
        SignalPattern("reminder please submit si",              weight=3.0),
        SignalPattern("pending shipments by end of day",        weight=2.5),
        SignalPattern("time off request",                       weight=3.0),
        SignalPattern("welcoming the new year",                 weight=3.0),
        SignalPattern("happy and prosperous new year",          weight=3.0),
        SignalPattern("india hss sd billing process completed", weight=2.5),
        SignalPattern("billing process for",                    weight=2.0),
        SignalPattern("pending bl release",                     weight=2.5),
        SignalPattern("miss connection",                        weight=2.5),
    ],
    EmailCategory.SPAM: [
        SignalPattern("congratulations you have won",           weight=5.0),
        SignalPattern("you have won",                           weight=4.5),
        SignalPattern("won a brand new",                        weight=4.5),
        SignalPattern("win a prize",                            weight=5.0),
        SignalPattern("click here to claim",                    weight=5.0),
        SignalPattern("to claim simply complete",               weight=4.5),
        SignalPattern("complete this short survey",             weight=4.0),
        SignalPattern("update your account to avoid suspension",weight=5.0),
        SignalPattern("avoid suspension",                       weight=4.0),
        SignalPattern("account suspension",                     weight=4.0),
        SignalPattern("limited time offer",                     weight=4.0),
        SignalPattern("weird trick",                            weight=4.0),
        SignalPattern("mailbox has exceeded",                   weight=4.0),    # phishing IT alert
        SignalPattern("exceeded its storage limit",             weight=4.0),    # phishing IT alert
        SignalPattern("increase your shipping revenue",         weight=3.5),    # promotional junk
        SignalPattern("unsubscribe",                            weight=2.0),
        SignalPattern("promotional",                            weight=2.0),
        SignalPattern("advertisement",                          weight=2.0),
        SignalPattern("special offer",                          weight=3.0),
        SignalPattern("free trial",                             weight=3.0),
        SignalPattern("bank officer",                           weight=5.0),
        SignalPattern("business proposal involving usd",        weight=5.0),
        SignalPattern("bitcoin",                                weight=5.0),
        SignalPattern("cryptocurrency",                         weight=5.0),
        SignalPattern("90 off",                                 weight=4.5),
        SignalPattern("your email storage is full",             weight=4.5),
        SignalPattern("storage is full",                        weight=4.0),
        SignalPattern("hot singles",                            weight=5.0),
        SignalPattern("congratulations",                        weight=4.0),
        SignalPattern("gift card",                              weight=4.5),
        SignalPattern("unpaid customs fee",                     weight=4.5),
        SignalPattern("undelivered messages in your mailbox",   weight=4.5),
        SignalPattern("undelivered messages",                   weight=4.0),
        SignalPattern("guaranteed 300 returns",                 weight=4.5),
    ],
}

# Categories that require genuine evidence before routing to Stage 2
# (not just an empty body / placeholder text)
EVIDENCE_REQUIRED_CATEGORIES = {
    EmailCategory.DOCUMENT_COMPARISON,
    EmailCategory.NEW_SI_REQUEST,
    EmailCategory.INVOICE_QUERY,
}
