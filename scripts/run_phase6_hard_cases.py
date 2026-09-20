"""Deterministic fixture-backed Phase-6 hard-case evaluation (no live provider)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.core.reliability import RetryPolicy
from backend.app.extraction.models import CanonicalField
from backend.app.resolution.models import (
    ExtractionResolutionRequest,
    ProviderResolution,
    SemanticResolutionRequest,
)
from backend.app.resolution.service import ResolutionExecutor


class FixtureProvider:
    def resolve(self, request):
        case = request.case_id
        if case == "accepted-port":
            return ProviderResolution(
                field=CanonicalField.PORT_OF_LOADING,
                value="Port Klang",
                normalized_value="PORT KLANG",
                confidence=0.97,
                evidence="Port of Loading: Port Klang",
                reasoning_code="LAYOUT_ASSOCIATION",
            )
        if case == "low-confidence":
            return ProviderResolution(
                field=CanonicalField.PORT_OF_DISCHARGE,
                value="Singapore",
                normalized_value="SINGAPORE",
                confidence=0.4,
                evidence="Port of Discharge: Singapore",
                reasoning_code="UNCERTAIN_LAYOUT",
            )
        if case == "semantic-party":
            return ProviderResolution(
                field=CanonicalField.SHIPPER,
                equivalent=True,
                confidence=0.96,
                evidence="ABC LOGISTICS SDN BHD | ABC LOGISTICS",
                reasoning_code="LEGAL_SUFFIX_EQUIVALENCE",
            )
        if case == "unsafe-unit":
            return ProviderResolution(
                field=CanonicalField.GROSS_WEIGHT_KG,
                value="10,000 LB",
                normalized_value=10000,
                confidence=0.99,
                evidence="Gross Weight: 10,000 LB",
                reasoning_code="QUANTITY_PARSE",
            )
        raise AssertionError(f"unexpected fixture case: {case}")


def extraction(case_id, field, evidence):
    return ExtractionResolutionRequest(
        case_id=case_id,
        field=field,
        document_role="SI",
        document_id=f"doc:{case_id}",
        content_identity=f"fixture:{case_id}",
        evidence=evidence,
        deterministic_candidates=(),
        escalation_reason="UNRESOLVED_EXTRACTION",
    )


def main() -> None:
    executor = ResolutionExecutor(
        provider=FixtureProvider(),
        enabled=True,
        confidence_threshold=0.9,
        timeout_seconds=0.2,
        retry_policy=RetryPolicy(max_attempts=2, backoff_seconds=0),
        max_calls_per_case=2,
        max_concurrent_calls=2,
        provider_name="deterministic-fixture",
        model_name="phase6-fixture-v1",
        resolver_version="phase6-resolver-v1",
        prompt_schema_version="phase6-schema-v1",
    )
    decisions = [
        executor.resolve_extraction(extraction(
            "accepted-port", CanonicalField.PORT_OF_LOADING, "Port of Loading: Port Klang"
        )),
        executor.resolve_extraction(extraction(
            "low-confidence", CanonicalField.PORT_OF_DISCHARGE, "Port of Discharge: Singapore"
        )),
        executor.resolve_extraction(extraction(
            "missing-source", CanonicalField.CONSIGNEE, ""
        )),
        executor.resolve_semantic(SemanticResolutionRequest(
            case_id="semantic-party",
            field=CanonicalField.SHIPPER,
            si_value="ABC LOGISTICS SDN BHD",
            bl_value="ABC LOGISTICS",
            si_evidence="Shipper: ABC LOGISTICS SDN BHD",
            bl_evidence="Shipper: ABC LOGISTICS",
            source_identity="fixture:semantic-party",
            escalation_reason="SEMANTIC_NORMALIZATION_REQUIRED",
        )),
        executor.resolve_extraction(extraction(
            "unsafe-unit", CanonicalField.GROSS_WEIGHT_KG, "Gross Weight: 10,000 LB"
        )),
    ]
    cached = executor.resolve_extraction(extraction(
        "accepted-port", CanonicalField.PORT_OF_LOADING, "Port of Loading: Port Klang"
    ))
    metrics = executor.metrics.snapshot()
    output = {
        "mode": "fixture-backed; no live provider",
        "hard_cases_attempted": len(decisions),
        "accepted": sum(decision.accepted for decision in decisions),
        "rejected_or_unresolved": sum(not decision.accepted for decision in decisions),
        "remaining_unresolved": sum(not decision.accepted for decision in decisions),
        "validation_reasons": [decision.validation_reason for decision in decisions],
        "repeat_cache_hit": cached.cache_hit,
        **metrics,
    }
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
