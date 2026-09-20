"""Small Phase-0 traceability gate for the frozen requirement IDs."""
from __future__ import annotations

import sys
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {"ING-09", "SUB-01", "SEC-01", "SEC-02", "SEC-03", "SCP-03", "SCP-04", "SCP-08"}


def main() -> None:
    matrix = (ROOT / "docs" / "requirements_matrix.md").read_text(encoding="utf-8")
    missing = [identifier for identifier in REQUIRED if f"| {identifier} " not in matrix or " PASS " not in next(line for line in matrix.splitlines() if f"| {identifier} " in line)]
    artifacts = [ROOT / "reports" / "leakage_audit.md", ROOT / "implement.md"]
    if missing or not all(path.exists() for path in artifacts):
        raise SystemExit(f"Phase 0 traceability failed: missing={missing}, artifacts={[str(path) for path in artifacts if not path.exists()]}")
    phase = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    rows: list[dict[str, str]] = []
    for line in matrix.splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 7 or not re.fullmatch(r"\d+", cells[3]):
            continue
        owner = int(cells[3])
        if owner <= phase:
            rows.append(
                {
                    "id": cells[0],
                    "owner": cells[3],
                    "status": cells[5],
                    "evidence": cells[6],
                }
            )

    todo = [row["id"] for row in rows if row["status"] == "TODO"]
    failed = [row["id"] for row in rows if row["status"] == "FAIL"]
    evidence_errors: list[str] = []
    for row in rows:
        if row["status"] != "PASS":
            continue
        if not row["evidence"]:
            evidence_errors.append(f"{row['id']}: missing evidence")
            continue
        for reference in (part.strip() for part in row["evidence"].split(";") if part.strip()):
            path_text, separator, test_name = reference.partition("::")
            path = ROOT / path_text
            if not path.exists():
                evidence_errors.append(f"{row['id']}: missing path {path_text}")
                continue
            if separator:
                source = path.read_text(encoding="utf-8")
                if f"def {test_name}" not in source:
                    evidence_errors.append(f"{row['id']}: missing test {test_name}")
                if f'@pytest.mark.req("{row["id"]}")' not in source:
                    evidence_errors.append(f"{row['id']}: missing req marker in {path_text}")

    counts = {
        "PASS": sum(row["status"] == "PASS" for row in rows),
        "TODO": len(todo),
        "FAIL": len(failed),
    }
    if todo or failed or evidence_errors:
        raise SystemExit(
            f"Phase {phase} traceability failed: counts={counts}, TODO={todo}, "
            f"FAIL={failed}, evidence_errors={evidence_errors}"
        )
    print(f"Phase {phase} traceability: PASS {counts}")


if __name__ == "__main__":
    main()
