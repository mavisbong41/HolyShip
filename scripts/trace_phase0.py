"""Small Phase-0 traceability gate for the frozen requirement IDs."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {"ING-09", "SUB-01", "SEC-01", "SEC-02", "SEC-03", "SCP-03", "SCP-04", "SCP-08"}


def main() -> None:
    matrix = (ROOT / "docs" / "requirements_matrix.md").read_text(encoding="utf-8")
    missing = [identifier for identifier in REQUIRED if f"| {identifier} " not in matrix or " PASS " not in next(line for line in matrix.splitlines() if f"| {identifier} " in line)]
    artifacts = [ROOT / "reports" / "leakage_audit.md", ROOT / "implement.md"]
    if missing or not all(path.exists() for path in artifacts):
        raise SystemExit(f"Phase 0 traceability failed: missing={missing}, artifacts={[str(path) for path in artifacts if not path.exists()]}")
    phase = sys.argv[1] if len(sys.argv) > 1 else "0"
    if phase != "0":
        outstanding = [line.split("|")[1].strip() for line in matrix.splitlines() if "| 1  |" in line and " TODO " in line]
        if outstanding:
            raise SystemExit(f"Phase {phase} traceability failed: Phase-1 rows remain TODO: {outstanding}")
    print("Phase 0 traceability: PASS")


if __name__ == "__main__":
    main()
