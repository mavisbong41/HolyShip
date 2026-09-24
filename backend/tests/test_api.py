from __future__ import annotations

"""
Batch 1 API tests — no live PostgreSQL required.

Uses FastAPI TestClient with an in-memory override of the DB session
that is backed by a mock SyncService.  The goal is to test routing,
request/response shapes, and that the same classifier is invoked via
POST /api/email/incoming.

Database integration (real PostgreSQL) is covered by test_sync_service.py.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.api.product_schemas import ProductEmailDetail, ProductEmailSummary
from backend.app.storage.models import EmailMessageRecord
from backend.app.sync.service import EmailSyncOutcome, SyncReport


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def client():
    """TestClient with a mocked DB session (no real DB needed)."""
    mock_session = MagicMock()

    # Override the get_session dependency
    from backend.app.api.deps import get_session
    app.dependency_overrides[get_session] = lambda: mock_session
    with TestClient(app) as c:
        yield c, mock_session
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /api/health
# ---------------------------------------------------------------------------

def test_health_returns_ok():
    with TestClient(app) as c:
        resp = c.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


# ---------------------------------------------------------------------------
# POST /api/email/incoming — shape and same classifier
# ---------------------------------------------------------------------------

@pytest.mark.req("SCP-07")
def test_incoming_email_returns_classified_outcome(client):
    tc, mock_session = client

    with patch("backend.app.api.router.SyncService") as MockSvc:
        mock_svc_instance = MagicMock()
        MockSvc.return_value = mock_svc_instance
        mock_svc_instance.sync_one.return_value = EmailSyncOutcome(
            external_message_id="incoming_test",
            status="CLASSIFIED",
        )

        resp = tc.post("/api/email/incoming", json={
            "subject": "TO CONFIRM DOCS",
            "body": "Please compare the attached SI and draft BL.",
            "sender": "ops@example.com",
            "attachments": [
                {"filename": "SI.txt"},
                {"filename": "BL.txt"},
            ],
        })

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "CLASSIFIED"
    assert data["external_message_id"] == "incoming_test"
    # Verify SyncService was instantiated and sync_one was called
    MockSvc.assert_called_once()
    mock_svc_instance.sync_one.assert_called_once()


def test_incoming_email_missing_subject_returns_422(client):
    tc, _ = client
    resp = tc.post("/api/email/incoming", json={"body": "some body"})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/sync
# ---------------------------------------------------------------------------

def test_sync_static_source_returns_report(client):
    tc, mock_session = client

    with patch("backend.app.api.router.SyncService") as MockSvc, \
         patch("backend.app.api.router.StaticBundleSource") as MockSource:

        mock_svc_instance = MagicMock()
        MockSvc.return_value = mock_svc_instance
        mock_svc_instance.sync.return_value = SyncReport(
            total=10, ingested=8, skipped=2,
            classified=7, human_review=1, failed=0,
        )

        resp = tc.post("/api/sync", json={"source": "static"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 10
    assert data["classified"] == 7
    assert data["failed"] == 0
    mock_svc_instance.sync.assert_called_once_with(MockSource.return_value, force=False)


def test_sync_endpoint_propagates_force_true(client):
    tc, mock_session = client

    with patch("backend.app.api.router.SyncService") as MockSvc, \
         patch("backend.app.api.router.StaticBundleSource") as MockSource:

        mock_svc_instance = MagicMock()
        MockSvc.return_value = mock_svc_instance
        mock_svc_instance.sync.return_value = SyncReport(
            total=10, ingested=10, skipped=0,
            classified=9, human_review=1, failed=0,
        )

        resp = tc.post("/api/sync", json={"source": "static", "force": True})

    assert resp.status_code == 200
    mock_svc_instance.sync.assert_called_once_with(MockSource.return_value, force=True)


def test_sync_http_source_requires_url(client):
    tc, _ = client
    resp = tc.post("/api/sync", json={"source": "http"})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/emails
# ---------------------------------------------------------------------------

def test_list_emails_returns_empty_list(client):
    tc, mock_session = client
    mock_session.scalars.return_value.all.return_value = []
    resp = tc.get("/api/emails")
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# GET /api/emails/{id} — 404 when not found
# ---------------------------------------------------------------------------

def test_get_email_not_found(client):
    tc, mock_session = client
    mock_session.get.return_value = None
    resp = tc.get(f"/api/emails/{uuid.uuid4()}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/emails/{id}/classification — 404 when not found
# ---------------------------------------------------------------------------

def test_get_classification_not_found(client):
    tc, mock_session = client
    mock_session.scalar.return_value = None
    resp = tc.get(f"/api/emails/{uuid.uuid4()}/classification")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/human-review
# ---------------------------------------------------------------------------

def test_list_human_review_returns_empty(client):
    tc, mock_session = client
    mock_session.scalars.return_value.all.return_value = []
    resp = tc.get("/api/human-review")
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# GET /api/human-review/{id} — 404 when not found
# ---------------------------------------------------------------------------

def test_get_human_review_not_found(client):
    tc, mock_session = client
    mock_session.get.return_value = None
    resp = tc.get(f"/api/human-review/{uuid.uuid4()}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# CORS headers verification
# ---------------------------------------------------------------------------

def test_cors_allows_onrender_origins():
    with TestClient(app) as c:
        # Preflight OPTIONS request from Render frontend
        resp = c.options(
            "/api/v1/sync/initial",
            headers={
                "Origin": "https://holyship.onrender.com",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == "https://holyship.onrender.com"

        # Local development origin
        resp_dev = c.options(
            "/api/v1/summary",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp_dev.status_code == 200
        assert resp_dev.headers.get("access-control-allow-origin") == "http://localhost:5173"

        # Untrusted origin should not receive Access-Control-Allow-Origin header
        resp_untrusted = c.options(
            "/api/v1/summary",
            headers={
                "Origin": "https://evil-untrusted-site.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp_untrusted.headers.get("access-control-allow-origin") is None


def test_cors_headers_preserved_on_500_error():
    from backend.app.api.deps import get_session
    mock_session = MagicMock()
    app.dependency_overrides[get_session] = lambda: mock_session
    try:
        with TestClient(app, raise_server_exceptions=False) as tc:
            with patch("backend.app.api.router._build_sync_service", side_effect=RuntimeError("Simulated internal explosion")):
                resp = tc.post(
                    "/api/v1/sync/initial",
                    headers={"Origin": "https://holyship.onrender.com"},
                    json={"source": "static"},
                )
                assert resp.status_code == 500
                assert resp.headers.get("access-control-allow-origin") == "https://holyship.onrender.com"
                data = resp.json()
                assert data["detail"] == "Internal Server Error"
                assert "Simulated internal explosion" in data["error"]
    finally:
        app.dependency_overrides.clear()


def _product_detail(email_id: uuid.UUID, category: str | None = "document_comparison") -> ProductEmailDetail:
    now = datetime.now(timezone.utc)
    return ProductEmailDetail(
        email=ProductEmailSummary(
            id=email_id,
            external_message_id="msg-001",
            source_type="simulated_api",
            sender="shipper@example.com",
            subject="Draft BL",
            received_at=now,
            created_at=now,
            processing_status="COMPLETED",
            attachment_count=0,
            category=category,
            classification_confidence=1.0 if category else None,
            comparison_readiness=None,
            comparison_state=None,
            mismatch_count=0,
            unresolved_count=0,
            needs_review=False,
            review_status=None,
            review_reason=None,
        ),
        body="Please confirm.",
        recipients=[],
        content_hash="abc123",
    )


@pytest.mark.req("OUTLOOK-05")
def test_v1_category_override_persists_manual_classification(client):
    tc, mock_session = client
    email_id = uuid.uuid4()
    record = EmailMessageRecord(
        id=email_id,
        external_message_id="msg-001",
        source_type="simulated_api",
        sender="shipper@example.com",
        recipients=[],
        subject="Draft BL",
        body="Please confirm.",
        content_hash="abc123",
        processing_status="COMPLETED",
        source_metadata={},
    )
    record.classification_results = []
    mock_session.get.return_value = record

    with patch("backend.app.api.router.get_email_detail", return_value=_product_detail(email_id, "invoice_query")):
        resp = tc.patch(
            f"/api/v1/emails/{email_id}/category",
            json={
                "category": "invoice_query",
                "reviewer_name": "Outlook reviewer",
                "reason": "Customer is asking about invoice charges.",
            },
        )

    assert resp.status_code == 200
    assert resp.json()["email"]["category"] == "invoice_query"
    assert any(getattr(item, "category", None) == "invoice_query" for item in mock_session.add.call_args_list[0].args)


@pytest.mark.req("OUTLOOK-05")
def test_v1_reply_workflow_records_human_confirmed_send(client):
    tc, mock_session = client
    email_id = uuid.uuid4()
    record = EmailMessageRecord(
        id=email_id,
        external_message_id="msg-001",
        source_type="simulated_api",
        sender="shipper@example.com",
        recipients=[],
        subject="Draft BL",
        body="Please confirm.",
        content_hash="abc123",
        processing_status="COMPLETED",
        source_metadata={},
    )
    mock_session.get.return_value = record

    resp = tc.post(
        f"/api/v1/emails/{email_id}/reply/send",
        json={"final_message": "Dear Customer, confirmed.", "reviewer_name": "Outlook reviewer"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SENT"
    assert data["draft"] == "Dear Customer, confirmed."
    assert record.source_metadata["outlook_workflow"]["status"] == "SENT"
    assert record.source_metadata["outlook_events"][-1]["reason_code"] == "REPLY_SENT_CONFIRMED"


@pytest.mark.req("SYNC-06")
@pytest.mark.req("LIFE-07")
def test_v1_outlook_reconcile_marks_deleted_without_destroying_history(client):
    tc, mock_session = client
    email_id = uuid.uuid4()
    record = EmailMessageRecord(
        id=email_id,
        external_message_id="msg-delete",
        source_type="GRAPH",
        sender="shipper@example.com",
        recipients=[],
        subject="Draft BL",
        body="Please confirm.",
        content_hash="abc123",
        processing_status="COMPLETED",
        source_metadata={},
    )
    record.lifecycle_status = "ACTIVE"
    record.outlook_read_state = "UNKNOWN"
    record.outlook_categories = []
    record.outlook_archived = False
    mock_session.get.return_value = record

    resp = tc.post(
        "/api/v1/outlook/reconcile",
        json={
            "email_id": str(email_id),
            "lifecycle_status": "DELETED",
            "outlook_read_state": "UNREAD",
            "outlook_categories": ["BL_COMPARISON", "Customer"],
            "actor_name": "Outlook sync",
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "OUTLOOK_EMAIL_DELETED"
    assert data["lifecycle"]["lifecycle_status"] == "DELETED"
    assert data["lifecycle"]["outlook_read_state"] == "UNREAD"
    assert data["lifecycle"]["outlook_categories"] == ["BL_COMPARISON", "Customer"]
    assert record.deleted_at is not None
    assert record.source_metadata["outlook_events"][-1]["reason_code"] == "OUTLOOK_EMAIL_DELETED"


@pytest.mark.req("SYNC-06")
@pytest.mark.req("LIFE-07")
def test_v1_outlook_reconcile_restores_same_logical_email(client):
    tc, mock_session = client
    email_id = uuid.uuid4()
    record = EmailMessageRecord(
        id=email_id,
        external_message_id="msg-restore",
        source_type="GRAPH",
        sender="shipper@example.com",
        recipients=[],
        subject="Draft BL",
        body="Please confirm.",
        content_hash="abc123",
        processing_status="COMPLETED",
        source_metadata={},
    )
    record.lifecycle_status = "DELETED"
    record.outlook_read_state = "READ"
    record.outlook_categories = ["BL_COMPARISON"]
    record.outlook_archived = False
    record.outlook_sync_error = "Previous sync failed"
    mock_session.get.return_value = record

    resp = tc.post(
        "/api/v1/outlook/reconcile",
        json={
            "email_id": str(email_id),
            "lifecycle_status": "RESTORED",
            "outlook_read_state": "READ",
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["email_id"] == str(email_id)
    assert data["lifecycle"]["lifecycle_status"] == "ACTIVE"
    assert data["action"] == "OUTLOOK_EMAIL_RESTORED"
    assert record.restored_at is not None
    assert record.outlook_sync_error is None

