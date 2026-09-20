"""Run the Phase 7 product-boundary demo against a running HolyShip API.

Usage:
    python scripts/demo_phase7.py

The script only uses supported HTTP endpoints. It uses the public bundle for
existing persisted document scenarios and submits two new messages through the
generic incoming-email endpoint. It does not insert database rows directly.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
BASE_URL = os.environ.get("HOLYSHIP_API_URL", "http://127.0.0.1:8000").rstrip("/")


def request_json(method: str, path: str, payload: dict | None = None) -> object:
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(f"{BASE_URL}{path}", data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError) as exc:
        detail = exc.read().decode("utf-8", errors="replace") if isinstance(exc, HTTPError) else str(exc)
        raise RuntimeError(f"{method} {path} failed: {detail}") from exc


def find_existing_case(*, query: str, predicate) -> dict:
    page = request_json("GET", f"/api/v1/emails?search={query}&limit=20")
    items = page["items"]
    for item in items:
        detail = request_json("GET", f"/api/v1/emails/{item['id']}")
        if predicate(detail):
            return detail
    raise RuntimeError(f"No persisted demo case matched search={query!r}")


def print_case(label: str, detail: dict) -> None:
    comparison = detail.get("comparison") or {}
    print(
        json.dumps(
            {
                "scenario": label,
                "email_id": detail["email"]["id"],
                "external_message_id": detail["email"]["external_message_id"],
                "status": detail["email"]["processing_status"],
                "category": (detail.get("classification") or {}).get("category"),
                "comparison_state": comparison.get("state"),
                "mismatched_fields": comparison.get("mismatched_fields", []),
                "review_count": len(detail.get("review", [])),
            },
            indent=2,
            sort_keys=True,
        )
    )


def main() -> None:
    health = request_json("GET", "/api/health")
    if health.get("ok") is not True:
        raise RuntimeError(f"Unexpected health response: {health}")
    print("health: PASS")

    sync = request_json("POST", "/api/v1/sync/initial", {"source": "static"})
    print(
        f"initial sync: PASS total={sync['total']} ingested={sync['ingested']} "
        f"skipped={sync['skipped']} failed={sync['failed']} job_id={sync['job_id']}"
    )

    queue = request_json("GET", "/api/v1/emails?limit=10")
    print(f"queue: PASS total={queue['total']} returned={len(queue['items'])}")

    normal = find_existing_case(
        query="email_001",
        predicate=lambda item: item["email"]["processing_status"] == "COMPLETED",
    )
    print_case("normal non-review", normal)

    comparison = find_existing_case(
        query="email_001",
        predicate=lambda item: bool(item.get("comparison")),
    )
    print_case("SI vs BL comparison", comparison)
    if len(comparison["comparison"]["fields"]) != 7:
        raise RuntimeError("Comparison demo did not expose all seven canonical fields")

    awaiting_payload = {
        "external_message_id": "phase7-demo-awaiting-documents",
        "sender": "demo@example.com",
        "subject": "Please send draft BL for DEMO-001",
        "body": "Please assist to send the draft BL for DEMO-001 for checking asap.",
    }
    awaiting_result = request_json("POST", "/api/v1/ingestion/email", awaiting_payload)
    awaiting = find_existing_case(
        query="phase7-demo-awaiting-documents",
        predicate=lambda item: item["email"]["external_message_id"] == "phase7-demo-awaiting-documents",
    )
    print_case("new incoming awaiting documents", awaiting)
    if (awaiting.get("classification") or {}).get("comparison_readiness") != "AWAITING_DOCUMENTS":
        raise RuntimeError(f"Expected AWAITING_DOCUMENTS, got {awaiting_result} / {awaiting}")

    spam_result = request_json(
        "POST",
        "/api/v1/ingestion/email",
        {
            "external_message_id": "phase7-demo-spam",
            "sender": "marketing@example.com",
            "subject": "WIN A PRIZE NOW",
            "body": "Click here for an unrelated promotion.",
        },
    )
    spam = find_existing_case(
        query="phase7-demo-spam",
        predicate=lambda item: item["email"]["external_message_id"] == "phase7-demo-spam",
    )
    print_case("new incoming non-comparison", spam)
    if spam["email"]["processing_status"] != "COMPLETED":
        raise RuntimeError(f"Expected completed spam path, got {spam_result} / {spam}")

    events = request_json("GET", "/api/v1/events?limit=25")
    print(f"events: PASS polling_events={len(events)}")
    summary = request_json("GET", "/api/v1/summary")
    print(f"summary: PASS total_emails={summary['total_emails']} needs_review={summary['needs_review_count']}")
    print("demo: PASS")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"demo: FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
