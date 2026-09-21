from __future__ import annotations

import difflib
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
        key = self._key(value)
        if not key:
            return None
        res = self._aliases.get(key)
        if res is not None:
            return res
        cleaned = re.sub(r"\s*\([^)]*\)", "", key).strip()
        if cleaned != key:
            res = self._aliases.get(cleaned)
            if res is not None:
                return res
        if "," in cleaned:
            port_name = cleaned.split(",")[0].strip()
            res = self._aliases.get(port_name)
            if res is not None:
                return res
            if "/" in port_name:
                for part in port_name.split("/"):
                    res = self._aliases.get(part.strip())
                    if res is not None:
                        return res
        elif "/" in cleaned:
            for part in cleaned.split("/"):
                res = self._aliases.get(part.strip())
                if res is not None:
                    return res
        return None

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


_PORT_LOCODE = re.compile(r"^(.*?)\s*\(([A-Z]{2}\s*[A-Z]{3})\)$", re.IGNORECASE)


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
        si_str = str(si_value).strip() if si_value is not None else ""
        bl_str = str(bl_value).strip() if bl_value is not None else ""
        m_si = _PORT_LOCODE.fullmatch(si_str)
        m_bl = _PORT_LOCODE.fullmatch(bl_str)
        si_name = m_si.group(1).strip() if m_si else si_str
        bl_name = m_bl.group(1).strip() if m_bl else bl_str
        si_code = m_si.group(2).replace(" ", "").upper() if m_si else None
        bl_code = m_bl.group(2).replace(" ", "").upper() if m_bl else None
        si_name_port = self.port_aliases.resolve(si_name)
        bl_name_port = self.port_aliases.resolve(bl_name)
        si_code_port = self.port_aliases.resolve(si_code) if si_code else None
        bl_code_port = self.port_aliases.resolve(bl_code) if bl_code else None

        si_port = si_name_port if si_name_port is not None else si_code_port
        bl_port = bl_name_port if bl_name_port is not None else bl_code_port

        evidence = {
            "alias_registry_version": self.port_aliases.version,
            "si_approved_port": si_port,
            "bl_approved_port": bl_port,
        }

        # If both name ports were resolved against approved registry
        if si_name_port is not None and bl_name_port is not None:
            decision = LayerDecision.EQUIVALENT if si_name_port == bl_name_port else LayerDecision.DIFFERENT
            return LayerResolution(
                decision=decision,
                si_value=si_name_port,
                bl_value=bl_name_port,
                reason_code=(
                    "L1_APPROVED_PORTS_EQUAL"
                    if decision == LayerDecision.EQUIVALENT
                    else "L1_APPROVED_PORTS_DIFFER"
                ),
                evidence=evidence,
            )

        si_norm = l0_normalize(si_name)
        bl_norm = l0_normalize(bl_name)

        # If normalized port names are identical
        if si_norm and bl_norm and si_norm == bl_norm:
            return LayerResolution(
                decision=LayerDecision.EQUIVALENT,
                si_value=si_name,
                bl_value=bl_name,
                reason_code="L1_PORT_NAMES_EQUAL",
                evidence=evidence,
            )

        # If LOCODEs match and neither name conflicts with approved names of other ports
        if si_code and bl_code and si_code == bl_code:
            if si_norm and bl_norm and si_norm != bl_norm:
                sim = difflib.SequenceMatcher(None, str(si_norm), str(bl_norm)).ratio()
                if sim < 0.8:
                    return LayerResolution(
                        decision=LayerDecision.DIFFERENT,
                        si_value=si_name,
                        bl_value=bl_name,
                        reason_code="L1_PORT_NAMES_DIFFER",
                        evidence=evidence,
                    )
            return LayerResolution(
                decision=LayerDecision.EQUIVALENT,
                si_value=si_name,
                bl_value=bl_name,
                reason_code="L1_PORT_MATCH",
                evidence=evidence,
            )

        # If both ports were resolved via name/code
        if si_port is not None and bl_port is not None:
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

        # If one or both are unapproved, check similarity
        if si_norm and bl_norm and si_norm != bl_norm:
            sim = difflib.SequenceMatcher(None, str(si_norm), str(bl_norm)).ratio()
            if sim >= 0.8:
                return _no_decision(
                    si_value,
                    bl_value,
                    "L1_PORT_ALIAS_NOT_APPROVED",
                    evidence,
                )
            return LayerResolution(
                decision=LayerDecision.DIFFERENT,
                si_value=si_name,
                bl_value=bl_name,
                reason_code="L1_PORT_NAMES_DIFFER",
                evidence=evidence,
            )

        return _no_decision(
            si_value,
            bl_value,
            "L1_PORT_ALIAS_NOT_APPROVED",
            evidence,
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
        if _is_entity_candidate_for_l2(str(si_value), str(bl_value)):
            return _no_decision(
                si_value,
                bl_value,
                "L1_ENTITY_DIFFERENCE_REQUIRES_L2",
                {"rule": "meaningful_tokens_differ"},
            )
        return LayerResolution(
            decision=LayerDecision.DIFFERENT,
            si_value=si_entity,
            bl_value=bl_entity,
            reason_code="L1_ENTITY_DIFFER",
            evidence={"rule": "distinct_entities"},
        )


def _is_entity_candidate_for_l2(a: str, b: str) -> bool:
    a_low, b_low = a.lower(), b.lower()
    if a_low == b_low:
        return False

    name_a = a_low.split("|")[0].split("\n")[0].strip()
    name_b = b_low.split("|")[0].split("\n")[0].strip()

    stopwords = {
        "sdn", "bhd", "pte", "ltd", "limited", "llc", "fze", "fzc", "gmbh", "co", "corp", "inc",
    }

    tokens_a = [w.strip("(),.;") for w in name_a.split() if w.strip("(),.;")]
    tokens_b = [w.strip("(),.;") for w in name_b.split() if w.strip("(),.;")]

    meaningful_a = [w for w in tokens_a if w not in stopwords]
    meaningful_b = [w for w in tokens_b if w not in stopwords]

    set_a = set(meaningful_a)
    set_b = set(meaningful_b)

    if not set_a or not set_b:
        return True

    if meaningful_a == meaningful_b:
        return True

    if len(meaningful_a) == len(meaningful_b) and len(meaningful_a) > 0:
        abbrev_diffs = 0
        for w1, w2 in zip(meaningful_a, meaningful_b):
            if w1 != w2:
                if (
                    w1.startswith(w2)
                    or w2.startswith(w1)
                    or (w1 == "intl" and w2 == "international")
                    or (w2 == "intl" and w1 == "international")
                ):
                    abbrev_diffs += 1
                else:
                    abbrev_diffs = 99
        if abbrev_diffs == 1:
            return True

    if " ".join(meaningful_a) == " ".join(meaningful_b[: len(meaningful_a)]) or " ".join(
        meaningful_b
    ) == " ".join(meaningful_a[: len(meaningful_b)]):
        if abs(len(meaningful_a) - len(meaningful_b)) == 1 and (
            "sdn" in tokens_a
            or "sdn" in tokens_b
            or "limited" in tokens_a
            or "limited" in tokens_b
        ):
            return True

    if (
        len(meaningful_a) >= 2
        and len(meaningful_b) >= 2
        and meaningful_a[0] == meaningful_b[0]
        and abs(len(meaningful_a) - len(meaningful_b)) <= 1
        and len(meaningful_a) <= 4
        and len(meaningful_b) <= 4
    ):
        if meaningful_a[:2] == meaningful_b[:2] or (
            meaningful_a[0] == meaningful_b[0]
            and len(meaningful_a) == 2
            and len(meaningful_b) == 2
        ):
            return True

    return False


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


_ENTITY_DELIMITER_PUNCTUATION = re.compile(r"[\s\|\;\,\.]+")


def _normalize_entity(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = _ENTITY_ABBREVIATION_PERIOD.sub("", value)
    cleaned = re.sub(r"[\s\|\;\,]+", " ", cleaned)
    normalized = l0_normalize(cleaned)
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
