from __future__ import annotations

from dataclasses import replace
from typing import Any

from backend.app.comparison.models import SemanticResolution
from backend.app.extraction.models import (
    CANONICAL_FIELDS,
    CanonicalField,
    DocumentExtractionResult,
    ExtractedField,
    FieldStatus,
    MappingMethod,
)
from backend.app.resolution.models import (
    ExtractionResolutionRequest,
    SemanticResolutionRequest,
)
from backend.app.resolution.service import ResolutionExecutor


def apply_extraction_overlays(
    extraction: DocumentExtractionResult,
    *,
    executor: ResolutionExecutor,
    case_id: str,
    document_id: str,
    content_identity: str,
) -> DocumentExtractionResult:
    """Return comparison-only overlays; never mutate persisted Phase-3 rows."""

    fields = dict(extraction.fields)
    pending: list[tuple[CanonicalField, ExtractedField, ExtractionResolutionRequest]] = []
    for field_name in CANONICAL_FIELDS:
        source = fields[field_name]
        if source.status not in {FieldStatus.UNRESOLVED, FieldStatus.AMBIGUOUS}:
            continue
        evidence = _field_evidence(source)
        candidates = tuple(source.evidence.get("candidates") or ())
        pending.append((
            field_name,
            source,
            ExtractionResolutionRequest(
                case_id=case_id,
                field=field_name,
                document_role=extraction.document_role,
                document_id=document_id,
                content_identity=content_identity,
                evidence=evidence,
                deterministic_candidates=candidates,
                escalation_reason=(
                    "AMBIGUOUS_FIELD_CANDIDATES"
                    if source.status == FieldStatus.AMBIGUOUS
                    else "UNRESOLVED_EXTRACTION"
                ),
            ),
        ))
    decisions = executor.resolve_extraction_batch(tuple(item[2] for item in pending))
    for (field_name, source, _request), decision in zip(pending, decisions, strict=True):
        audit = {
            "accepted": decision.accepted,
            "validation_reason": decision.validation_reason,
            "confidence": decision.confidence,
            "proposed_value": decision.value,
            "accepted_canonical_value": decision.normalized_value if decision.accepted else None,
            "request_hash": decision.request_hash,
            "cache_hit": decision.cache_hit,
            **decision.evidence,
        }
        if decision.accepted:
            fields[field_name] = replace(
                source,
                canonical_value=decision.normalized_value,
                status=FieldStatus.RESOLVED,
                confidence=decision.confidence,
                mapping_method=MappingMethod.LLM_RESOLVED,
                evidence={**source.evidence, "ai_resolution": audit},
            )
        else:
            fields[field_name] = replace(
                source,
                evidence={**source.evidence, "ai_resolution": audit},
            )
    return DocumentExtractionResult(
        document_role=extraction.document_role,
        fields=fields,
        extractor_version=extraction.extractor_version,
    )


class HardCaseSemanticResolver:
    def __init__(
        self,
        executor: ResolutionExecutor,
        *,
        case_id: str,
        source_identity: str,
        si_fields: dict[CanonicalField, ExtractedField],
        bl_fields: dict[CanonicalField, ExtractedField],
    ) -> None:
        self.executor = executor
        self.case_id = case_id
        self.source_identity = source_identity
        self.si_fields = si_fields
        self.bl_fields = bl_fields

    def resolve(self, field_name: CanonicalField, si_value: Any, bl_value: Any) -> SemanticResolution:
        decision = self.executor.resolve_semantic(
            SemanticResolutionRequest(
                case_id=self.case_id,
                field=field_name,
                si_value=si_value,
                bl_value=bl_value,
                si_evidence=_field_evidence(self.si_fields[field_name]),
                bl_evidence=_field_evidence(self.bl_fields[field_name]),
                source_identity=self.source_identity,
                escalation_reason="SEMANTIC_NORMALIZATION_REQUIRED",
            )
        )
        return SemanticResolution(
            equivalent=decision.equivalent if decision.accepted else None,
            confidence=decision.confidence,
            reason=(
                f"AI_{decision.evidence.get('reasoning_code', 'RESOLVED')}"
                if decision.accepted
                else decision.validation_reason
            ),
        )


def _field_evidence(field: ExtractedField) -> str:
    location = field.source_location
    parts = [
        location.text_span,
        location.label_cell,
        location.value_cell,
        None if field.raw_value is None else str(field.raw_value),
    ]
    return "\n".join(part.strip() for part in parts if isinstance(part, str) and part.strip())
