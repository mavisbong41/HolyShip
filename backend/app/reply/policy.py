from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

ReplyMode = Literal["REQUEST_INFORMATION", "RESOLUTION_REPLY"]

REQUEST_INFORMATION_REASONS = frozenset({
    "READINESS_UNRESOLVED",
    "MISSING_REQUIRED_ATTACHMENT",
    "WRONG_DOCUMENT_TYPE",
    "UNREADABLE_ATTACHMENT",
    "UNSUPPORTED_ATTACHMENT",
    "CORRUPTED_ATTACHMENT",
    "MULTIPLE_CANDIDATES",
    "DOCUMENT_ROLE_UNRESOLVED",
    "COMPARISON_UNRESOLVED",
    "MISSING_SI",
    "MISSING_BL",
    "MULTIPLE_SI_CANDIDATES",
    "MULTIPLE_BL_CANDIDATES",
    "DOCUMENT_TYPE_UNCERTAIN",
})


@dataclass(frozen=True)
class ReplyPolicy:
    allowed: bool
    mode: ReplyMode | None
    reason: str
    missing_or_required_items: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "mode": self.mode,
            "reason": self.reason,
            "missing_or_required_items": self.missing_or_required_items,
        }


def evaluate_reply_policy(
    *,
    email_id: object | None,
    processing_status: str | None,
    comparison_state: str | None,
    mismatched_fields: list[Any] | None,
    unresolved_fields: list[Any] | None,
    reason_code: str | None,
) -> ReplyPolicy:
    mismatches = list(mismatched_fields or [])
    unresolved = list(unresolved_fields or [])
    required = [str(item) for item in unresolved + mismatches]
    if reason_code in {"MISSING_REQUIRED_ATTACHMENT", "MISSING_SI", "MISSING_BL"}:
        required.append("the required Shipping Instruction or Draft BL")
    elif reason_code in {"WRONG_DOCUMENT_TYPE", "DOCUMENT_ROLE_UNRESOLVED", "DOCUMENT_TYPE_UNCERTAIN"}:
        required.append("a confirmed Shipping Instruction and Draft BL document role")
    elif reason_code in {"UNREADABLE_ATTACHMENT", "UNSUPPORTED_ATTACHMENT", "CORRUPTED_ATTACHMENT"}:
        required.append("a readable replacement shipping document")
    elif reason_code in {"READINESS_UNRESOLVED", "MULTIPLE_CANDIDATES", "MULTIPLE_SI_CANDIDATES", "MULTIPLE_BL_CANDIDATES"}:
        required.append("sender confirmation of the correct comparison documents")
    elif reason_code == "COMPARISON_UNRESOLVED":
        required.append("sender confirmation for the unresolved comparison fields")
    required = list(dict.fromkeys(required))

    if not email_id:
        return ReplyPolicy(False, None, "A valid email_id is required.", required)
    if processing_status == "FAILED":
        return ReplyPolicy(False, None, "Reply is unavailable while technical processing has failed.", required)
    if processing_status == "COMPLETED" and comparison_state == "COMPLETED" and not unresolved and not mismatches:
        return ReplyPolicy(True, "RESOLUTION_REPLY", "Latest comparison completed with no remaining issues.", [])
    if processing_status == "BLOCKED" and reason_code not in REQUEST_INFORMATION_REASONS:
        return ReplyPolicy(False, None, "Reply is unavailable because the blocking reason is not requestable information.", required)
    if processing_status == "BLOCKED" or processing_status == "AWAITING_DOCUMENTS" or unresolved or mismatches or reason_code in REQUEST_INFORMATION_REASONS:
        if not required:
            required = ["sender/customer confirmation of the missing or uncertain information"]
        return ReplyPolicy(True, "REQUEST_INFORMATION", "External information is required before verification can complete.", required)
    return ReplyPolicy(False, None, "Reply is unavailable until the latest comparison is complete and its remaining issues are resolved.", required)
