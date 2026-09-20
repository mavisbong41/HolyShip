"""Run the Phase 7 product-boundary demo against a running HolyShip API."""

from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
BUNDLE_ATTACHMENTS = (ROOT / "data" / "bundle" / "attachments").resolve()
BASE_URL = os.environ.get("HOLYSHIP_API_URL", "http://127.0.0.1:8000").rstrip("/")


def request_json(method: str, path: str, payload: dict | None = None) -> object:
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(f"{BASE_URL}{path}", data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError) as exc:
        detail = exc.read().decode("utf-8", errors="replace") if isinstance(exc, HTTPError) else str(exc)
        raise RuntimeError(f"{method} {path} failed: {detail}") from exc


def bundle_file(filename: str) -> Path:
    path = (BUNDLE_ATTACHMENTS / filename).resolve()
    if not path.is_relative_to(BUNDLE_ATTACHMENTS):
        raise RuntimeError(f"Unsafe demo fixture path: {filename}")
    if not path.is_file():
        raise RuntimeError(f"Missing public demo fixture: {filename}")
    return path


def attachment(filename: str) -> dict[str, str]:
    path = bundle_file(filename)
    return {
        "filename": filename,
        "source_reference": filename,
        "content_type": {
            ".txt": "text/plain",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".pdf": "application/pdf",
        }.get(path.suffix.lower(), "application/octet-stream"),
        "content_base64": base64.b64encode(path.read_bytes()).decode("ascii"),
    }


def find_pair(extension: str) -> tuple[str, str]:
    for si_path in sorted(BUNDLE_ATTACHMENTS.glob(f"*_SI{extension}")):
        bl_path = BUNDLE_ATTACHMENTS / si_path.name.replace("_SI", "_BL")
        if bl_path.is_file():
            return si_path.name, bl_path.name
    raise RuntimeError(f"No public SI/BL pair found for {extension}")


def find_wrong_pair() -> tuple[str, str]:
    si_filename, _ = find_pair(".txt")
    for path in sorted(BUNDLE_ATTACHMENTS.glob("*_BL.txt")):
        if any(marker in path.read_bytes().upper() for marker in (
            b"COMMERCIAL INVOICE",
            b"PACKING LIST",
            b"CERTIFICATE OF ORIGIN",
        )):
            return si_filename, path.name
    raise RuntimeError("No public wrong-document fixture found")


def find_scanned_pair() -> tuple[str, str]:
    from backend.app.documents.readers.pdf_text import PdfTextReader

    reader = PdfTextReader()
    for si_path in sorted(BUNDLE_ATTACHMENTS.glob("*_SI.pdf")):
        bl_path = BUNDLE_ATTACHMENTS / si_path.name.replace("_SI", "_BL")
        if bl_path.is_file() and reader.read(
            si_path.read_bytes(), si_path.name, str(si_path)
        ).metadata.get("is_scanned") is True:
            return si_path.name, bl_path.name
    raise RuntimeError("No public scanned PDF SI/BL pair found")


def find_case(external_id: str) -> dict:
    page = request_json("GET", f"/api/v1/emails?search={quote(external_id)}&limit=20")
    for item in page["items"]:
        if item["external_message_id"] == external_id:
            return request_json("GET", f"/api/v1/emails/{item['id']}")
    raise RuntimeError(f"No persisted case found for {external_id}")


def print_case(label: str, detail: dict) -> None:
    comparison = detail.get("comparison") or {}
    print(json.dumps({
        "scenario": label,
        "email_id": detail["email"]["id"],
        "external_message_id": detail["email"]["external_message_id"],
        "status": detail["email"]["processing_status"],
        "category": (detail.get("classification") or {}).get("category"),
        "comparison_state": comparison.get("state"),
        "mismatched_fields": comparison.get("mismatched_fields", []),
        "document_validation": [item["validation_outcome"] for item in detail.get("documents", [])],
    }, indent=2, sort_keys=True))


def submit_comparison(external_id: str, si_filename: str, bl_filename: str) -> dict:
    result = request_json(
        "POST",
        "/api/v1/ingestion/email",
        {
            "external_message_id": external_id,
            "sender": "demo@example.com",
            "subject": f"Please compare SI and draft BL for {external_id}",
            "body": f"Please compare the attached Shipping Instruction and draft Bill of Lading for {external_id}.",
            "attachments": [attachment(si_filename), attachment(bl_filename)],
        },
    )
    detail = find_case(external_id)
    if (detail.get("classification") or {}).get("category") != "document_comparison":
        raise RuntimeError(f"Expected document_comparison for {external_id}: {result} / {detail}")
    return detail


def check_events(detail: dict) -> None:
    email_id = detail["email"]["id"]
    events = request_json("GET", f"/api/v1/events?email_id={quote(email_id)}&limit=100")
    if not events or any(event["email_id"] != email_id for event in events):
        raise RuntimeError(f"No persisted events for {detail['email']['external_message_id']}")


def main() -> None:
    health = request_json("GET", "/api/health")
    if health.get("ok") is not True:
        raise RuntimeError(f"Unexpected health response: {health}")
    print("health: PASS")

    sync = request_json("POST", "/api/v1/sync/initial", {"source": "static"})
    if sync["progress"]["processed"] != sync["progress"]["total"]:
        raise RuntimeError(f"Initial sync did not finish: {sync}")
    print(f"initial sync: PASS total={sync['total']} processed={sync['progress']['processed']} job_id={sync['job_id']}")

    queue = request_json("GET", "/api/v1/emails?limit=10")
    print(f"queue: PASS total={queue['total']} returned={len(queue['items'])}")

    normal_si, normal_bl = find_pair(".txt")
    normal = submit_comparison("phase-r-demo-text", normal_si, normal_bl)
    print_case("incoming text comparison", normal)
    if normal.get("comparison") is None or len(normal["comparison"]["fields"]) != 7:
        raise RuntimeError("Text comparison did not expose all seven canonical fields")
    check_events(normal)

    xlsx_si, xlsx_bl = find_pair(".xlsx")
    xlsx = submit_comparison("phase-r-demo-xlsx", xlsx_si, xlsx_bl)
    print_case("incoming XLSX comparison", xlsx)
    if xlsx.get("comparison") is None:
        raise RuntimeError("XLSX comparison did not produce a comparison result")
    check_events(xlsx)

    wrong_si, wrong_bl = find_wrong_pair()
    wrong = submit_comparison("phase-r-demo-wrong-document", wrong_si, wrong_bl)
    print_case("incoming wrong document", wrong)
    if wrong["email"]["processing_status"] != "BLOCKED" or "WRONG_DOCUMENT_TYPE" not in {
        item["validation_outcome"] for item in wrong.get("documents", [])
    }:
        raise RuntimeError(f"Wrong-document scenario did not fail closed: {wrong}")
    check_events(wrong)

    scanned_si, scanned_bl = find_scanned_pair()
    scanned = submit_comparison("phase-r-demo-scanned", scanned_si, scanned_bl)
    print_case("incoming scanned PDF", scanned)
    if scanned["email"]["processing_status"] not in {"BLOCKED", "FAILED"}:
        raise RuntimeError(f"Scanned scenario unexpectedly completed: {scanned}")
    if not any(item["format"] == "SCANNED_PDF" for item in scanned.get("documents", [])):
        raise RuntimeError(f"Scanned scenario did not route a scanned PDF: {scanned}")
    check_events(scanned)

    awaiting_payload = {
        "external_message_id": "phase-r-demo-awaiting-documents",
        "sender": "demo@example.com",
        "subject": "Please send draft BL for DEMO-001",
        "body": "Please assist to send the draft BL for DEMO-001 for checking asap.",
    }
    awaiting_result = request_json("POST", "/api/v1/ingestion/email", awaiting_payload)
    awaiting = find_case("phase-r-demo-awaiting-documents")
    print_case("new incoming awaiting documents", awaiting)
    if (awaiting.get("classification") or {}).get("comparison_readiness") != "AWAITING_DOCUMENTS":
        raise RuntimeError(f"Expected AWAITING_DOCUMENTS, got {awaiting_result} / {awaiting}")
    check_events(awaiting)

    spam_result = request_json(
        "POST",
        "/api/v1/ingestion/email",
        {
            "external_message_id": "phase-r-demo-spam",
            "sender": "marketing@example.com",
            "subject": "WIN A PRIZE NOW",
            "body": "Click here for an unrelated promotion.",
        },
    )
    spam = find_case("phase-r-demo-spam")
    print_case("new incoming spam", spam)
    if (spam.get("classification") or {}).get("category") != "spam":
        raise RuntimeError(f"Expected spam classification, got {spam_result} / {spam}")
    if spam["email"]["processing_status"] != "COMPLETED":
        raise RuntimeError(f"Expected completed spam path, got {spam_result} / {spam}")
    check_events(spam)

    events = request_json("GET", "/api/v1/events?limit=100")
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
