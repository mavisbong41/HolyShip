"""Requirement traceability gate for every project phase."""
from __future__ import annotations

import ast
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {"ING-09", "SUB-01", "SEC-01", "SEC-02", "SEC-03", "SCP-03", "SCP-04", "SCP-08"}
PHASE_ORDER = {"0": 0, "1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6A": 6, "6B": 7, "7": 8, "F": 9}
ALLOWED_STATUSES = {"TODO", "PASS", "FAIL", "WAIVED"}
REQUIREMENT_ID = re.compile(r"^[A-Z]{2,4}-\d{2}[a-z]?$")


@dataclass(frozen=True)
class RequirementRow:
    identifier: str
    owner: str
    status: str
    evidence: str


def parse_matrix(matrix: str) -> list[RequirementRow]:
    rows: list[RequirementRow] = []
    seen: set[str] = set()
    for line_number, line in enumerate(matrix.splitlines(), start=1):
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        identifier = cells[0] if cells else ""
        if not REQUIREMENT_ID.fullmatch(identifier):
            continue
        if len(cells) < 7:
            raise ValueError(f"malformed requirement row {identifier} at line {line_number}")
        if identifier in seen:
            raise ValueError(f"duplicate requirement ID {identifier}")
        owner = cells[3]
        status = cells[5]
        if owner not in PHASE_ORDER:
            raise ValueError(f"{identifier}: invalid owner phase {owner}")
        if status not in ALLOWED_STATUSES:
            raise ValueError(f"{identifier}: invalid status {status}")
        seen.add(identifier)
        rows.append(RequirementRow(identifier, owner, status, cells[6]))
    if not rows:
        raise ValueError("requirements matrix contains no requirement rows")
    return rows


def validate_seed_ids(rows: list[RequirementRow], seed_text: str) -> list[str]:
    errors: list[str] = []
    row_ids = {row.identifier for row in rows}
    seed_ids: set[str] = set()
    for raw_seed in seed_text.splitlines():
        seed = raw_seed.strip()
        if not seed:
            continue
        if seed in seed_ids:
            errors.append(f"duplicate frozen seed ID {seed}")
        seed_ids.add(seed)
        if seed not in row_ids:
            errors.append(f"missing frozen seed ID {seed}")
    return errors


def _req_markers_for_test(path: Path, test_name: str) -> set[str] | None:
    module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    base_name = test_name.split("[", 1)[0]
    for node in ast.walk(module):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.name != base_name:
            continue
        markers: set[str] = set()
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call) or not decorator.args:
                continue
            function = decorator.func
            if not (
                isinstance(function, ast.Attribute)
                and function.attr == "req"
                and isinstance(function.value, ast.Attribute)
                and function.value.attr == "mark"
            ):
                continue
            argument = decorator.args[0]
            if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                markers.add(argument.value)
        return markers
    return None


def validate_evidence_references(
    rows: list[RequirementRow], root: Path = ROOT
) -> tuple[list[str], list[str]]:
    test_paths: list[str] = []
    errors: list[str] = []
    for row in rows:
        if row.status != "PASS":
            continue
        if not row.evidence:
            errors.append(f"{row.identifier}: missing evidence")
            continue
        for reference in (part.strip() for part in row.evidence.split(";") if part.strip()):
            path_text, separator, test_name = reference.partition("::")
            path = root / path_text
            if not path.exists():
                errors.append(f"{row.identifier}: missing path {path_text}")
                continue
            if not separator:
                continue
            markers = _req_markers_for_test(path, test_name)
            if markers is None:
                errors.append(f"{row.identifier}: missing test {test_name}")
                continue
            if row.identifier not in markers:
                errors.append(
                    f"{row.identifier}: cited test {test_name} lacks "
                    f"@pytest.mark.req('{row.identifier}')"
                )
            if path_text not in test_paths:
                test_paths.append(path_text)
    return test_paths, errors


def validate_junit_results(junit_path: Path) -> list[str]:
    root = ET.parse(junit_path).getroot()
    errors: list[str] = []
    for testcase in root.iter("testcase"):
        skipped = testcase.find("skipped")
        if skipped is None:
            continue
        identity = f"{testcase.get('classname', '')}::{testcase.get('name', '')}".strip(":")
        reason = skipped.get("message") or (skipped.text or "").strip() or "no reason"
        errors.append(f"required evidence did not execute: {identity} ({reason})")
    return errors


def run_evidence_tests(test_paths: list[str], root: Path = ROOT) -> list[str]:
    if not test_paths:
        return []
    with tempfile.TemporaryDirectory(prefix="holyship-trace-") as temporary:
        junit_path = Path(temporary) / "pytest.xml"
        command = [
            sys.executable,
            str(root / "scripts" / "run_tests.py"),
            *test_paths,
            "-q",
            f"--junitxml={junit_path}",
        ]
        completed = subprocess.run(command, cwd=root, check=False)
        errors = [] if completed.returncode == 0 else [
            f"required evidence pytest exited with status {completed.returncode}"
        ]
        if not junit_path.exists():
            return errors + ["required evidence pytest did not produce JUnit results"]
        return errors + validate_junit_results(junit_path)


def main() -> None:
    rows = parse_matrix((ROOT / "docs" / "requirements_matrix.md").read_text(encoding="utf-8"))
    phase_name = sys.argv[1].upper() if len(sys.argv) > 1 and sys.argv[1] else "0"
    if phase_name not in PHASE_ORDER:
        raise SystemExit(f"Unknown phase {phase_name!r}; expected one of {', '.join(PHASE_ORDER)}")
    selected = [row for row in rows if PHASE_ORDER[row.owner] <= PHASE_ORDER[phase_name]]

    errors = validate_seed_ids(
        rows,
        (ROOT / "docs" / "requirements_seed_ids.txt").read_text(encoding="utf-8"),
    )
    missing_required = sorted(REQUIRED - {row.identifier for row in rows})
    errors.extend(f"missing required Phase 0 row {identifier}" for identifier in missing_required)
    test_paths, evidence_errors = validate_evidence_references(selected)
    errors.extend(evidence_errors)

    todo = [row.identifier for row in selected if row.status == "TODO"]
    failed = [row.identifier for row in selected if row.status == "FAIL"]
    counts = {
        "PASS": sum(row.status == "PASS" for row in selected),
        "TODO": len(todo),
        "FAIL": len(failed),
        "WAIVED": sum(row.status == "WAIVED" for row in selected),
    }
    if not errors:
        errors.extend(run_evidence_tests(test_paths))
    if todo or failed or errors:
        raise SystemExit(
            f"Phase {phase_name} traceability failed: counts={counts}, TODO={todo}, "
            f"FAIL={failed}, evidence_errors={errors}"
        )
    print(f"Phase {phase_name} traceability: PASS {counts}; evidence files executed={len(test_paths)}")


if __name__ == "__main__":
    main()
