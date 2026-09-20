from __future__ import annotations

import copy

import pytest

from backend.app.comparison.models import (
    ComparisonLayer,
    FieldComparisonStatus,
    LayerDecision,
    LayerResolution,
    SemanticResolution,
)
from backend.app.comparison.normalization import l0_normalize
from backend.app.comparison.service import (
    ComparisonService,
    DefaultL1Comparator,
    DefaultSemanticResolver,
)
from backend.app.extraction.models import (
    CANONICAL_FIELDS,
    CanonicalField,
    DocumentExtractionResult,
    ExtractedField,
    FieldStatus,
    MappingMethod,
    SourceLocation,
)


BASE_VALUES = {
    CanonicalField.SHIPPER: "Alpha Trading Sdn Bhd",
    CanonicalField.CONSIGNEE: "Beta Imports Ltd",
    CanonicalField.NOTIFY_PARTY: "Gamma Notify Co",
    CanonicalField.PORT_OF_LOADING: "Port Klang",
    CanonicalField.PORT_OF_DISCHARGE: "Singapore",
    CanonicalField.CONTAINER_COUNT: 6,
    CanonicalField.GROSS_WEIGHT_KG: 22000,
}


def _field(
    name: CanonicalField,
    value=...,
    *,
    status: FieldStatus = FieldStatus.RESOLVED,
    raw_value=...,
) -> ExtractedField:
    canonical = BASE_VALUES[name] if value is ... else value
    raw = canonical if raw_value is ... else raw_value
    if status == FieldStatus.MISSING:
        canonical = raw = None
        raw_label = None
        mapping_method = None
    else:
        raw_label = name.value.upper()
        mapping_method = MappingMethod.EXACT_LABEL
    return ExtractedField(
        canonical_field=name,
        raw_label=raw_label,
        raw_value=raw,
        canonical_value=canonical,
        status=status,
        confidence=1.0 if status == FieldStatus.RESOLVED else 0.0,
        mapping_method=mapping_method,
        source_location=SourceLocation(
            source_type="text",
            page_number=1,
            line_number=1,
            text_span=None if raw is None else f"{raw_label}: {raw}",
        ),
        evidence={"fixture": "phase4-core"},
    )


def _extraction(
    role: str,
    *,
    overrides: dict[CanonicalField, ExtractedField] | None = None,
) -> DocumentExtractionResult:
    replacements = overrides or {}
    return DocumentExtractionResult(
        document_role=role,
        fields={name: replacements.get(name, _field(name)) for name in CANONICAL_FIELDS},
        extractor_version="phase3-deterministic-v1",
    )


class SpyL1:
    def __init__(self, decision: LayerDecision):
        self.decision = decision
        self.calls = 0

    def compare(self, field_name, si_value, bl_value):
        self.calls += 1
        return LayerResolution(
            decision=self.decision,
            si_value=si_value,
            bl_value=bl_value,
            reason_code=f"TEST_L1_{self.decision.value}",
        )


class SpyL2:
    def __init__(self, equivalent: bool | None):
        self.equivalent = equivalent
        self.calls = 0

    def resolve(self, field_name, si_value, bl_value):
        self.calls += 1
        return SemanticResolution(
            equivalent=self.equivalent,
            confidence=0.0 if self.equivalent is None else 1.0,
            reason="test semantic decision",
        )


@pytest.mark.req("CMP-01")
def test_comparison_produces_exactly_seven_fields_with_si_as_reference():
    si_shipper = _field(CanonicalField.SHIPPER, "SI Reference Company")
    bl_shipper = _field(CanonicalField.SHIPPER, "BL Candidate Company")
    si = _extraction("SI", overrides={CanonicalField.SHIPPER: si_shipper})
    bl = _extraction("DRAFT_BL", overrides={CanonicalField.SHIPPER: bl_shipper})

    result = ComparisonService().compare(si, bl)

    assert tuple(result.fields) == CANONICAL_FIELDS
    assert len(result.fields) == 7
    shipper = result.fields[CanonicalField.SHIPPER]
    assert shipper.si_field is si_shipper
    assert shipper.bl_field is bl_shipper
    assert shipper.si_field.canonical_value == "SI Reference Company"
    assert shipper.bl_field.canonical_value == "BL Candidate Company"
    with pytest.raises(ValueError, match="SI extraction"):
        ComparisonService().compare(bl, si)


@pytest.mark.req("CMP-02")
def test_field_outcomes_cover_match_definite_mismatch_and_missing_uncertainty():
    service = ComparisonService()
    name = CanonicalField.SHIPPER

    matched = service.compare_field(name, _field(name, "Alpha"), _field(name, " alpha "))
    assert matched.status == FieldComparisonStatus.MATCH

    mismatch = ComparisonService(l1=SpyL1(LayerDecision.DIFFERENT)).compare_field(
        name,
        _field(name, "Alpha"),
        _field(name, "Beta"),
    )
    assert mismatch.status == FieldComparisonStatus.MISMATCH

    missing = _field(name, status=FieldStatus.MISSING)
    present = _field(name, "Alpha")
    assert service.compare_field(name, missing, present).status == FieldComparisonStatus.UNRESOLVED
    assert service.compare_field(name, present, missing).status == FieldComparisonStatus.UNRESOLVED
    assert service.compare_field(name, missing, missing).status == FieldComparisonStatus.UNRESOLVED


@pytest.mark.req("CMP-02")
@pytest.mark.parametrize("status", [FieldStatus.AMBIGUOUS, FieldStatus.UNRESOLVED])
def test_invalid_extraction_status_on_either_side_is_unresolved(status):
    name = CanonicalField.CONSIGNEE
    invalid = _field(name, None, status=status, raw_value="uncertain source value")
    valid = _field(name, "Beta Imports")
    service = ComparisonService()

    assert service.compare_field(name, invalid, valid).status == FieldComparisonStatus.UNRESOLVED
    assert service.compare_field(name, valid, invalid).status == FieldComparisonStatus.UNRESOLVED


@pytest.mark.req("CMP-04")
def test_l0_normalizes_only_safe_unicode_case_whitespace_and_line_break_artifacts():
    assert l0_normalize("ABC TRADING SDN BHD") == l0_normalize(
        "  abc   trading\nSDN BHD  "
    )
    assert l0_normalize("Cafe\u0301 Trading") == l0_normalize("Caf\u00e9 Trading")
    assert l0_normalize("ＡＢＣ Trading") == l0_normalize("ABC Trading")
    assert l0_normalize("ABC Trading Sdn Bhd") != l0_normalize(
        "ABC Logistics Sdn Bhd"
    )
    assert l0_normalize("ABC Trading Sdn. Bhd.") != l0_normalize(
        "ABC Trading Sdn Bhd"
    )


@pytest.mark.req("CMP-03")
@pytest.mark.req("CMP-13")
def test_layered_dispatch_short_circuits_only_after_a_decision():
    name = CanonicalField.SHIPPER

    l1 = SpyL1(LayerDecision.NO_DECISION)
    l2 = SpyL2(None)
    l0_match = ComparisonService(l1=l1, l2=l2).compare_field(
        name,
        _field(name, "ABC Trading"),
        _field(name, "  abc   trading "),
    )
    assert l0_match.status == FieldComparisonStatus.MATCH
    assert l0_match.layer == ComparisonLayer.L0
    assert (l1.calls, l2.calls) == (0, 0)

    l1 = SpyL1(LayerDecision.EQUIVALENT)
    l2 = SpyL2(None)
    l1_match = ComparisonService(l1=l1, l2=l2).compare_field(
        name,
        _field(name, "ABC Trading Sdn. Bhd."),
        _field(name, "ABC Trading Sdn Bhd"),
    )
    assert l1_match.status == FieldComparisonStatus.MATCH
    assert l1_match.layer == ComparisonLayer.L1
    assert (l1.calls, l2.calls) == (1, 0)

    l1 = SpyL1(LayerDecision.NO_DECISION)
    l2 = SpyL2(None)
    unresolved = ComparisonService(l1=l1, l2=l2).compare_field(
        name,
        _field(name, "ABC Trading Sdn. Bhd."),
        _field(name, "ABC Trading Sdn Bhd"),
    )
    assert unresolved.status == FieldComparisonStatus.UNRESOLVED
    assert unresolved.layer == ComparisonLayer.L2
    assert (l1.calls, l2.calls) == (1, 1)


@pytest.mark.req("CMP-08")
def test_semantic_resolution_contract_and_default_are_structured_and_uncertain():
    default = DefaultSemanticResolver()
    result = default.resolve(CanonicalField.SHIPPER, "Alpha", "Beta")

    assert result == SemanticResolution(
        equivalent=None,
        confidence=0.0,
        reason="SEMANTIC_RESOLUTION_NOT_CONFIGURED",
    )
    assert default.provider_calls == 0
    with pytest.raises(ValueError, match="confidence"):
        SemanticResolution(equivalent=True, confidence=1.1, reason="invalid")
    with pytest.raises(ValueError, match="reason"):
        SemanticResolution(equivalent=None, confidence=0.0, reason="")


@pytest.mark.req("REL-04")
@pytest.mark.parametrize(
    ("si_field", "bl_field"),
    [
        (_field(CanonicalField.SHIPPER, status=FieldStatus.MISSING), _field(CanonicalField.SHIPPER)),
        (_field(CanonicalField.SHIPPER), _field(CanonicalField.SHIPPER, status=FieldStatus.MISSING)),
        (_field(CanonicalField.SHIPPER, status=FieldStatus.MISSING), _field(CanonicalField.SHIPPER, status=FieldStatus.MISSING)),
        (_field(CanonicalField.SHIPPER, None, status=FieldStatus.AMBIGUOUS, raw_value="A or B"), _field(CanonicalField.SHIPPER)),
        (_field(CanonicalField.SHIPPER, None, status=FieldStatus.UNRESOLVED, raw_value="?"), _field(CanonicalField.SHIPPER)),
        (_field(CanonicalField.SHIPPER, "   "), _field(CanonicalField.SHIPPER, "\n")),
        (_field(CanonicalField.SHIPPER, "ABC International"), _field(CanonicalField.SHIPPER, "ABC Intl")),
    ],
)
def test_default_comparison_prefers_unresolved_to_an_unsupported_decision(
    si_field,
    bl_field,
):
    result = ComparisonService().compare_field(
        CanonicalField.SHIPPER,
        si_field,
        bl_field,
    )
    assert result.status == FieldComparisonStatus.UNRESOLVED


def test_comparison_is_pure_over_extraction_results_and_never_mutates_inputs(monkeypatch):
    from backend.app.documents.readers.composite import CompositeDocumentReader
    from backend.app.extraction.extractor import DeterministicDocumentExtractor

    monkeypatch.setattr(
        CompositeDocumentReader,
        "read",
        lambda *_args, **_kwargs: pytest.fail("comparison reopened a document"),
    )
    monkeypatch.setattr(
        DeterministicDocumentExtractor,
        "extract",
        lambda *_args, **_kwargs: pytest.fail("comparison reran extraction"),
    )
    si = _extraction("SI")
    bl = _extraction("DRAFT_BL")
    before_si = copy.deepcopy(si)
    before_bl = copy.deepcopy(bl)

    result = ComparisonService().compare(si, bl)

    assert len(result.fields) == 7
    assert si == before_si
    assert bl == before_bl


def test_default_l1_is_an_explicit_no_decision_placeholder():
    result = DefaultL1Comparator().compare(
        CanonicalField.SHIPPER,
        "ABC Trading Sdn. Bhd.",
        "ABC Trading Sdn Bhd",
    )
    assert result.decision == LayerDecision.NO_DECISION
