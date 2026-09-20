from __future__ import annotations

from pathlib import Path

import pytest

from scripts.trace_phase0 import (
    parse_matrix,
    validate_evidence_references,
    validate_junit_results,
    validate_seed_ids,
)


def _row(
    requirement_id: str,
    *,
    status: str = "PASS",
    evidence: str = "backend/tests/test_example.py::test_example",
) -> str:
    return (
        f"| {requirement_id} | requirement | spec | 0 | U | {status} | {evidence} |"
    )


@pytest.mark.req("SCP-06")
def test_trace_matrix_rejects_duplicate_ids_invalid_status_and_malformed_rows() -> None:
    with pytest.raises(ValueError, match="duplicate requirement ID ING-01"):
        parse_matrix("\n".join([_row("ING-01"), _row("ING-01")]))

    with pytest.raises(ValueError, match="invalid status DONE"):
        parse_matrix(_row("ING-01", status="DONE"))

    with pytest.raises(ValueError, match="malformed requirement row"):
        parse_matrix("| ING-01 | requirement | spec | 0 | U | PASS |")


@pytest.mark.req("SCP-06")
def test_trace_matrix_requires_every_frozen_seed_id() -> None:
    rows = parse_matrix(_row("ING-01"))

    assert validate_seed_ids(rows, "ING-01\nING-02\n") == [
        "missing frozen seed ID ING-02"
    ]


@pytest.mark.req("SCP-06")
def test_trace_marker_must_be_on_the_cited_test_function(tmp_path: Path) -> None:
    test_path = tmp_path / "backend" / "tests" / "test_example.py"
    test_path.parent.mkdir(parents=True)
    test_path.write_text(
        """import pytest

@pytest.mark.req(\"ING-01\")
def test_other():
    pass

def test_example():
    pass
""",
        encoding="utf-8",
    )
    rows = parse_matrix(_row("ING-01"))

    _, errors = validate_evidence_references(rows, tmp_path)

    assert errors == [
        "ING-01: cited test test_example lacks @pytest.mark.req('ING-01')"
    ]


@pytest.mark.req("SCP-06")
def test_trace_rejects_skipped_or_xfailed_required_evidence(tmp_path: Path) -> None:
    junit = tmp_path / "results.xml"
    junit.write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<testsuites tests="2" failures="0" errors="0" skipped="2">
  <testsuite name="pytest" tests="2" failures="0" errors="0" skipped="2">
    <testcase classname="test_example" name="test_skipped"><skipped type="pytest.skip" message="required service missing" /></testcase>
    <testcase classname="test_example" name="test_xfailed"><skipped type="pytest.xfail" message="known defect" /></testcase>
  </testsuite>
</testsuites>
""",
        encoding="utf-8",
    )

    errors = validate_junit_results(junit)

    assert errors == [
        "required evidence did not execute: test_example::test_skipped (required service missing)",
        "required evidence did not execute: test_example::test_xfailed (known defect)",
    ]
