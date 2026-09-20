from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any, Callable

from backend.app.comparison.models import LayerDecision, LayerResolution
from backend.app.comparison.normalization import l0_normalize
from backend.app.extraction.models import CanonicalField


_CONTAINER_COMPOUND = re.compile(r"^0*([0-9]+)\s*(?:x|×)\s*(\S(?:.*\S)?)$", re.IGNORECASE)
_CONTAINER_SIMPLE = re.compile(r"^0*([0-9]+)(?:\s+containers?)?$", re.IGNORECASE)
_WEIGHT = re.compile(
    r"^(?P<number>(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\.[0-9]+)?)"
    r"\s*(?:kg|kgs|kilograms?)?$",
    re.IGNORECASE,
)
_ENTITY_ABBREVIATION_PERIOD = re.compile(r"(?<=[^\W\d_])\.(?=\s|$)", re.UNICODE)
_ENTITY_FIELDS = frozenset(
    {
        CanonicalField.SHIPPER,
        CanonicalField.CONSIGNEE,
        CanonicalField.NOTIFY_PARTY,
    }
)
_PORT_FIELDS = frozenset(
    {
        CanonicalField.PORT_OF_LOADING,
        CanonicalField.PORT_OF_DISCHARGE,
    }
)


class PortAliasRegistry:
    """Validated exact lookup for approved port names and UN/LOCODE aliases."""

    def __init__(self, config_path: Path | None = None) -> None:
        path = config_path or Path(__file__).with_name("port_aliases.json")
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.version = str(payload.get("version", ""))
        self._aliases: dict[str, str] = {}
        self.canonical_ports: frozenset[str]

        canonical_ports: set[str] = set()
        for entry in payload.get("ports", []):
            canonical = self._key(entry["canonical"])
            if not canonical:
                raise ValueError("port alias canonical name cannot be empty")
            canonical_ports.add(canonical)
            self._register(canonical, canonical)
            for alias in entry.get("aliases", []):
                self._register(self._key(alias), canonical)
        self.canonical_ports = frozenset(canonical_ports)

    def resolve(self, value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        return self._aliases.get(self._key(value))

    def _register(self, alias: str, canonical: str) -> None:
        if not alias:
            raise ValueError("port alias cannot be empty")
        existing = self._aliases.get(alias)
        if existing is not None and existing != canonical:
            raise ValueError(f"port alias {alias!r} maps to multiple canonical ports")
        self._aliases[alias] = canonical

    @staticmethod
    def _key(value: str) -> str:
        normalized = l0_normalize(value)
        return normalized if isinstance(normalized, str) else ""


class FieldSpecificL1Comparator:
    """Dispatch deterministic L1 rules by canonical field."""

    def __init__(self, port_aliases: PortAliasRegistry | None = None) -> None:
        self.port_aliases = port_aliases or PortAliasRegistry()
        self._comparators: dict[
            CanonicalField,
            Callable[[Any, Any], LayerResolution],
        ] = {
            CanonicalField.CONTAINER_COUNT: self._compare_container_count,
            CanonicalField.GROSS_WEIGHT_KG: self._compare_gross_weight,
            CanonicalField.PORT_OF_LOADING: self._compare_port,
            CanonicalField.PORT_OF_DISCHARGE: self._compare_port,
            CanonicalField.SHIPPER: self._compare_entity,
            CanonicalField.CONSIGNEE: self._compare_entity,
            CanonicalField.NOTIFY_PARTY: self._compare_entity,
        }

    def compare(
        self,
        field_name: CanonicalField,
        si_value: Any,
        bl_value: Any,
    ) -> LayerResolution:
        if not isinstance(field_name, CanonicalField):
            field_name = CanonicalField(field_name)
        return self._comparators[field_name](si_value, bl_value)

    @staticmethod
    def _compare_container_count(si_value: Any, bl_value: Any) -> LayerResolution:
        si_count, si_type = _parse_container_count(si_value)
        bl_count, bl_type = _parse_container_count(bl_value)
        evidence = {"si_container_type": si_type, "bl_container_type": bl_type}
        if si_count is None or bl_count is None:
            return _no_decision(
                si_value,
                bl_value,
                "L1_CONTAINER_COUNT_UNPARSEABLE",
                evidence,
            )
        decision = (
            LayerDecision.EQUIVALENT if si_count == bl_count else LayerDecision.DIFFERENT
        )
        return LayerResolution(
            decision=decision,
            si_value=si_count,
            bl_value=bl_count,
            reason_code=(
                "L1_CONTAINER_COUNTS_EQUAL"
                if decision == LayerDecision.EQUIVALENT
                else "L1_CONTAINER_COUNTS_DIFFER"
            ),
            evidence=evidence,
        )

    @staticmethod
    def _compare_gross_weight(si_value: Any, bl_value: Any) -> LayerResolution:
        si_weight = _parse_weight_kg(si_value)
        bl_weight = _parse_weight_kg(bl_value)
        if si_weight is None or bl_weight is None:
            return _no_decision(
                si_value,
                bl_value,
                "L1_GROSS_WEIGHT_UNPARSEABLE",
                {"unit": "kg"},
            )
        decision = (
            LayerDecision.EQUIVALENT
            if si_weight == bl_weight
            else LayerDecision.DIFFERENT
        )
        return LayerResolution(
            decision=decision,
            si_value=si_weight,
            bl_value=bl_weight,
            reason_code=(
                "L1_GROSS_WEIGHTS_EQUAL"
                if decision == LayerDecision.EQUIVALENT
                else "L1_GROSS_WEIGHTS_DIFFER"
            ),
            evidence={"unit": "kg"},
        )

    def _compare_port(self, si_value: Any, bl_value: Any) -> LayerResolution:
        si_port = self.port_aliases.resolve(si_value)
        bl_port = self.port_aliases.resolve(bl_value)
        evidence = {
            "alias_registry_version": self.port_aliases.version,
            "si_approved_port": si_port,
            "bl_approved_port": bl_port,
        }
        if si_port is None or bl_port is None:
            return _no_decision(
                si_value,
                bl_value,
                "L1_PORT_ALIAS_NOT_APPROVED",
                evidence,
            )
        decision = LayerDecision.EQUIVALENT if si_port == bl_port else LayerDecision.DIFFERENT
        return LayerResolution(
            decision=decision,
            si_value=si_port,
            bl_value=bl_port,
            reason_code=(
                "L1_APPROVED_PORTS_EQUAL"
                if decision == LayerDecision.EQUIVALENT
                else "L1_APPROVED_PORTS_DIFFER"
            ),
            evidence=evidence,
        )

    @staticmethod
    def _compare_entity(si_value: Any, bl_value: Any) -> LayerResolution:
        si_entity = _normalize_entity(si_value)
        bl_entity = _normalize_entity(bl_value)
        if si_entity is None or bl_entity is None:
            return _no_decision(
                si_value,
                bl_value,
                "L1_ENTITY_VALUE_UNSUPPORTED",
            )
        if si_entity == bl_entity:
            return LayerResolution(
                decision=LayerDecision.EQUIVALENT,
                si_value=si_entity,
                bl_value=bl_entity,
                reason_code="L1_SAFE_ENTITY_PUNCTUATION_EQUAL",
                evidence={"rule": "abbreviation_periods_only"},
            )
        return _no_decision(
            si_entity,
            bl_entity,
            "L1_ENTITY_EQUIVALENCE_UNPROVEN",
            {"rule": "meaningful_tokens_preserved"},
        )


def _parse_container_count(value: Any) -> tuple[int | None, str | None]:
    if isinstance(value, bool):
        return None, None
    if isinstance(value, int) and value >= 0:
        return value, None
    if isinstance(value, float) and math.isfinite(value) and value >= 0 and value.is_integer():
        return int(value), None
    if not isinstance(value, str):
        return None, None
    compound = _CONTAINER_COMPOUND.fullmatch(value.strip())
    if compound:
        return int(compound.group(1)), compound.group(2).strip()
    simple = _CONTAINER_SIMPLE.fullmatch(value.strip())
    if simple:
        return int(simple.group(1)), None
    return None, None


def _parse_weight_kg(value: Any) -> int | float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        numeric = float(value)
        if not math.isfinite(numeric) or numeric < 0:
            return None
        return int(numeric) if numeric.is_integer() else numeric
    if not isinstance(value, str):
        return None
    match = _WEIGHT.fullmatch(value.strip())
    if not match:
        return None
    numeric = float(match.group("number").replace(",", ""))
    if not math.isfinite(numeric):
        return None
    return int(numeric) if numeric.is_integer() else numeric


def _normalize_entity(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    without_abbreviation_periods = _ENTITY_ABBREVIATION_PERIOD.sub("", value)
    normalized = l0_normalize(without_abbreviation_periods)
    return normalized if normalized else None


def _no_decision(
    si_value: Any,
    bl_value: Any,
    reason_code: str,
    evidence: dict[str, Any] | None = None,
) -> LayerResolution:
    return LayerResolution(
        decision=LayerDecision.NO_DECISION,
        si_value=si_value,
        bl_value=bl_value,
        reason_code=reason_code,
        evidence=evidence or {},
    )
