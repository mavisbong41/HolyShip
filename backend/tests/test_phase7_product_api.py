from __future__ import annotations

import uuid
import subprocess
import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.sync.service import EmailSyncOutcome, SyncReport


@pytest.mark.req("API-07")
def test_product_field_contract_preserves_seven_fields_and_three_states():
    from backend.app.api.product_schemas import (
        PRODUCT_CANONICAL_FIELDS,
        ProductFieldComparison,
    )

    assert PRODUCT_CANONICAL_FIELDS == (
        "shipper",
        "consignee",
        "notify_party",
        "port_of_loading",
        "port_of_discharge",
        "container_count",
        "gross_weight_kg",
    )

    field = ProductFieldComparison(
        field="gross_weight_kg",
        si={"raw": "22,000 KG", "canonical": 22000, "normalized": 22000},
        bl={"raw": "22000 kg", "canonical": 22000, "normalized": 22000},
        status="MATCH",
        reason_code="L1_NUMERIC_EQUAL",
        evidence=[],
    )
    assert field.status == "MATCH"
    assert field.si.raw == "22,000 KG"
    assert field.bl.normalized == 22000


def test_product_pagination_validation_rejects_negative_and_oversized_values():
    from backend.app.api.product_queries import validate_page

    with pytest.raises(ValueError):
        validate_page(skip=-1, limit=25)
    with pytest.raises(ValueError):
        validate_page(skip=0, limit=0)
    with pytest.raises(ValueError):
        validate_page(skip=0, limit=501)


@pytest.mark.req("API-01")
def test_v1_queue_returns_explicit_page_contract_and_filter_values():
    from backend.app.api.product_schemas import EmailQueuePage

    page = EmailQueuePage(
        items=[],
        total=0,
        skip=0,
        limit=25,
    )
    mock_session = MagicMock()
    from backend.app.api.deps import get_session

    app.dependency_overrides[get_session] = lambda: mock_session
    try:
        with patch("backend.app.api.router.list_email_queue", return_value=page) as list_queue:
            with TestClient(app) as client:
                response = client.get(
                    "/api/v1/emails?status=COMPLETED&category=document_comparison&has_mismatch=true&limit=25"
                )
        assert response.status_code == 200
        assert response.json() == {"items": [], "total": 0, "skip": 0, "limit": 25}
        list_queue.assert_called_once()
        assert list_queue.call_args.kwargs["status"] == "COMPLETED"
        assert list_queue.call_args.kwargs["category"] == "document_comparison"
        assert list_queue.call_args.kwargs["has_mismatch"] is True
    finally:
        app.dependency_overrides.clear()


@pytest.mark.req("API-01")
def test_v1_queue_rejects_invalid_filters_and_pagination():
    with TestClient(app) as client:
        assert client.get("/api/v1/emails?skip=-1").status_code == 422
        assert client.get("/api/v1/emails?limit=501").status_code == 422
        assert client.get("/api/v1/emails?status=not-a-status").status_code == 422
        assert client.get("/api/v1/emails?category=not-a-category").status_code == 422


@pytest.mark.req("API-02")
def test_v1_unknown_email_detail_returns_404():
    mock_session = MagicMock()
    mock_session.scalar.return_value = None
    from backend.app.api.deps import get_session

    app.dependency_overrides[get_session] = lambda: mock_session
    try:
        with TestClient(app) as client:
            response = client.get(f"/api/v1/emails/{uuid.uuid4()}")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


@pytest.mark.req("API-02")
def test_product_get_routes_do_not_construct_processing_services():
    mock_session = MagicMock()
    from backend.app.api.deps import get_session
    from backend.app.api.product_schemas import EmailQueuePage, ProductSummary

    app.dependency_overrides[get_session] = lambda: mock_session
    try:
        with patch("backend.app.api.router._build_sync_service", side_effect=AssertionError("GET invoked processing")):
            with patch(
                "backend.app.api.router.list_email_queue",
                return_value=EmailQueuePage(items=[], total=0, skip=0, limit=10),
            ):
                with patch(
                    "backend.app.api.router.get_product_summary",
                    return_value=ProductSummary(
                        total_emails=0,
                        status_counts={},
                        needs_review_count=0,
                        comparison_ready_count=0,
                        mismatch_count=0,
                        unresolved_count=0,
                    ),
                ):
                    with patch("backend.app.api.router.get_email_detail", return_value=None):
                        with patch("backend.app.api.router.list_processing_events", return_value=[]):
                            with TestClient(app) as client:
                                assert client.get("/api/v1/emails?limit=10").status_code == 200
                                assert client.get("/api/v1/summary").status_code == 200
                                assert client.get(f"/api/v1/emails/{uuid.uuid4()}").status_code == 404
                                assert client.get("/api/v1/events?limit=10").status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_product_detail_preserves_unresolved_and_blocked_semantics():
    from backend.app.api.product_schemas import ProductComparison

    comparison = ProductComparison(
        state="BLOCKED",
        mismatch_found=False,
        mismatched_fields=[],
        unresolved_fields=["gross_weight_kg"],
        reason_code="COMPARISON_UNRESOLVED",
        message="Comparison unresolved.",
        fields=[],
    )
    assert comparison.state == "BLOCKED"
    assert comparison.mismatch_found is False
    assert comparison.unresolved_fields == ["gross_weight_kg"]


@pytest.mark.req("API-06")
@pytest.mark.req("ING-05")
def test_v1_events_contract_is_polling_compatible():
    mock_session = MagicMock()
    from backend.app.api.deps import get_session

    app.dependency_overrides[get_session] = lambda: mock_session
    try:
        with patch("backend.app.api.router.list_processing_events", return_value=[]):
            with TestClient(app) as client:
                response = client.get("/api/v1/events?limit=10")
        assert response.status_code == 200
        assert response.json() == []
    finally:
        app.dependency_overrides.clear()


@pytest.mark.req("ING-04")
def test_demo_script_can_import_backend_from_script_execution_context():
    root = Path(__file__).resolve().parents[2]
    probe = (
        "import runpy, sys; "
        "sys.path.pop(0); sys.path.insert(0, 'scripts'); "
        "namespace = runpy.run_path('scripts/demo_phase7.py', run_name='demo_probe'); "
        "namespace['find_scanned_pair']()"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=root,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout


@pytest.mark.req("ING-01")
@pytest.mark.req("ING-03")
@pytest.mark.req("ING-04")
@pytest.mark.req("API-03")
@pytest.mark.req("API-04")
@pytest.mark.req("ING-10")
def test_v1_initial_sync_and_incoming_aliases_reuse_existing_pipeline():
    mock_session = MagicMock()
    from backend.app.api.deps import get_session

    app.dependency_overrides[get_session] = lambda: mock_session
    try:
        with patch("backend.app.api.router.SyncService") as sync_service:
            worker = MagicMock()
            sync_service.return_value = worker
            worker.sync.return_value = SyncReport(total=2, ingested=2, classified=2)
            worker.sync_one.return_value = EmailSyncOutcome(
                external_message_id="phase7-incoming",
                status="CLASSIFIED",
            )
            with TestClient(app) as client:
                initial = client.post("/api/v1/sync/initial", json={"source": "static"})
                incoming = client.post(
                    "/api/v1/ingestion/email",
                    json={"external_message_id": "phase7-incoming", "subject": "Hello"},
                )
        assert initial.status_code == 200
        assert initial.json()["status"] == "COMPLETED"
        assert initial.json()["total"] == 2
        assert initial.json()["progress"] == {
            "total": 2,
            "processed": 2,
            "percent": 100.0,
            "ingested": 2,
            "skipped": 0,
            "failed": 0,
        }
        assert incoming.status_code == 200
        assert incoming.json()["status"] == "CLASSIFIED"
        assert sync_service.call_count == 2
        incoming_source = sync_service.return_value.sync_one.call_args.args[1]
        assert incoming_source.source_type == "INCOMING_API"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.req("API-04")
def test_v1_incoming_attachment_content_is_decoded_for_the_shared_pipeline():
    mock_session = MagicMock()
    from backend.app.api.deps import get_session

    app.dependency_overrides[get_session] = lambda: mock_session
    try:
        with patch("backend.app.api.router.SyncService") as sync_service:
            sync_service.return_value.sync_one.return_value = EmailSyncOutcome(
                external_message_id="phase7-content",
                status="CLASSIFIED",
            )
            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/ingestion/email",
                    json={
                        "external_message_id": "phase7-content",
                        "subject": "Document",
                        "attachments": [
                            {
                                "filename": "doc.txt",
                                "content_base64": "U0k6IHRlc3Q=",
                            }
                        ],
                    },
                )
        assert response.status_code == 200
        source = sync_service.return_value.sync_one.call_args.args[1]
        attachment = source.payloads[0].attachments[0]
        assert source.get_attachment_content(attachment) == b"SI: test"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.req("API-04")
def test_v1_incoming_attachment_rejects_invalid_base64():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/ingestion/email",
            json={
                "external_message_id": "phase7-invalid-content",
                "subject": "Document",
                "attachments": [{"filename": "doc.txt", "content_base64": "%%%"}],
            },
        )
    assert response.status_code == 422


@pytest.mark.req("SEC-04")
@pytest.mark.req("API-04")
def test_v1_incoming_attachment_rejects_content_above_configured_limit():
    from backend.app.api.deps import get_settings_dep
    from backend.app.core.config import Settings

    app.dependency_overrides[get_settings_dep] = lambda: Settings(max_attachment_bytes=4)
    try:
        with patch("backend.app.api.router.SyncService") as sync_service:
            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/ingestion/email",
                    json={
                        "external_message_id": "phasef-oversized-content",
                        "subject": "Document",
                        "attachments": [
                            {
                                "filename": "doc.txt",
                                "content_base64": "MTIzNDU=",
                            }
                        ],
                    },
                )
        assert response.status_code == 413
        assert response.json()["detail"] == "Attachment content exceeds the configured 4-byte limit"
        sync_service.assert_not_called()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.req("API-05")
def test_v1_reprocess_rejects_non_failed_email_with_409():
    mock_session = MagicMock()
    record = MagicMock(processing_status="COMPLETED")
    mock_session.get.return_value = record
    from backend.app.api.deps import get_session

    app.dependency_overrides[get_session] = lambda: mock_session
    try:
        with TestClient(app) as client:
            response = client.post(f"/api/v1/emails/{uuid.uuid4()}/reprocess")
        assert response.status_code == 409
    finally:
        app.dependency_overrides.clear()


@pytest.mark.req("API-05")
def test_v1_reprocess_forces_the_existing_pipeline_for_failed_email():
    mock_session = MagicMock()
    record = MagicMock(
        id=uuid.uuid4(),
        external_message_id="failed-email",
        processing_status="FAILED",
    )
    mock_session.get.return_value = record
    from backend.app.api.deps import get_session
    from backend.app.ingestion.models import EmailMessage

    message = EmailMessage(
        external_message_id="failed-email",
        source_type="INCOMING_API",
        subject="Retry me",
        body="Please retry",
        content_hash="d" * 64,
    )
    app.dependency_overrides[get_session] = lambda: mock_session
    try:
        with patch("backend.app.api.router._reprocess_source", return_value=(message, MagicMock())):
            with patch("backend.app.api.router.SyncService") as sync_service:
                sync_service.return_value.sync_one.return_value = EmailSyncOutcome(
                    external_message_id="failed-email", status="CLASSIFIED"
                )
                with TestClient(app) as client:
                    response = client.post(f"/api/v1/emails/{record.id}/reprocess")
        assert response.status_code == 200
        assert response.json()["status"] == "CLASSIFIED"
        assert sync_service.return_value.sync_one.call_args.kwargs["force"] is True
    finally:
        app.dependency_overrides.clear()


@pytest.mark.req("API-07")
def test_openapi_lists_product_contract_without_internal_storage_routes():
    with TestClient(app) as client:
        document = client.get("/openapi.json")
    assert document.status_code == 200
    paths = document.json()["paths"]
    assert "/api/v1/emails" in paths
    assert "/api/v1/emails/{email_id}" in paths
    assert "/api/v1/summary" in paths
    assert "/api/v1/events" in paths
    assert "request_json" not in document.text
