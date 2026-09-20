"""Submit the completed public submission once and persist the aggregate response."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "data" / "bundle"))
from loader import Inbox  # noqa: E402


def main() -> None:
    submission = json.loads((ROOT / "reports" / "latest" / "submission.json").read_text(encoding="utf-8"))
    latest = ROOT / "reports" / "latest"
    latest.mkdir(parents=True, exist_ok=True)
    try:
        response = Inbox("http://localhost:8080").submit(submission)
    except Exception as exc:
        with (ROOT / "reports" / "score_history.jsonl").open("a", encoding="utf-8") as history:
            history.write(json.dumps({"timestamp": datetime.now(timezone.utc).isoformat(), "result": "unavailable", "error": str(exc)}, sort_keys=True) + "\n")
        raise
    (latest / "scoreboard.json").write_text(json.dumps(response, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with (ROOT / "reports" / "score_history.jsonl").open("a", encoding="utf-8") as history:
        history.write(json.dumps({"timestamp": datetime.now(timezone.utc).isoformat(), "result": "ok", "response": response}, sort_keys=True) + "\n")
    print(json.dumps(response, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
