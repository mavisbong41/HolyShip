from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from backend.app.documents.models import DocumentType, UnifiedDocument


class RoleValidationOutcome(str, Enum):
    VALID = "VALID"
    WRONG_DOCUMENT_TYPE = "WRONG_DOCUMENT_TYPE"
    INCONCLUSIVE = "INCONCLUSIVE"


@dataclass(frozen=True)
class RoleValidationResult:
    document_type: DocumentType
    outcome: RoleValidationOutcome
    confidence: float
    markers: list[str] = field(default_factory=list)
    evidence: str = ""


class DocumentRoleValidator:
    """Assign SI/BL roles from materialized content, never from a filename alone."""

    WRONG_TYPE_MARKERS = (
        "COMMERCIAL INVOICE",
        "PACKING LIST",
        "CERTIFICATE OF ORIGIN",
    )
    SI_MARKERS = (
        "SHIPPING INSTRUCTION",
        "BILL OF LADING INSTRUCTION",
        "BL INSTRUCTION:",
        "SHIPPING INSTRUCTIONS",
    )
    BL_PATTERNS = (
        re.compile(r"\bBILL OF LADING\s*\(DRAFT\)", re.IGNORECASE),
        re.compile(r"\bDRAFT\s+BILL OF LADING\b", re.IGNORECASE),
        re.compile(r"\bDRAFT\s+BL\b", re.IGNORECASE),
        re.compile(r"^BILL OF LADING\s*:", re.IGNORECASE | re.MULTILINE),
    )

    def validate(self, document: UnifiedDocument) -> RoleValidationResult:
        content = self._content(document).upper()
        wrong_markers = [marker for marker in self.WRONG_TYPE_MARKERS if marker in content]
        if wrong_markers:
            return RoleValidationResult(
                document_type=DocumentType.OTHER,
                outcome=RoleValidationOutcome.WRONG_DOCUMENT_TYPE,
                confidence=1.0,
                markers=wrong_markers,
                evidence=f"Conflicting business-document marker(s): {', '.join(wrong_markers)}",
            )

        si_markers = [marker for marker in self.SI_MARKERS if marker in content]
        bl_markers = [
            match.group(0).upper()
            for pattern in self.BL_PATTERNS
            if (match := pattern.search(content))
        ]

        if si_markers and not bl_markers:
            return RoleValidationResult(
                document_type=DocumentType.SI,
                outcome=RoleValidationOutcome.VALID,
                confidence=1.0,
                markers=si_markers,
                evidence=f"Content declares SI role: {', '.join(si_markers)}",
            )
        if bl_markers and not si_markers:
            return RoleValidationResult(
                document_type=DocumentType.DRAFT_BL,
                outcome=RoleValidationOutcome.VALID,
                confidence=1.0,
                markers=bl_markers,
                evidence="Content declares draft Bill of Lading role",
            )

        return RoleValidationResult(
            document_type=DocumentType.UNKNOWN,
            outcome=RoleValidationOutcome.INCONCLUSIVE,
            confidence=0.0,
            markers=si_markers + bl_markers,
            evidence=(
                "Conflicting SI/BL content markers"
                if si_markers and bl_markers
                else "No sufficient content marker proves SI or draft BL role"
            ),
        )

    @staticmethod
    def _content(document: UnifiedDocument) -> str:
        table_text = "\n".join(
            " | ".join(str(cell) for cell in row)
            for table in document.tables
            for row in table.rows
        )
        return f"{document.raw_text}\n{table_text}"
