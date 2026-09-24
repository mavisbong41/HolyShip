from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from backend.app.extraction.models import CanonicalField


@dataclass(frozen=True)
class ExtractionResolutionRequest:
    case_id: str
    field: CanonicalField
    document_role: str
    document_id: str
    content_identity: str
    evidence: str
    deterministic_candidates: tuple[Any, ...]
    escalation_reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.field, CanonicalField):
            object.__setattr__(self, "field", CanonicalField(self.field))


@dataclass(frozen=True)
class SemanticResolutionRequest:
    case_id: str
    field: CanonicalField
    si_value: Any
    bl_value: Any
    si_evidence: str
    bl_evidence: str
    source_identity: str
    escalation_reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.field, CanonicalField):
            object.__setattr__(self, "field", CanonicalField(self.field))


@dataclass(frozen=True)
class ProviderResolution:
    field: CanonicalField
    confidence: float
    evidence: str
    reasoning_code: str
    value: Any = None
    normalized_value: Any = None
    equivalent: bool | None = None
    audit_metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.field, CanonicalField):
            object.__setattr__(self, "field", CanonicalField(self.field))
        if isinstance(self.confidence, bool) or not isinstance(self.confidence, (int, float)):
            raise TypeError("confidence must be numeric")
        confidence = float(self.confidence)
        if not math.isfinite(confidence) or not 0 <= confidence <= 1:
            raise ValueError("confidence must be finite and between zero and one")
        object.__setattr__(self, "confidence", confidence)
        if self.equivalent is not None and not isinstance(self.equivalent, bool):
            raise TypeError("equivalent must be bool or None")
        if not isinstance(self.evidence, str):
            raise TypeError("evidence must be a string")
        if not isinstance(self.reasoning_code, str) or not self.reasoning_code.strip():
            raise ValueError("reasoning_code must be non-empty")


@dataclass(frozen=True)
class ResolutionDecision:
    accepted: bool
    validation_reason: str
    field: CanonicalField
    confidence: float = 0.0
    value: Any = None
    normalized_value: Any = None
    equivalent: bool | None = None
    evidence: dict[str, Any] = field(default_factory=dict)
    cache_hit: bool = False
    provider_calls: int = 0
    request_hash: str = ""


@dataclass
class ResolutionMetrics:
    escalated_cases: set[str] = field(default_factory=set)
    provider_calls: int = 0
    accepted: int = 0
    rejected: int = 0
    cache_hits: int = 0
    provider_failures: int = 0
    malformed_responses: int = 0

    def snapshot(self) -> dict[str, int | float]:
        case_count = len(self.escalated_cases)
        return {
            "escalated_cases": case_count,
            "provider_calls": self.provider_calls,
            "accepted": self.accepted,
            "rejected": self.rejected,
            "cache_hits": self.cache_hits,
            "provider_failures": self.provider_failures,
            "malformed_responses": self.malformed_responses,
            "average_calls_per_escalated_case": (
                self.provider_calls / case_count if case_count else 0.0
            ),
        }
