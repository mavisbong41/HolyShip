from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CanonicalField(str, Enum):
    SHIPPER = "shipper"
    CONSIGNEE = "consignee"
    NOTIFY_PARTY = "notify_party"
    PORT_OF_LOADING = "port_of_loading"
    PORT_OF_DISCHARGE = "port_of_discharge"
    CONTAINER_COUNT = "container_count"
    GROSS_WEIGHT_KG = "gross_weight_kg"


CANONICAL_FIELDS: tuple[CanonicalField, ...] = tuple(CanonicalField)


class MappingMethod(str, Enum):
    EXACT_LABEL = "exact_label"
    ALIAS_DICTIONARY = "alias_dictionary"
    BILINGUAL_LABEL_NORMALIZATION = "bilingual_label_normalization"
    CONTEXTUAL_BUSINESS_RULE = "contextual_business_rule"
    TABLE_STRUCTURE = "table_structure"
    LLM_RESOLVED = "llm_resolved"


class FieldStatus(str, Enum):
    RESOLVED = "RESOLVED"
    MISSING = "MISSING"
    UNRESOLVED = "UNRESOLVED"
    AMBIGUOUS = "AMBIGUOUS"


@dataclass(frozen=True)
class SourceLocation:
    source_type: str
    page_number: int | None = None
    line_number: int | None = None
    text_span: str | None = None
    table_name: str | None = None
    row_index: int | None = None
    label_cell: str | None = None
    value_cell: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            key: value
            for key, value in {
                "source_type": self.source_type,
                "page_number": self.page_number,
                "line_number": self.line_number,
                "text_span": self.text_span,
                "table_name": self.table_name,
                "row_index": self.row_index,
                "label_cell": self.label_cell,
                "value_cell": self.value_cell,
            }.items()
            if value is not None
        }


@dataclass(frozen=True)
class ExtractedField:
    canonical_field: CanonicalField
    raw_label: str | None
    raw_value: Any
    canonical_value: Any
    status: FieldStatus
    confidence: float
    mapping_method: MappingMethod | None
    source_location: SourceLocation
    evidence: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.canonical_field, CanonicalField):
            object.__setattr__(self, "canonical_field", CanonicalField(self.canonical_field))
        if not isinstance(self.status, FieldStatus):
            object.__setattr__(self, "status", FieldStatus(self.status))
        if self.mapping_method is not None and not isinstance(self.mapping_method, MappingMethod):
            object.__setattr__(self, "mapping_method", MappingMethod(self.mapping_method))
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if self.status == FieldStatus.MISSING:
            if self.raw_label is not None or self.raw_value is not None or self.canonical_value is not None:
                raise ValueError("missing fields cannot fabricate labels or values")
            if self.mapping_method is not None:
                raise ValueError("missing fields cannot claim a mapping method")


@dataclass(frozen=True)
class DocumentExtractionResult:
    document_role: str
    fields: dict[CanonicalField, ExtractedField]
    extractor_version: str

    def __post_init__(self) -> None:
        if set(self.fields) != set(CANONICAL_FIELDS):
            raise ValueError("document extraction must contain exactly the seven canonical fields")
        for field_name, result in self.fields.items():
            if result.canonical_field != field_name:
                raise ValueError("field result key and canonical field must agree")


@dataclass(frozen=True)
class LabelMappingContext:
    """Explicit business context required by contextual label rules."""

    document_role: str | None = None
    section: str | None = None
    negotiable_bill_of_lading: bool = False

    @property
    def is_negotiable_bl_consignee_context(self) -> bool:
        role = (self.document_role or "").strip().upper()
        section = (self.section or "").strip().casefold().replace("_", " ")
        return (
            role in {"BL", "DRAFT_BL", "BILL OF LADING"}
            and self.negotiable_bill_of_lading
            and section in {"consignee", "consignee or order", "order consignee"}
        )


@dataclass(frozen=True)
class LabelMappingResult:
    raw_label: str
    canonical_field: CanonicalField | None
    mapping_method: MappingMethod | None
    confidence: float
    reason_code: str
    evidence: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.raw_label, str):
            raise TypeError("raw_label must be a string")
        if self.canonical_field is not None and not isinstance(self.canonical_field, CanonicalField):
            object.__setattr__(self, "canonical_field", CanonicalField(self.canonical_field))
        if self.mapping_method is not None and not isinstance(self.mapping_method, MappingMethod):
            object.__setattr__(self, "mapping_method", MappingMethod(self.mapping_method))
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if self.canonical_field is None and self.mapping_method is not None:
            raise ValueError("unresolved mappings cannot claim a mapping method")
        if self.canonical_field is not None and self.mapping_method is None:
            raise ValueError("resolved mappings must record a mapping method")
