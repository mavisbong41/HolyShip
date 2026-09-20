from __future__ import annotations

import pytest

from backend.app.comparison.models import FieldComparisonStatus
from backend.app.comparison.service import ComparisonService
from backend.app.extraction.models import (
    CANONICAL_FIELDS,
    CanonicalField,
    DocumentExtractionResult,
    ExtractedField,
    FieldStatus,
    MappingMethod,
    SourceLocation,
)


def _field(name: CanonicalField, canonical_value, *, raw_value=...) -> ExtractedField:
    raw = canonical_value if raw_value is ... else raw_value
    return ExtractedField(
        canonical_field=name,
        raw_label=name.value.upper(),
        raw_value=raw,
        canonical_value=canonical_value,
        status=FieldStatus.RESOLVED,
        confidence=1.0,
        mapping_method=MappingMethod.EXACT_LABEL,
        source_location=SourceLocation(source_type="metamorphic"),
    )


MATCH_CASES = [
    ("trim", CanonicalField.SHIPPER, " ABC Trading ", "ABC Trading", None, None),
    ("spaces", CanonicalField.CONSIGNEE, "ABC   Trading", "ABC Trading", None, None),
    ("case", CanonicalField.NOTIFY_PARTY, "ABC TRADING", "abc trading", None, None),
    ("unicode", CanonicalField.SHIPPER, "Cafe\u0301 Trading", "Caf\u00e9 Trading", None, None),
    ("line_break", CanonicalField.CONSIGNEE, "ABC\nTrading", "ABC Trading", None, None),
    ("entity_punctuation", CanonicalField.SHIPPER, "ABC Sdn. Bhd.", "ABC Sdn Bhd", None, None),
    ("weight_format", CanonicalField.GROSS_WEIGHT_KG, "22,000 KG", "22000 kg", None, None),
    ("weight_native", CanonicalField.GROSS_WEIGHT_KG, 22000, "22,000 KG", 22000, "22,000 KG"),
    ("container_type", CanonicalField.CONTAINER_COUNT, 6, 6, "6 x 40'HC", "6 x 40'GP"),
    ("port_klang_code", CanonicalField.PORT_OF_LOADING, "Port Klang", "MYPKG", None, None),
    ("port_klang_display_code", CanonicalField.PORT_OF_LOADING, "Port Klang", "MY PKG", None, None),
    ("singapore_code", CanonicalField.PORT_OF_DISCHARGE, "Singapore", "SGSIN", None, None),
    ("singapore_display_code", CanonicalField.PORT_OF_DISCHARGE, "Singapore", "SG SIN", None, None),
]


@pytest.mark.req("CMP-12")
@pytest.mark.parametrize(
    ("_case", "field_name", "si_value", "bl_value", "si_raw", "bl_raw"),
    MATCH_CASES,
    ids=[case[0] for case in MATCH_CASES],
)
def test_format_and_approved_equivalence_transformations_have_zero_false_alarms(
    _case,
    field_name,
    si_value,
    bl_value,
    si_raw,
    bl_raw,
):
    result = ComparisonService().compare_field(
        field_name,
        _field(field_name, si_value, raw_value=si_value if si_raw is None else si_raw),
        _field(field_name, bl_value, raw_value=bl_value if bl_raw is None else bl_raw),
    )
    assert result.status == FieldComparisonStatus.MATCH


NEGATIVE_CASES = [
    (
        "meaningful_company_word",
        CanonicalField.SHIPPER,
        "ABC Trading Sdn Bhd",
        "ABC Logistics Sdn Bhd",
        FieldComparisonStatus.UNRESOLVED,
    ),
    (
        "geographic_word",
        CanonicalField.CONSIGNEE,
        "ABC Trading Malaysia Sdn Bhd",
        "ABC Trading Singapore Sdn Bhd",
        FieldComparisonStatus.UNRESOLVED,
    ),
    (
        "different_port",
        CanonicalField.PORT_OF_DISCHARGE,
        "Port Klang",
        "Singapore",
        FieldComparisonStatus.MISMATCH,
    ),
    (
        "different_container_count",
        CanonicalField.CONTAINER_COUNT,
        6,
        5,
        FieldComparisonStatus.MISMATCH,
    ),
    (
        "different_gross_weight",
        CanonicalField.GROSS_WEIGHT_KG,
        22000,
        23000,
        FieldComparisonStatus.MISMATCH,
    ),
]


@pytest.mark.req("CMP-12")
@pytest.mark.parametrize(
    ("_case", "field_name", "si_value", "bl_value", "expected"),
    NEGATIVE_CASES,
    ids=[case[0] for case in NEGATIVE_CASES],
)
def test_semantic_negative_controls_are_never_normalized_to_match(
    _case,
    field_name,
    si_value,
    bl_value,
    expected,
):
    result = ComparisonService().compare_field(
        field_name,
        _field(field_name, si_value),
        _field(field_name, bl_value),
    )
    assert result.status == expected
    assert result.status != FieldComparisonStatus.MATCH


def test_one_material_defect_produces_exactly_one_mismatch():
    si = DocumentExtractionResult(
        document_role="SI",
        fields={name: _field(name, 6 if name == CanonicalField.CONTAINER_COUNT else f"same-{name.value}") for name in CANONICAL_FIELDS},
        extractor_version="phase3-deterministic-v1",
    )
    bl_fields = dict(si.fields)
    bl_fields[CanonicalField.CONTAINER_COUNT] = _field(CanonicalField.CONTAINER_COUNT, 5)
    bl = DocumentExtractionResult(
        document_role="DRAFT_BL",
        fields=bl_fields,
        extractor_version=si.extractor_version,
    )

    result = ComparisonService().compare(si, bl)

    assert result.mismatched_fields == (CanonicalField.CONTAINER_COUNT,)
    assert result.unresolved_fields == ()
    assert sum(
        field.status == FieldComparisonStatus.MISMATCH for field in result.fields.values()
    ) == 1
