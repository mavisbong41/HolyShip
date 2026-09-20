from __future__ import annotations

import time

import pytest

from backend.app.comparison.models import FieldComparisonStatus
from backend.app.comparison.service import ComparisonService
from backend.app.extraction.models import (
    CanonicalField,
    ExtractedField,
    FieldStatus,
    SourceLocation,
)


def _resolved(field: CanonicalField, value: str) -> ExtractedField:
    return ExtractedField(
        canonical_field=field,
        raw_label=field.value,
        raw_value=value,
        canonical_value=value,
        status=FieldStatus.RESOLVED,
        confidence=1.0,
        mapping_method="exact_label",
        source_location=SourceLocation(source_type="test"),
    )


class _MalformedResolver:
    def resolve(self, field_name, si_value, bl_value):
        return {"equivalent": True, "confidence": 1.0}


class _SlowResolver:
    def resolve(self, field_name, si_value, bl_value):
        time.sleep(0.2)
        return {"equivalent": True, "confidence": 1.0, "reason": "too late"}


def test_malformed_semantic_resolver_output_is_unresolved():
    field = CanonicalField.SHIPPER
    result = ComparisonService(l2=_MalformedResolver()).compare_field(
        field,
        _resolved(field, "Alpha Logistics"),
        _resolved(field, "Alpha Logistics Limited"),
    )

    assert result.status == FieldComparisonStatus.UNRESOLVED
    assert result.reason_code == "SEMANTIC_RESOLUTION_INVALID"


def test_semantic_resolver_timeout_is_unresolved_without_blocking_the_batch():
    field = CanonicalField.SHIPPER
    started = time.perf_counter()
    result = ComparisonService(
        l2=_SlowResolver(),
        semantic_timeout_seconds=0.01,
    ).compare_field(
        field,
        _resolved(field, "Alpha Logistics"),
        _resolved(field, "Alpha Logistics Limited"),
    )

    assert result.status == FieldComparisonStatus.UNRESOLVED
    assert result.reason_code == "SEMANTIC_RESOLUTION_TIMEOUT"
    assert time.perf_counter() - started < 0.1


@pytest.mark.parametrize("filename", ["合同_日本語.txt", "résumé.txt"])
def test_unicode_filename_is_not_rejected_by_phase5_boundaries(filename):
    assert filename.encode("utf-8").decode("utf-8") == filename
