from __future__ import annotations

from typing import Any, Protocol

from backend.app.core.reliability import run_with_timeout
from backend.app.comparison.l1 import FieldSpecificL1Comparator
from backend.app.comparison.models import (
    ComparisonBatchResult,
    ComparisonLayer,
    FieldComparisonResult,
    FieldComparisonStatus,
    LayerDecision,
    LayerResolution,
    SemanticResolution,
)
from backend.app.comparison.normalization import l0_normalize
from backend.app.extraction.models import (
    CANONICAL_FIELDS,
    CanonicalField,
    DocumentExtractionResult,
    ExtractedField,
    FieldStatus,
)


COMPARISON_VERSION = "phase4-deterministic-v1"


class L1Comparator(Protocol):
    def compare(
        self,
        field_name: CanonicalField,
        si_value: Any,
        bl_value: Any,
    ) -> LayerResolution: ...


class SemanticResolver(Protocol):
    def resolve(
        self,
        field_name: CanonicalField,
        si_value: Any,
        bl_value: Any,
    ) -> SemanticResolution: ...


class DefaultL1Comparator:
    """P4A boundary: field-specific L1 behavior belongs to P4B."""

    def compare(
        self,
        field_name: CanonicalField,
        si_value: Any,
        bl_value: Any,
    ) -> LayerResolution:
        return LayerResolution(
            decision=LayerDecision.NO_DECISION,
            si_value=si_value,
            bl_value=bl_value,
            reason_code="L1_NOT_IMPLEMENTED_P4A",
        )


class DefaultSemanticResolver:
    """Safe L2 default that performs no provider calls and makes no claim."""

    provider_calls = 0

    def resolve(
        self,
        field_name: CanonicalField,
        si_value: Any,
        bl_value: Any,
    ) -> SemanticResolution:
        return SemanticResolution(
            equivalent=None,
            confidence=0.0,
            reason="SEMANTIC_RESOLUTION_NOT_CONFIGURED",
        )


class ComparisonService:
    def __init__(
        self,
        *,
        l1: L1Comparator | None = None,
        l2: SemanticResolver | None = None,
        semantic_timeout_seconds: float | None = None,
    ) -> None:
        self.l1 = l1 if l1 is not None else FieldSpecificL1Comparator()
        self.l2 = l2 if l2 is not None else DefaultSemanticResolver()
        if semantic_timeout_seconds is not None and semantic_timeout_seconds <= 0:
            raise ValueError("semantic_timeout_seconds must be positive")
        self.semantic_timeout_seconds = semantic_timeout_seconds

    def compare(
        self,
        si: DocumentExtractionResult,
        draft_bl: DocumentExtractionResult,
    ) -> ComparisonBatchResult:
        if si.document_role != "SI":
            raise ValueError("SI extraction must be the comparison reference")
        if draft_bl.document_role != "DRAFT_BL":
            raise ValueError("DRAFT_BL extraction must be the comparison candidate")

        fields = {
            field_name: self.compare_field(
                field_name,
                si.fields[field_name],
                draft_bl.fields[field_name],
            )
            for field_name in CANONICAL_FIELDS
        }
        return ComparisonBatchResult(fields=fields)

    def compare_field(
        self,
        field_name: CanonicalField,
        si_field: ExtractedField,
        bl_field: ExtractedField,
    ) -> FieldComparisonResult:
        if not isinstance(field_name, CanonicalField):
            field_name = CanonicalField(field_name)
        if si_field.canonical_field != field_name or bl_field.canonical_field != field_name:
            raise ValueError("comparison inputs must match the requested canonical field")

        normalized_si = l0_normalize(si_field.canonical_value)
        normalized_bl = l0_normalize(bl_field.canonical_value)
        if not self._is_comparable(si_field, normalized_si) or not self._is_comparable(
            bl_field,
            normalized_bl,
        ):
            return self._result(
                field_name,
                si_field,
                bl_field,
                normalized_si,
                normalized_bl,
                ComparisonLayer.PRECONDITION,
                FieldComparisonStatus.UNRESOLVED,
                "EXTRACTION_VALUE_NOT_COMPARABLE",
                {
                    "si_extraction_status": si_field.status.value,
                    "bl_extraction_status": bl_field.status.value,
                },
            )

        if normalized_si == normalized_bl:
            return self._result(
                field_name,
                si_field,
                bl_field,
                normalized_si,
                normalized_bl,
                ComparisonLayer.L0,
                FieldComparisonStatus.MATCH,
                "L0_VALUES_EQUAL",
            )

        l1_result = self.l1.compare(field_name, normalized_si, normalized_bl)
        if l1_result.decision != LayerDecision.NO_DECISION:
            return self._result(
                field_name,
                si_field,
                bl_field,
                l1_result.si_value,
                l1_result.bl_value,
                ComparisonLayer.L1,
                self._status_for_decision(l1_result.decision),
                l1_result.reason_code,
                l1_result.evidence,
            )

        if l1_result.si_value == l1_result.bl_value:
            return self._result(
                field_name,
                si_field,
                bl_field,
                l1_result.si_value,
                l1_result.bl_value,
                ComparisonLayer.L1,
                FieldComparisonStatus.MATCH,
                "L1_VALUES_EQUAL",
                l1_result.evidence,
            )

        l2_result = self._resolve_semantically(
            field_name,
            l1_result.si_value,
            l1_result.bl_value,
        )
        if l2_result.equivalent is True:
            status = FieldComparisonStatus.MATCH
        elif l2_result.equivalent is False:
            status = FieldComparisonStatus.MISMATCH
        else:
            status = FieldComparisonStatus.UNRESOLVED
        return self._result(
            field_name,
            si_field,
            bl_field,
            l1_result.si_value,
            l1_result.bl_value,
            ComparisonLayer.L2,
            status,
            l2_result.reason,
            {"confidence": l2_result.confidence},
        )


    def _resolve_semantically(
        self,
        field_name: CanonicalField,
        si_value: Any,
        bl_value: Any,
    ) -> SemanticResolution:
        def resolve() -> SemanticResolution:
            return self.l2.resolve(field_name, si_value, bl_value)

        try:
            result = (
                run_with_timeout(resolve, timeout_seconds=self.semantic_timeout_seconds)
                if self.semantic_timeout_seconds is not None
                and not isinstance(self.l2, DefaultSemanticResolver)
                else resolve()
            )
        except TimeoutError:
            return SemanticResolution(
                equivalent=None,
                confidence=0.0,
                reason="SEMANTIC_RESOLUTION_TIMEOUT",
            )
        except Exception:
            return SemanticResolution(
                equivalent=None,
                confidence=0.0,
                reason="SEMANTIC_RESOLUTION_FAILED",
            )

        if not isinstance(result, SemanticResolution):
            return SemanticResolution(
                equivalent=None,
                confidence=0.0,
                reason="SEMANTIC_RESOLUTION_INVALID",
            )
        return result

    @staticmethod
    def _is_comparable(field: ExtractedField, normalized_value: Any) -> bool:
        if field.status != FieldStatus.RESOLVED or field.canonical_value is None:
            return False
        return not isinstance(normalized_value, str) or bool(normalized_value)

    @staticmethod
    def _status_for_decision(decision: LayerDecision) -> FieldComparisonStatus:
        if decision == LayerDecision.EQUIVALENT:
            return FieldComparisonStatus.MATCH
        if decision == LayerDecision.DIFFERENT:
            return FieldComparisonStatus.MISMATCH
        raise ValueError("NO_DECISION cannot be converted into a final status")

    @staticmethod
    def _result(
        field_name: CanonicalField,
        si_field: ExtractedField,
        bl_field: ExtractedField,
        normalized_si: Any,
        normalized_bl: Any,
        layer: ComparisonLayer,
        status: FieldComparisonStatus,
        reason_code: str,
        evidence: dict[str, Any] | None = None,
    ) -> FieldComparisonResult:
        return FieldComparisonResult(
            canonical_field=field_name,
            si_field=si_field,
            bl_field=bl_field,
            normalized_si=normalized_si,
            normalized_bl=normalized_bl,
            layer=layer,
            status=status,
            reason_code=reason_code,
            evidence=dict(evidence or {}),
        )
