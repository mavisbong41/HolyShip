from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from backend.app.documents.models import DocumentCell, DocumentTable, DocumentType, UnifiedDocument
from backend.app.extraction.label_mapping import LabelMapper
from backend.app.extraction.models import (
    CANONICAL_FIELDS,
    CanonicalField,
    DocumentExtractionResult,
    ExtractedField,
    FieldStatus,
    LabelMappingContext,
    MappingMethod,
    SourceLocation,
)


EXTRACTOR_VERSION = "phase3-deterministic-v1"
_LABEL_VALUE = re.compile(r"^(?P<label>[^:：\?]{1,160})\s*[:：\?]+\s*(?P<value>.*)$")
_TO_ORDER_VALUE = re.compile(r"^(?P<label>To\s+the\s+Order\s+of(?:\s*\([^\)]*\))?)(?:\s*[:：\?]+\s*|\s+)(?P<value>.+)$", re.IGNORECASE)

_PLACEHOLDER_VALUE = re.compile(r"^(?:N/?A|TBA|TBD|\?+|_+[A-Z0-9]*|to be advised|pending)$", re.IGNORECASE)
_NUMBER_WITH_KG = re.compile(r"^([0-9][0-9,]*(?:\.[0-9]+)?)\s*(?:kg|kgs|kilograms?)?$", re.IGNORECASE)
_CONTAINER_COMPOUND = re.compile(r"^([0-9]+)\s*(?:x|×)\s*(.+)$", re.IGNORECASE)
_CONTAINER_SIMPLE = re.compile(r"^0*([0-9]+)(?:\s+containers?)?$", re.IGNORECASE)
_MULTILINE_FIELDS = {
    CanonicalField.SHIPPER,
    CanonicalField.CONSIGNEE,
    CanonicalField.NOTIFY_PARTY,
}
_SINGLE_FOLLOWING_LINE_FIELDS = {
    CanonicalField.PORT_OF_LOADING,
    CanonicalField.PORT_OF_DISCHARGE,
}


@dataclass(frozen=True)
class _Candidate:
    canonical_field: CanonicalField
    raw_label: str
    raw_value: Any
    canonical_value: Any
    status: FieldStatus
    confidence: float
    mapping_method: MappingMethod
    source_location: SourceLocation
    evidence: dict[str, Any] = field(default_factory=dict)


class DeterministicDocumentExtractor:
    """One coordinated deterministic pass that returns all seven field slots."""

    def __init__(
        self,
        mapper: LabelMapper | None = None,
        *,
        version: str = EXTRACTOR_VERSION,
    ):
        self.mapper = mapper or LabelMapper()
        self.version = version

    def extract(self, document: UnifiedDocument) -> DocumentExtractionResult:
        candidates: dict[CanonicalField, list[_Candidate]] = {
            field_name: [] for field_name in CANONICAL_FIELDS
        }
        self._scan_tables(document, candidates)
        self._scan_text(document, candidates)

        fields = {
            field_name: self._resolve(field_name, candidates[field_name])
            for field_name in CANONICAL_FIELDS
        }
        return DocumentExtractionResult(
            document_role=document.document_type.value,
            fields=fields,
            extractor_version=self.version,
        )

    def _scan_tables(
        self,
        document: UnifiedDocument,
        candidates: dict[CanonicalField, list[_Candidate]],
    ) -> None:
        for table in document.tables:
            row_index = 0
            while row_index < len(table.rows):
                row = table.rows[row_index]
                mapped_cells = [self.mapper.map_label(str(value)) for value in row]
                mapped_positions = [
                    index for index, mapping in enumerate(mapped_cells) if mapping.canonical_field is not None
                ]

                # A header row followed by a value row is a deterministic vertical table.
                if (
                    len(mapped_positions) >= 2
                    and row_index + 1 < len(table.rows)
                    and len(table.rows[row_index + 1]) >= len(row)
                ):
                    value_row = table.rows[row_index + 1]
                    for column_index in mapped_positions:
                        self._add_candidate(
                            candidates,
                            mapping=mapped_cells[column_index],
                            raw_value=value_row[column_index],
                            method=MappingMethod.TABLE_STRUCTURE,
                            location=self._table_location(
                                table,
                                row_index,
                                column_index,
                                row_index + 1,
                                column_index,
                            ),
                            evidence={"table_orientation": "header_value_rows"},
                        )
                    row_index += 2
                    continue

                if len(row) >= 2:
                    mapping = mapped_cells[0]
                    if mapping.canonical_field is not None:
                        raw_value: Any
                        if len(row) == 2:
                            raw_value = row[1]
                        else:
                            raw_value = " ".join(str(value) for value in row[1:])
                        self._add_candidate(
                            candidates,
                            mapping=mapping,
                            raw_value=raw_value,
                            method=MappingMethod.TABLE_STRUCTURE,
                            location=self._table_location(table, row_index, 0, row_index, 1),
                            evidence={
                                "table_orientation": "key_value_row",
                                "label_mapping_method": mapping.mapping_method.value,
                            },
                        )
                row_index += 1

    def _scan_text(
        self,
        document: UnifiedDocument,
        candidates: dict[CanonicalField, list[_Candidate]],
    ) -> None:
        pages = document.pages or []
        page_texts = [(page.page_number, page.text) for page in pages]
        if not page_texts:
            page_texts = [(1, document.raw_text)]

        for page_number, text in page_texts:
            lines = text.splitlines()
            index = 0
            while index < len(lines):
                original_line = lines[index]
                line = original_line.strip()
                if not line:
                    index += 1
                    continue

                contextual = _TO_ORDER_VALUE.fullmatch(line)
                if contextual:
                    raw_label = contextual.group("label")
                    raw_value = contextual.group("value").strip()
                    mapping = self.mapper.map_label(
                        raw_label,
                        context=LabelMappingContext(
                            document_role=document.document_type.value,
                            section="consignee",
                            negotiable_bill_of_lading=document.document_type == DocumentType.DRAFT_BL,
                        ),
                    )
                    if mapping.canonical_field is not None:
                        self._add_candidate(
                            candidates,
                            mapping=mapping,
                            raw_value=raw_value,
                            method=mapping.mapping_method,
                            location=SourceLocation(
                                source_type="text",
                                page_number=page_number,
                                line_number=index + 1,
                                text_span=original_line,
                            ),
                        )
                    index += 1
                    continue

                match = _LABEL_VALUE.fullmatch(line)
                if match:
                    raw_label = match.group("label").strip()
                    raw_value = match.group("value").strip()
                    mapping = self.mapper.map_label(raw_label)
                    if mapping.canonical_field is not None and raw_value:
                        self._add_candidate(
                            candidates,
                            mapping=mapping,
                            raw_value=raw_value,
                            method=mapping.mapping_method,
                            location=SourceLocation(
                                source_type="text",
                                page_number=page_number,
                                line_number=index + 1,
                                text_span=original_line,
                            ),
                        )
                        index += 1
                        continue
                    if mapping.canonical_field is None:
                        index += 1
                        continue
                    # An explicit empty ``Label:`` begins a conservative
                    # multiline block for entity fields.
                    line = raw_label

                mapping = self.mapper.map_label(line)
                if mapping.canonical_field is None:
                    index += 1
                    continue

                value_lines: list[str] = []
                if mapping.canonical_field in _MULTILINE_FIELDS:
                    cursor = index + 1
                    while cursor < len(lines):
                        candidate_line = lines[cursor].strip()
                        if not candidate_line:
                            break
                        if self._line_starts_mapped_field(candidate_line):
                            break
                        value_lines.append(candidate_line)
                        cursor += 1
                elif mapping.canonical_field in _SINGLE_FOLLOWING_LINE_FIELDS and index + 1 < len(lines):
                    candidate_line = lines[index + 1].strip()
                    if candidate_line and not self._line_starts_mapped_field(candidate_line):
                        value_lines.append(candidate_line)
                        cursor = index + 2
                    else:
                        cursor = index + 1
                else:
                    cursor = index + 1

                if value_lines:
                    raw_value = "\n".join(value_lines)
                    self._add_candidate(
                        candidates,
                        mapping=mapping,
                        raw_value=raw_value,
                        method=mapping.mapping_method,
                        location=SourceLocation(
                            source_type="text",
                            page_number=page_number,
                            line_number=index + 1,
                            text_span="\n".join([original_line, *value_lines]),
                        ),
                    )
                    index = cursor
                else:
                    index += 1

    def _line_starts_mapped_field(self, line: str) -> bool:
        contextual = _TO_ORDER_VALUE.fullmatch(line)
        if contextual:
            return True
        match = _LABEL_VALUE.fullmatch(line)
        label = match.group("label").strip() if match else line
        return self.mapper.map_label(label).canonical_field is not None

    def _add_candidate(
        self,
        candidates: dict[CanonicalField, list[_Candidate]],
        *,
        mapping,
        raw_value: Any,
        method: MappingMethod,
        location: SourceLocation,
        evidence: dict[str, Any] | None = None,
    ) -> None:
        field_name = mapping.canonical_field
        if field_name is None:
            return
        canonical_value, parse_evidence = self._canonicalize(field_name, raw_value)
        status = FieldStatus.RESOLVED if canonical_value is not None else FieldStatus.UNRESOLVED
        candidate = _Candidate(
            canonical_field=field_name,
            raw_label=mapping.raw_label,
            raw_value=raw_value,
            canonical_value=canonical_value,
            status=status,
            confidence=mapping.confidence if status == FieldStatus.RESOLVED else 0.0,
            mapping_method=method,
            source_location=location,
            evidence={**mapping.evidence, **(evidence or {}), **parse_evidence},
        )
        signature = (
            candidate.raw_label,
            self._stable_value(candidate.raw_value),
            self._stable_value(candidate.canonical_value),
        )
        if not any(
            (
                existing.raw_label,
                self._stable_value(existing.raw_value),
                self._stable_value(existing.canonical_value),
            )
            == signature
            for existing in candidates[field_name]
        ):
            candidates[field_name].append(candidate)

    @staticmethod
    def _canonicalize(field_name: CanonicalField, raw_value: Any) -> tuple[Any, dict[str, Any]]:
        if isinstance(raw_value, str) and _PLACEHOLDER_VALUE.fullmatch(raw_value.strip()):
            return None, {"parse_reason": "PLACEHOLDER_VALUE"}
        if field_name == CanonicalField.CONTAINER_COUNT:
            return DeterministicDocumentExtractor._parse_container_count(raw_value)
        if field_name == CanonicalField.GROSS_WEIGHT_KG:
            return DeterministicDocumentExtractor._parse_gross_weight(raw_value)
        if isinstance(raw_value, str):
            value = raw_value.strip()
            return (value if value else None), {}
        return raw_value, {}

    @staticmethod
    def _parse_container_count(raw_value: Any) -> tuple[int | None, dict[str, Any]]:
        if isinstance(raw_value, bool):
            return None, {"parse_reason": "BOOLEAN_IS_NOT_CONTAINER_COUNT"}
        if isinstance(raw_value, int) and raw_value >= 0:
            return raw_value, {}
        if isinstance(raw_value, float) and raw_value >= 0 and raw_value.is_integer():
            return int(raw_value), {}
        if not isinstance(raw_value, str):
            return None, {"parse_reason": "UNSUPPORTED_CONTAINER_VALUE"}
        value = raw_value.strip()
        compound = _CONTAINER_COMPOUND.fullmatch(value)
        if compound:
            return int(compound.group(1)), {"container_type": compound.group(2).strip()}
        simple = _CONTAINER_SIMPLE.fullmatch(value)
        if simple:
            return int(simple.group(1)), {}
        return None, {"parse_reason": "UNRECOGNIZED_CONTAINER_FORMAT"}

    @staticmethod
    def _parse_gross_weight(raw_value: Any) -> tuple[int | float | None, dict[str, Any]]:
        if isinstance(raw_value, bool):
            return None, {"parse_reason": "BOOLEAN_IS_NOT_WEIGHT"}
        if isinstance(raw_value, (int, float)) and raw_value >= 0:
            value = float(raw_value)
            return (int(value) if value.is_integer() else value), {"unit": "kg"}
        if not isinstance(raw_value, str):
            return None, {"parse_reason": "UNSUPPORTED_WEIGHT_VALUE"}
        match = _NUMBER_WITH_KG.fullmatch(raw_value.strip())
        if not match:
            return None, {"parse_reason": "UNRECOGNIZED_GROSS_WEIGHT_FORMAT"}
        value = float(match.group(1).replace(",", ""))
        return (int(value) if value.is_integer() else value), {"unit": "kg"}

    @staticmethod
    def _stable_value(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)

    @staticmethod
    def _table_location(
        table: DocumentTable,
        label_row: int,
        label_column: int,
        value_row: int,
        value_column: int,
    ) -> SourceLocation:
        label_cell = DeterministicDocumentExtractor._cell_at(table, label_row, label_column)
        value_cell = DeterministicDocumentExtractor._cell_at(table, value_row, value_column)
        actual_row = label_cell.row_index if label_cell is not None else label_row + 1
        return SourceLocation(
            source_type="table",
            page_number=table.page_number,
            table_name=table.title,
            row_index=actual_row,
            label_cell=label_cell.coordinate if label_cell is not None else f"R{label_row + 1}C{label_column + 1}",
            value_cell=value_cell.coordinate if value_cell is not None else f"R{value_row + 1}C{value_column + 1}",
        )

    @staticmethod
    def _cell_at(table: DocumentTable, row_index: int, column_index: int) -> DocumentCell | None:
        if row_index >= len(table.cells) or column_index >= len(table.cells[row_index]):
            return None
        return table.cells[row_index][column_index]

    @staticmethod
    def _resolve(field_name: CanonicalField, candidates: list[_Candidate]) -> ExtractedField:
        if not candidates:
            return ExtractedField(
                canonical_field=field_name,
                raw_label=None,
                raw_value=None,
                canonical_value=None,
                status=FieldStatus.MISSING,
                confidence=0.0,
                mapping_method=None,
                source_location=SourceLocation(source_type="none"),
                evidence={"reason_code": "FIELD_NOT_PRESENT"},
            )

        resolved = [candidate for candidate in candidates if candidate.status == FieldStatus.RESOLVED]
        distinct_values = {
            DeterministicDocumentExtractor._stable_value(candidate.canonical_value)
            for candidate in resolved
        }
        if len(distinct_values) == 1:
            selected = resolved[0]
            return ExtractedField(
                canonical_field=field_name,
                raw_label=selected.raw_label,
                raw_value=selected.raw_value,
                canonical_value=selected.canonical_value,
                status=FieldStatus.RESOLVED,
                confidence=selected.confidence,
                mapping_method=selected.mapping_method,
                source_location=selected.source_location,
                evidence=selected.evidence,
            )
        if len(distinct_values) > 1:
            return ExtractedField(
                canonical_field=field_name,
                raw_label=None,
                raw_value=None,
                canonical_value=None,
                status=FieldStatus.AMBIGUOUS,
                confidence=0.0,
                mapping_method=None,
                source_location=SourceLocation(source_type="multiple"),
                evidence={
                    "reason_code": "CONFLICTING_FIELD_VALUES",
                    "candidates": [
                        {
                            "raw_label": candidate.raw_label,
                            "raw_value": candidate.raw_value,
                            "canonical_value": candidate.canonical_value,
                            "mapping_method": candidate.mapping_method.value,
                            "source_location": candidate.source_location.to_dict(),
                        }
                        for candidate in resolved
                    ],
                },
            )

        selected = candidates[0]
        return ExtractedField(
            canonical_field=field_name,
            raw_label=selected.raw_label,
            raw_value=selected.raw_value,
            canonical_value=None,
            status=FieldStatus.UNRESOLVED,
            confidence=0.0,
            mapping_method=selected.mapping_method,
            source_location=selected.source_location,
            evidence=selected.evidence,
        )
