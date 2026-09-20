from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from backend.app.extraction.models import (
    CANONICAL_FIELDS,
    CanonicalField,
    ExtractedField,
)


class FieldComparisonStatus(str, Enum):
    """The only authoritative final outcomes for a field comparison."""

    MATCH = "MATCH"
    MISMATCH = "MISMATCH"
    UNRESOLVED = "UNRESOLVED"


class ComparisonLayer(str, Enum):
    PRECONDITION = "PRECONDITION"
    L0 = "L0"
    L1 = "L1"
    L2 = "L2"


class LayerDecision(str, Enum):
    EQUIVALENT = "EQUIVALENT"
    DIFFERENT = "DIFFERENT"
    NO_DECISION = "NO_DECISION"


@dataclass(frozen=True)
class LayerResolution:
    decision: LayerDecision
    si_value: Any
    bl_value: Any
    reason_code: str
    evidence: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.decision, LayerDecision):
            object.__setattr__(self, "decision", LayerDecision(self.decision))
        if not isinstance(self.reason_code, str) or not self.reason_code.strip():
            raise ValueError("reason_code must be a non-empty string")


@dataclass(frozen=True)
class SemanticResolution:
    equivalent: bool | None
    confidence: float
    reason: str

    def __post_init__(self) -> None:
        if self.equivalent is not None and not isinstance(self.equivalent, bool):
            raise TypeError("equivalent must be bool or None")
        if isinstance(self.confidence, bool) or not isinstance(self.confidence, (int, float)):
            raise TypeError("confidence must be numeric")
        confidence = float(self.confidence)
        if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be finite and between 0 and 1")
        object.__setattr__(self, "confidence", confidence)
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("reason must be a non-empty string")


@dataclass(frozen=True)
class FieldComparisonResult:
    canonical_field: CanonicalField
    si_field: ExtractedField
    bl_field: ExtractedField
    normalized_si: Any
    normalized_bl: Any
    layer: ComparisonLayer
    status: FieldComparisonStatus
    reason_code: str
    evidence: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.canonical_field, CanonicalField):
            object.__setattr__(self, "canonical_field", CanonicalField(self.canonical_field))
        if not isinstance(self.layer, ComparisonLayer):
            object.__setattr__(self, "layer", ComparisonLayer(self.layer))
        if not isinstance(self.status, FieldComparisonStatus):
            object.__setattr__(self, "status", FieldComparisonStatus(self.status))
        if self.si_field.canonical_field != self.canonical_field:
            raise ValueError("SI field does not match canonical field")
        if self.bl_field.canonical_field != self.canonical_field:
            raise ValueError("BL field does not match canonical field")
        if not isinstance(self.reason_code, str) or not self.reason_code.strip():
            raise ValueError("reason_code must be a non-empty string")


@dataclass(frozen=True)
class ComparisonBatchResult:
    fields: dict[CanonicalField, FieldComparisonResult]
    si_role: str = "SI"
    bl_role: str = "DRAFT_BL"

    def __post_init__(self) -> None:
        if self.si_role != "SI" or self.bl_role != "DRAFT_BL":
            raise ValueError("comparison direction must be SI reference to DRAFT_BL candidate")
        if set(self.fields) != set(CANONICAL_FIELDS):
            raise ValueError("comparison must contain exactly the seven canonical fields")
        for field_name, result in self.fields.items():
            if result.canonical_field != field_name:
                raise ValueError("comparison key and canonical field must agree")

    @property
    def mismatched_fields(self) -> tuple[CanonicalField, ...]:
        return tuple(
            name
            for name in CANONICAL_FIELDS
            if self.fields[name].status == FieldComparisonStatus.MISMATCH
        )

    @property
    def unresolved_fields(self) -> tuple[CanonicalField, ...]:
        return tuple(
            name
            for name in CANONICAL_FIELDS
            if self.fields[name].status == FieldComparisonStatus.UNRESOLVED
        )

    @property
    def mismatch_found(self) -> bool:
        return bool(self.mismatched_fields)

    @property
    def all_fields_definite(self) -> bool:
        return not self.unresolved_fields

    @property
    def comparison_state(self) -> str:
        return "COMPLETED" if self.all_fields_definite else "BLOCKED"

    @property
    def reason_code(self) -> str:
        return "COMPARISON_COMPLETE" if self.all_fields_definite else "COMPARISON_UNRESOLVED"

    @property
    def message(self) -> str:
        if not self.all_fields_definite:
            return "Comparison unresolved."
        if self.mismatch_found:
            return "Mismatch detected."
        return "No mismatch detected."
