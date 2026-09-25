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
from pydantic import SecretStr

from backend.app.main import app
from backend.app.api.deps import get_settings_dep
from backend.app.api.product_schemas import ProductEmailDetail, ProductEmailSummary
from backend.app.core.config import Settings
from backend.app.storage.models import EmailMessageRecord
from backend.app.sync.service import EmailSyncOutcome, SyncReport
from backend.app.reply.policy import ReplyPolicy


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


def test_graph_webhook_validation_and_notifications_only_wake_delta_sync(client):
    tc, _ = client
    runtime = MagicMock()
    runtime.validate_client_state.side_effect = lambda value: value == "expected-state"
    tc.app.state.graph_sync_runtime = runtime

    validation = tc.post("/api/v1/graph/notifications?validationToken=opaque-token")
    assert validation.status_code == 200
    assert validation.text == "opaque-token"

    notification = tc.post("/api/v1/graph/notifications", json={"value": [
        {"subscriptionId": "sub-1", "clientState": "expected-state", "sequenceNumber": "2"},
        {"subscriptionId": "sub-1", "clientState": "expected-state", "sequenceNumber": "1"},
        {"subscriptionId": "sub-1", "clientState": "expected-state", "sequenceNumber": "2"},
    ]})
    assert notification.status_code == 202
    assert notification.json()["action"] == "DELTA_SYNC_TRIGGERED"
    assert notification.json()["accepted"] == 3
    runtime.wake.assert_called_once_with()

    rejected = tc.post("/api/v1/graph/notifications", json={"value": [
        {"subscriptionId": "sub-1", "clientState": "wrong"},
    ]})
    assert rejected.status_code == 403


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


def test_v1_category_override_keeps_human_choice_when_graph_writeback_fails(client):
    tc, mock_session = client
    email_id = uuid.uuid4()
    record = EmailMessageRecord(
        id=email_id, external_message_id="graph-category-1", source_type="MICROSOFT_GRAPH",
        recipients=[], subject="Draft BL", body="Please compare.", content_hash="abc123",
        processing_status="COMPLETED", source_metadata={},
    )
    record.classification_results = []
    mock_session.get.return_value = record
    settings = Settings(
        _env_file=None, microsoft_graph_enabled=True,
        microsoft_graph_tenant_id="tenant", microsoft_graph_client_id="client",
        microsoft_graph_client_secret=SecretStr("secret"), microsoft_graph_mailbox="ops@example.com",
    )
    app.dependency_overrides[get_settings_dep] = lambda: settings
    from backend.app.ingestion.graph_client import GraphClientError
    with (
        patch("backend.app.api.router.get_email_detail", return_value=_product_detail(email_id, "document_comparison")),
        patch("backend.app.api.router.MicrosoftGraphClient") as graph,
    ):
        graph.return_value.set_categories.side_effect = GraphClientError("provider unavailable")
        response = tc.patch(
            f"/api/v1/emails/{email_id}/category",
            json={"category": "document_comparison", "reviewer_name": "Reviewer"},
        )

    assert response.status_code == 200
    assert any(
        getattr(call.args[0], "reason_code", None) == "MANUAL_CATEGORY_OVERRIDE"
        for call in mock_session.add.call_args_list
    )
    assert record.outlook_sync_error == "provider unavailable"
    graph.return_value.set_categories.assert_called_once_with("graph-category-1", ["document_comparison"])


@pytest.mark.req("OUTLOOK-05")
def test_v1_reply_workflow_records_human_confirmed_send_only_after_graph_success(client):
    tc, mock_session = client
    email_id = uuid.uuid4()
    record = EmailMessageRecord(
        id=email_id,
        external_message_id="msg-001",
        source_type="MICROSOFT_GRAPH",
        sender="shipper@example.com",
        recipients=[],
        subject="Draft BL",
        body="Please confirm.",
        content_hash="abc123",
        processing_status="COMPLETED",
        source_metadata={},
    )
    mock_session.get.return_value = record

    eligible = ReplyPolicy(True, "RESOLUTION_REPLY", "clean", [])
    with patch("backend.app.api.router._reply_policy_for_record", return_value=eligible), patch("backend.app.api.router.MicrosoftGraphClient") as graph:
        resp = tc.post(
            f"/api/v1/emails/{email_id}/reply/send",
            json={"final_message": "Dear Customer, confirmed.", "reviewer_name": "Outlook reviewer", "confirmed": True, "idempotency_key": "reply-test-001"},
        )
        graph.return_value.reply.assert_called_once_with("msg-001", "Dear Customer, confirmed.")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SENT"
    assert data["draft"] == "Dear Customer, confirmed."
    assert record.source_metadata["outlook_workflow"]["status"] == "SENT"
    assert record.source_metadata["outlook_events"][-1]["reason_code"] == "REPLY_SENT_CONFIRMED"


def test_v1_reply_send_requires_confirmation_and_preserves_failed_draft(client):
    tc, mock_session = client
    email_id = uuid.uuid4()
    record = EmailMessageRecord(
        id=email_id, external_message_id="graph-1", source_type="MICROSOFT_GRAPH",
        recipients=[], subject="Draft BL", body="Please confirm.", content_hash="abc123",
        processing_status="COMPLETED", source_metadata={},
    )
    mock_session.get.return_value = record
    eligible = ReplyPolicy(True, "RESOLUTION_REPLY", "clean", [])
    with patch("backend.app.api.router._reply_policy_for_record", return_value=eligible):
        unconfirmed = tc.post(f"/api/v1/emails/{email_id}/reply/send", json={"final_message": "Draft", "confirmed": False, "idempotency_key": "reply-test-002"})
        assert unconfirmed.status_code == 422
        with patch("backend.app.api.router.MicrosoftGraphClient") as graph:
            from backend.app.ingestion.graph_client import GraphClientError
            graph.return_value.reply.side_effect = GraphClientError("timeout")
            failed = tc.post(f"/api/v1/emails/{email_id}/reply/send", json={"final_message": "Draft", "confirmed": True, "idempotency_key": "reply-test-003"})
        assert failed.status_code == 502
        assert record.source_metadata["outlook_workflow"]["status"] == "SEND_FAILED"
        assert record.source_metadata["outlook_workflow"]["draft"] == "Draft"

        with patch("backend.app.api.router.MicrosoftGraphClient") as graph:
            retried = tc.post(f"/api/v1/emails/{email_id}/reply/send", json={"final_message": "Draft", "confirmed": True, "idempotency_key": "reply-test-003"})
            assert retried.status_code == 200
            graph.return_value.reply.assert_called_once_with("graph-1", "Draft")

        with patch("backend.app.api.router.MicrosoftGraphClient") as graph:
            duplicate = tc.post(f"/api/v1/emails/{email_id}/reply/send", json={"final_message": "Draft", "confirmed": True, "idempotency_key": "reply-test-003"})
            assert duplicate.status_code == 200
            graph.return_value.reply.assert_not_called()

        conflicting = tc.post(f"/api/v1/emails/{email_id}/reply/send", json={"final_message": "Draft", "confirmed": True, "idempotency_key": "reply-test-004"})
    assert conflicting.status_code == 409


def test_v1_reply_endpoints_reject_ineligible_case_before_provider_call(client):
    tc, mock_session = client
    email_id = uuid.uuid4()
    record = EmailMessageRecord(id=email_id, external_message_id="graph-blocked", source_type="MICROSOFT_GRAPH", recipients=[], subject="Draft BL", body="", content_hash="blocked", processing_status="BLOCKED", source_metadata={})
    mock_session.get.return_value = record
    blocked = ReplyPolicy(False, None, "latest comparison is unresolved", ["consignee"])
    with patch("backend.app.api.router._reply_policy_for_record", return_value=blocked), patch("backend.app.api.router.MicrosoftGraphClient") as graph:
        generated = tc.post(f"/api/v1/emails/{email_id}/reply/generate", json={"key_points": []})
        sent = tc.post(f"/api/v1/emails/{email_id}/reply/send", json={"final_message": "Draft", "confirmed": True, "idempotency_key": "blocked-send"})
    assert generated.status_code == 409
    assert sent.status_code == 409
    graph.return_value.reply.assert_not_called()


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



@pytest.mark.req("SYNC-06")
@pytest.mark.req("LIFE-07")
def test_v1_sync_status_endpoint(client):
    tc, mock_session = client
    from backend.app.api.product_schemas import ProductSyncStatus
    with patch("backend.app.api.router.get_product_sync_status") as mock_sync_status:
        mock_sync_status.return_value = ProductSyncStatus(
            total_emails=10,
            active_count=8,
            deleted_count=2,
            archived_count=0,
            unread_count=3,
            sync_error_count=0,
            last_outlook_sync_at=None,
        )
        resp = tc.get("/api/v1/sync/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_emails"] == 10
        assert data["active_count"] == 8
        assert data["deleted_count"] == 2
        assert data["unread_count"] == 3


@pytest.mark.req("SYNC-06")
@pytest.mark.req("LIFE-07")
def test_v1_outlook_reconcile_idempotent_delete_avoids_duplicate_audit_events(client):
    tc, mock_session = client
    email_id = uuid.uuid4()
    record = EmailMessageRecord(
        id=email_id,
        external_message_id="msg-del-idem",
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
    record.outlook_categories = []
    record.outlook_archived = False
    mock_session.get.return_value = record

    resp = tc.post(
        "/api/v1/outlook/reconcile",
        json={
            "email_id": str(email_id),
            "lifecycle_status": "DELETED",
            "actor_name": "Outlook sync",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["lifecycle"]["lifecycle_status"] == "DELETED"
    assert data["action"] == "OUTLOOK_LIFECYCLE_RECONCILED"


@pytest.mark.req("SYNC-06")
@pytest.mark.req("LIFE-07")
def test_v1_outlook_reconcile_idempotent_restore_avoids_duplicate_audit_events(client):
    tc, mock_session = client
    email_id = uuid.uuid4()
    record = EmailMessageRecord(
        id=email_id,
        external_message_id="msg-res-idem",
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
    record.outlook_read_state = "READ"
    record.outlook_categories = []
    record.outlook_archived = False
    mock_session.get.return_value = record

    resp = tc.post(
        "/api/v1/outlook/reconcile",
        json={
            "email_id": str(email_id),
            "lifecycle_status": "RESTORED",
            "actor_name": "Outlook sync",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["lifecycle"]["lifecycle_status"] == "ACTIVE"
    assert data["action"] == "OUTLOOK_LIFECYCLE_RECONCILED"
