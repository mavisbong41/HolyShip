from __future__ import annotations

import json

import pytest

from backend.app.extraction.label_mapping import DEFAULT_LABEL_CONFIG, LabelMapper
from backend.app.extraction.models import (
    CANONICAL_FIELDS,
    CanonicalField,
    LabelMappingContext,
    LabelMappingResult,
    MappingMethod,
)


def test_canonical_field_contract_contains_exactly_seven_values():
    assert {field.value for field in CANONICAL_FIELDS} == {
        "shipper",
        "consignee",
        "notify_party",
        "port_of_loading",
        "port_of_discharge",
        "container_count",
        "gross_weight_kg",
    }
    assert len(CANONICAL_FIELDS) == 7


@pytest.mark.req("MAP-01")
def test_configured_exact_and_alias_labels_map_to_common_canonical_fields(tmp_path):
    mapper = LabelMapper()

    assert mapper.map_label("Shipper").canonical_field == CanonicalField.SHIPPER
    assert mapper.map_label("Load Port").canonical_field == CanonicalField.PORT_OF_LOADING
    assert mapper.map_label("Loading Port").canonical_field == CanonicalField.PORT_OF_LOADING
    assert mapper.map_label(" POL: ").canonical_field == CanonicalField.PORT_OF_LOADING
    assert mapper.map_label("POD").canonical_field == CanonicalField.PORT_OF_DISCHARGE
    assert mapper.map_label("No. of Containers").canonical_field == CanonicalField.CONTAINER_COUNT

    config = json.loads(DEFAULT_LABEL_CONFIG.read_text(encoding="utf-8"))
    config["fields"]["port_of_loading"]["aliases"].append("Origin Load Port")
    custom_path = tmp_path / "labels.json"
    custom_path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
    custom = LabelMapper(custom_path)
    assert custom.map_label("Origin Load Port").canonical_field == CanonicalField.PORT_OF_LOADING


@pytest.mark.req("MAP-02")
def test_bilingual_descriptive_labels_preserve_raw_label_and_parentheses_are_not_stripped():
    mapper = LabelMapper()
    examples = {
        "Shipper (Principal or Seller) (发货人)": CanonicalField.SHIPPER,
        "Port of Loading (POL) (装货港)": CanonicalField.PORT_OF_LOADING,
        "Gross Wt (kgs) (毛重 KGS)": CanonicalField.GROSS_WEIGHT_KG,
    }

    for raw_label, expected in examples.items():
        result = mapper.map_label(raw_label)
        assert result.raw_label == raw_label
        assert result.canonical_field == expected
        assert result.mapping_method == MappingMethod.BILINGUAL_LABEL_NORMALIZATION

    unsafe_to_strip = mapper.map_label("Port of Loading (Agent)")
    assert unsafe_to_strip.raw_label == "Port of Loading (Agent)"
    assert unsafe_to_strip.canonical_field is None
    assert unsafe_to_strip.reason_code == "UNMAPPED_LABEL"


@pytest.mark.req("MAP-03")
def test_to_the_order_of_requires_explicit_negotiable_bl_consignee_context():
    mapper = LabelMapper()
    raw_label = "To the Order of ABC Bank"
    valid_context = LabelMappingContext(
        document_role="DRAFT_BL",
        section="consignee",
        negotiable_bill_of_lading=True,
    )

    result = mapper.map_label(raw_label, context=valid_context)
    assert result.raw_label == raw_label
    assert result.canonical_field == CanonicalField.CONSIGNEE
    assert result.mapping_method == MappingMethod.CONTEXTUAL_BUSINESS_RULE

    invalid_contexts = [
        None,
        LabelMappingContext(document_role="SI", section="consignee", negotiable_bill_of_lading=True),
        LabelMappingContext(document_role="DRAFT_BL", section="notify_party", negotiable_bill_of_lading=True),
        LabelMappingContext(document_role="DRAFT_BL", section="consignee", negotiable_bill_of_lading=False),
    ]
    for context in invalid_contexts:
        assert mapper.map_label(raw_label, context=context).canonical_field is None


@pytest.mark.req("MAP-03")
@pytest.mark.parametrize(
    "label",
    ["Purchase Order", "Order Number", "Please process this order", "Delivery Order"],
)
def test_ordinary_order_language_never_maps_to_consignee(label):
    context = LabelMappingContext(
        document_role="DRAFT_BL",
        section="consignee",
        negotiable_bill_of_lading=True,
    )
    result = LabelMapper().map_label(label, context=context)
    assert result.canonical_field is None
    assert result.mapping_method is None


@pytest.mark.req("MAP-04")
def test_provenance_contract_is_exact_and_phase3_mapper_emits_only_deterministic_methods():
    assert {method.value for method in MappingMethod} == {
        "exact_label",
        "alias_dictionary",
        "bilingual_label_normalization",
        "contextual_business_rule",
        "table_structure",
        "llm_resolved",
    }
    mapper = LabelMapper()
    contextual = LabelMappingContext("DRAFT_BL", "consignee", True)
    results = [
        mapper.map_label("Shipper"),
        mapper.map_label("POL"),
        mapper.map_label("Shipper (Principal or Seller) (发货人)"),
        mapper.map_label("To the Order of ABC Bank", context=contextual),
    ]
    assert {result.mapping_method for result in results} == {
        MappingMethod.EXACT_LABEL,
        MappingMethod.ALIAS_DICTIONARY,
        MappingMethod.BILINGUAL_LABEL_NORMALIZATION,
        MappingMethod.CONTEXTUAL_BUSINESS_RULE,
    }
    assert all(result.mapping_method != MappingMethod.LLM_RESOLVED for result in results)

    with pytest.raises(ValueError):
        LabelMappingResult(
            raw_label="Shipper",
            canonical_field=CanonicalField.SHIPPER,
            mapping_method="invented_method",
            confidence=1.0,
            reason_code="LABEL_MAPPED",
        )


@pytest.mark.req("MAP-05")
def test_near_miss_and_ambiguous_business_labels_remain_unresolved(tmp_path):
    mapper = LabelMapper()
    for label in (
        "Loading Port Agent",
        "Port of Loading (Estimated)",
        "Consignee Reference",
        "Notify Party Address",
        "Gross Weight Allowance",
    ):
        result = mapper.map_label(label)
        assert result.canonical_field is None
        assert result.reason_code == "UNMAPPED_LABEL"

    config = json.loads(DEFAULT_LABEL_CONFIG.read_text(encoding="utf-8"))
    config["fields"]["shipper"]["aliases"].append("Party Name")
    config["fields"]["consignee"]["aliases"].append("Party Name")
    custom_path = tmp_path / "ambiguous-labels.json"
    custom_path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")

    ambiguous = LabelMapper(custom_path).map_label("Party Name")
    assert ambiguous.canonical_field is None
    assert ambiguous.mapping_method is None
    assert ambiguous.reason_code == "AMBIGUOUS_LABEL"
    assert ambiguous.evidence["candidate_fields"] == ["consignee", "shipper"]


@pytest.mark.req("MAP-06")
def test_non_gross_weight_labels_never_map_and_gross_net_coexist_safely():
    mapper = LabelMapper()
    for label in ("NET WEIGHT", "Net Wt", "Net Weight (KG)", "净重", "Total Net Weight"):
        result = mapper.map_label(label)
        assert result.raw_label == label
        assert result.canonical_field is None
        assert result.mapping_method is None
        assert result.reason_code == "NON_GROSS_WEIGHT_LABEL"

    gross = mapper.map_label("Gross Weight")
    net = mapper.map_label("Net Weight")
    assert gross.canonical_field == CanonicalField.GROSS_WEIGHT_KG
    assert net.canonical_field is None
