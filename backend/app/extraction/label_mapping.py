from __future__ import annotations

import json
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from backend.app.extraction.models import (
    CANONICAL_FIELDS,
    CanonicalField,
    LabelMappingContext,
    LabelMappingResult,
    MappingMethod,
)


DEFAULT_LABEL_CONFIG = Path(__file__).with_name("field_labels.json")
_TRAILING_SEPARATOR = re.compile(r"\s*[:：]\s*$")
_EXPLICIT_NON_GROSS = re.compile(r"(?:^|\b)(?:net|tare)\s+(?:weight|wt)(?:\b|\s*\()", re.IGNORECASE)
_TO_THE_ORDER_OF = re.compile(r"^to\s+the\s+order\s+of(?:\s+.+)?$", re.IGNORECASE)


def normalize_label_for_lookup(raw_label: str) -> str:
    """Normalize only syntax that is safe for exact dictionary lookup."""

    normalized = unicodedata.normalize("NFKC", raw_label)
    normalized = _TRAILING_SEPARATOR.sub("", normalized)
    return " ".join(normalized.split()).casefold()


@dataclass(frozen=True)
class _Candidate:
    canonical_field: CanonicalField
    method: MappingMethod


class LabelMapper:
    """Strict config-backed label mapper. It intentionally performs no fuzzy lookup."""

    def __init__(self, config_path: str | Path | None = None):
        self.config_path = Path(config_path) if config_path is not None else DEFAULT_LABEL_CONFIG
        config = json.loads(self.config_path.read_text(encoding="utf-8"))
        fields = config.get("fields")
        if not isinstance(fields, dict):
            raise ValueError("field label configuration must contain a fields object")
        if set(fields) != {field.value for field in CANONICAL_FIELDS}:
            raise ValueError("field label configuration must define exactly the seven canonical fields")

        candidates: dict[str, list[_Candidate]] = defaultdict(list)
        for field in CANONICAL_FIELDS:
            field_config = fields[field.value]
            if not isinstance(field_config, dict):
                raise ValueError(f"configuration for {field.value} must be an object")
            self._add_labels(
                candidates,
                field,
                MappingMethod.EXACT_LABEL,
                field_config.get("exact_labels", []),
            )
            self._add_labels(
                candidates,
                field,
                MappingMethod.ALIAS_DICTIONARY,
                field_config.get("aliases", []),
            )
            self._add_labels(
                candidates,
                field,
                MappingMethod.BILINGUAL_LABEL_NORMALIZATION,
                field_config.get("bilingual_labels", []),
            )
        self._candidates = dict(candidates)
        self._explicit_non_gross = {
            normalize_label_for_lookup(label)
            for label in config.get("explicit_non_gross_weight_labels", [])
        }

    @staticmethod
    def _add_labels(
        candidates: dict[str, list[_Candidate]],
        field: CanonicalField,
        method: MappingMethod,
        labels: Iterable[str],
    ) -> None:
        if not isinstance(labels, list) or not all(isinstance(label, str) for label in labels):
            raise ValueError(f"{method.value} labels for {field.value} must be a string list")
        for label in labels:
            normalized = normalize_label_for_lookup(label)
            if not normalized:
                raise ValueError(f"empty configured label for {field.value}")
            candidate = _Candidate(field, method)
            if candidate not in candidates[normalized]:
                candidates[normalized].append(candidate)

    def map_label(
        self,
        raw_label: str,
        *,
        context: LabelMappingContext | None = None,
    ) -> LabelMappingResult:
        if not isinstance(raw_label, str):
            raise TypeError("raw_label must be a string")
        normalized = normalize_label_for_lookup(raw_label)

        if self._is_explicit_non_gross_weight(normalized):
            return self._unresolved(raw_label, "NON_GROSS_WEIGHT_LABEL")

        if _TO_THE_ORDER_OF.fullmatch(normalized):
            if context is not None and context.is_negotiable_bl_consignee_context:
                return LabelMappingResult(
                    raw_label=raw_label,
                    canonical_field=CanonicalField.CONSIGNEE,
                    mapping_method=MappingMethod.CONTEXTUAL_BUSINESS_RULE,
                    confidence=1.0,
                    reason_code="NEGOTIABLE_BL_CONSIGNEE_ORDER_LABEL",
                    evidence={
                        "document_role": context.document_role,
                        "section": context.section,
                        "negotiable_bill_of_lading": True,
                    },
                )
            return self._unresolved(raw_label, "CONTEXT_REQUIRED")

        candidates = self._candidates.get(normalized, [])
        fields = {candidate.canonical_field for candidate in candidates}
        if len(fields) > 1:
            return self._unresolved(
                raw_label,
                "AMBIGUOUS_LABEL",
                {"candidate_fields": sorted(field.value for field in fields)},
            )
        if not candidates:
            return self._unresolved(raw_label, "UNMAPPED_LABEL")

        selected = min(candidates, key=lambda item: list(MappingMethod).index(item.method))
        confidence = {
            MappingMethod.EXACT_LABEL: 1.0,
            MappingMethod.ALIAS_DICTIONARY: 0.99,
            MappingMethod.BILINGUAL_LABEL_NORMALIZATION: 0.99,
        }[selected.method]
        return LabelMappingResult(
            raw_label=raw_label,
            canonical_field=selected.canonical_field,
            mapping_method=selected.method,
            confidence=confidence,
            reason_code="LABEL_MAPPED",
            evidence={"normalized_lookup": normalized, "config": self.config_path.name},
        )

    def _is_explicit_non_gross_weight(self, normalized: str) -> bool:
        return (
            normalized in self._explicit_non_gross
            or "净重" in normalized
            or _EXPLICIT_NON_GROSS.search(normalized) is not None
        )

    @staticmethod
    def _unresolved(
        raw_label: str,
        reason_code: str,
        evidence: dict | None = None,
    ) -> LabelMappingResult:
        return LabelMappingResult(
            raw_label=raw_label,
            canonical_field=None,
            mapping_method=None,
            confidence=0.0,
            reason_code=reason_code,
            evidence=evidence or {},
        )
