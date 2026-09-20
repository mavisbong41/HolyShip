from __future__ import annotations

import copy

import pytest

from backend.app.comparison.models import (
    ComparisonLayer,
    FieldComparisonStatus,
    SemanticResolution,
)
from backend.app.comparison.service import ComparisonService
from backend.app.extraction.models import (
    CanonicalField,
    ExtractedField,
    FieldStatus,
    MappingMethod,
    SourceLocation,
)


def _field(
    name: CanonicalField,
    canonical_value,
    *,
    raw_value=...,
    status: FieldStatus = FieldStatus.RESOLVED,
    evidence: dict | None = None,
) -> ExtractedField:
    raw = canonical_value if raw_value is ... else raw_value
    if status == FieldStatus.MISSING:
        raw = None
        canonical_value = None
        raw_label = None
        method = None
    else:
        raw_label = name.value.upper()
        method = MappingMethod.EXACT_LABEL
    return ExtractedField(
        canonical_field=name,
        raw_label=raw_label,
        raw_value=raw,
        canonical_value=canonical_value,
        status=status,
        confidence=1.0 if status == FieldStatus.RESOLVED else 0.0,
        mapping_method=method,
        source_location=SourceLocation(source_type="synthetic"),
        evidence=evidence or {},
    )


@pytest.mark.req("MAP-07")
@pytest.mark.req("CMP-05")
def test_container_count_uses_canonical_count_and_preserves_auxiliary_type():
    name = CanonicalField.CONTAINER_COUNT
    si = _field(name, 6, raw_value="6 x 40'HC", evidence={"container_type": "40'HC"})
    bl = _field(name, 6, raw_value="6 x 40'GP", evidence={"container_type": "40'GP"})
    before = (copy.deepcopy(si), copy.deepcopy(bl))

    canonical_match = ComparisonService().compare_field(name, si, bl)
    text_match = ComparisonService().compare_field(
        name,
        _field(name, "6 x 40'HC"),
        _field(name, "6 x 40'GP"),
    )
    mismatch = ComparisonService().compare_field(
        name,
        _field(name, "6 x 40'HC"),
        _field(name, "5 x 40'HC"),
    )
    malformed = ComparisonService().compare_field(
        name,
        _field(name, None, raw_value="six containers", status=FieldStatus.UNRESOLVED),
        _field(name, 6),
    )

    assert canonical_match.status == FieldComparisonStatus.MATCH
    assert canonical_match.layer == ComparisonLayer.L0
    assert text_match.status == FieldComparisonStatus.MATCH
    assert (text_match.normalized_si, text_match.normalized_bl) == (6, 6)
    assert mismatch.status == FieldComparisonStatus.MISMATCH
    assert malformed.status == FieldComparisonStatus.UNRESOLVED
    assert (si, bl) == before
    assert si.evidence["container_type"] == "40'HC"
    assert bl.evidence["container_type"] == "40'GP"


@pytest.mark.req("CMP-05")
def test_gross_weight_uses_numeric_kg_without_net_weight_substitution():
    from backend.app.documents.models import DocumentType, UnifiedDocument
    from backend.app.extraction.extractor import DeterministicDocumentExtractor

    name = CanonicalField.GROSS_WEIGHT_KG
    service = ComparisonService()

    formatted = service.compare_field(
        name,
        _field(name, "22,000 KG"),
        _field(name, "22000 kg"),
    )
    native_numeric = service.compare_field(
        name,
        _field(name, 22000, raw_value=22000),
        _field(name, "22,000 KG"),
    )
    mismatch = service.compare_field(name, _field(name, 22000), _field(name, 23000))
    net_document = UnifiedDocument(
        raw_text="NET WEIGHT: 18000 KG",
        document_type=DocumentType.SI,
    )
    net_field = DeterministicDocumentExtractor().extract(net_document).fields[name]
    net_only = service.compare_field(
        name,
        net_field,
        _field(name, 22000),
    )

    assert formatted.status == FieldComparisonStatus.MATCH
    assert native_numeric.status == FieldComparisonStatus.MATCH
    assert (native_numeric.normalized_si, native_numeric.normalized_bl) == (22000, 22000)
    assert mismatch.status == FieldComparisonStatus.MISMATCH
    assert net_field.status == FieldStatus.MISSING
    assert net_field.raw_value is None
    assert net_only.status == FieldComparisonStatus.UNRESOLVED


@pytest.mark.req("CMP-05")
@pytest.mark.req("CMP-06")
def test_entity_normalization_is_narrow_and_preserves_meaningful_words():
    name = CanonicalField.SHIPPER
    service = ComparisonService()

    l0_match = service.compare_field(
        name,
        _field(name, "  ABC   TRADING SDN BHD "),
        _field(name, "abc trading sdn bhd"),
    )
    punctuation_match = service.compare_field(
        name,
        _field(name, "ABC Trading Sdn. Bhd."),
        _field(name, "ABC Trading Sdn Bhd"),
    )
    meaningful_change = service.compare_field(
        name,
        _field(name, "ABC Trading Sdn Bhd"),
        _field(name, "ABC Logistics Sdn Bhd"),
    )
    geographic_change = service.compare_field(
        name,
        _field(name, "ABC Trading Malaysia Sdn Bhd"),
        _field(name, "ABC Trading Singapore Sdn Bhd"),
    )

    assert l0_match.status == FieldComparisonStatus.MATCH
    assert punctuation_match.status == FieldComparisonStatus.MATCH
    assert punctuation_match.layer == ComparisonLayer.L1
    assert meaningful_change.status == FieldComparisonStatus.UNRESOLVED
    assert geographic_change.status == FieldComparisonStatus.UNRESOLVED
    assert "logistics" in meaningful_change.normalized_bl
    assert "singapore" in geographic_change.normalized_bl


@pytest.mark.req("CMP-05")
@pytest.mark.req("CMP-07")
def test_ports_use_only_approved_aliases_without_fuzzy_matching():
    name = CanonicalField.PORT_OF_LOADING
    service = ComparisonService()

    approved_alias = service.compare_field(
        name,
        _field(name, "Port Klang"),
        _field(name, "MYPKG"),
    )
    l0_match = service.compare_field(
        name,
        _field(name, "  PORT   KLANG "),
        _field(name, "port klang"),
    )
    unapproved_similar = service.compare_field(
        name,
        _field(name, "Port Klang"),
        _field(name, "Port Klan"),
    )
    different_ports = service.compare_field(
        name,
        _field(name, "Port Klang"),
        _field(name, "Singapore"),
    )

    assert approved_alias.status == FieldComparisonStatus.MATCH
    assert approved_alias.layer == ComparisonLayer.L1
    assert l0_match.status == FieldComparisonStatus.MATCH
    assert l0_match.layer == ComparisonLayer.L0
    assert unapproved_similar.status == FieldComparisonStatus.UNRESOLVED
    assert different_ports.status == FieldComparisonStatus.MISMATCH


class _CountingL1:
    def __init__(self, delegate):
        self.delegate = delegate
        self.calls = 0

    def compare(self, field_name, si_value, bl_value):
        self.calls += 1
        return self.delegate.compare(field_name, si_value, bl_value)


class _CountingL2:
    def __init__(self):
        self.calls = 0

    def resolve(self, field_name, si_value, bl_value):
        self.calls += 1
        return SemanticResolution(None, 0.0, "TEST_NO_SEMANTIC_DECISION")


def test_real_l1_preserves_l0_l1_l2_short_circuit_order():
    from backend.app.comparison.l1 import FieldSpecificL1Comparator

    name = CanonicalField.SHIPPER

    l1 = _CountingL1(FieldSpecificL1Comparator())
    l2 = _CountingL2()
    l0_result = ComparisonService(l1=l1, l2=l2).compare_field(
        name,
        _field(name, "ABC Trading"),
        _field(name, " abc trading "),
    )
    assert l0_result.layer == ComparisonLayer.L0
    assert (l1.calls, l2.calls) == (0, 0)

    l1 = _CountingL1(FieldSpecificL1Comparator())
    l2 = _CountingL2()
    l1_result = ComparisonService(l1=l1, l2=l2).compare_field(
        name,
        _field(name, "ABC Trading Sdn. Bhd."),
        _field(name, "ABC Trading Sdn Bhd"),
    )
    assert l1_result.layer == ComparisonLayer.L1
    assert (l1.calls, l2.calls) == (1, 0)

    l1 = _CountingL1(FieldSpecificL1Comparator())
    l2 = _CountingL2()
    l2_result = ComparisonService(l1=l1, l2=l2).compare_field(
        name,
        _field(name, "ABC International"),
        _field(name, "ABC Intl"),
    )
    assert l2_result.layer == ComparisonLayer.L2
    assert l2_result.status == FieldComparisonStatus.UNRESOLVED
    assert (l1.calls, l2.calls) == (1, 1)
