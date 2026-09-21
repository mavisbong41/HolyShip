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
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
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

