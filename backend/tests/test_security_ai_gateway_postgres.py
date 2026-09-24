from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

from backend.app.storage.database import Base
from scripts.database_isolation import database_identity, resolved_urls


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.req("SEC-04")
def test_security_migration_redacts_legacy_ai_payloads():
    test_url = os.environ.get("HOLYSHIP_TEST_DATABASE_URL")
    if not test_url:
        pytest.skip("HOLYSHIP_TEST_DATABASE_URL is required")

    dev_url, configured_test_url = resolved_urls()
    assert database_identity(test_url) == database_identity(configured_test_url)
    assert database_identity(test_url) != database_identity(dev_url)

    engine = create_engine(test_url)
    environment = os.environ | {"DATABASE_URL": test_url}
    email_id = uuid4()
    review_id = uuid4()
    event_id = uuid4()
    resolution_id = uuid4()
    now = datetime.now(timezone.utc)
    raw_question = "Why is customer@example.com shipment blocked?"
    raw_evidence = "Port of Loading: Port Klang"

    try:
        with engine.begin() as connection:
            connection.execute(text("DROP SCHEMA public CASCADE"))
            connection.execute(text("CREATE SCHEMA public"))

        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "20260921_0015"],
            cwd=ROOT,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )

        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO email_messages "
                    "(id, external_message_id, source_type, sender, recipients, subject, body, "
                    "received_at, source_metadata, content_hash, processing_status, created_at, updated_at) "
                    "VALUES (:id, 'security-migration-email', 'INCOMING_API', NULL, CAST('[]' AS jsonb), "
                    "'Security migration', '', NULL, CAST('{}' AS jsonb), :hash, 'BLOCKED', :now, :now)"
                ),
                {"id": email_id, "hash": "e" * 64, "now": now},
            )
            connection.execute(
                text(
                    "INSERT INTO human_review_cases "
                    "(id, email_id, document_id, source_comparison_id, field_name, reason_code, reason_text, "
                    "candidate_scores, evidence, confidence, status, case_origin, workflow_identity, "
                    "reviewer_name, resolution, notes, resolved_at, created_at, updated_at) "
                    "VALUES (:id, :email_id, NULL, NULL, NULL, 'COMPARISON_UNRESOLVED', 'Needs review', "
                    "CAST('{}' AS jsonb), CAST('{}' AS jsonb), NULL, 'OPEN', 'ACTIVE', :identity, "
                    "NULL, NULL, NULL, NULL, :now, :now)"
                ),
                {
                    "id": review_id,
                    "email_id": email_id,
                    "identity": f"security:{review_id}",
                    "now": now,
                },
            )
            connection.execute(
                text(
                    "INSERT INTO human_review_events "
                    "(id, review_case_id, action, actor_name, details, created_at) "
                    "VALUES (:id, :review_id, 'AI_ASSISTANT_ASKED', NULL, "
                    "CAST(:details AS jsonb), :now)"
                ),
                {
                    "id": event_id,
                    "review_id": review_id,
                    "details": (
                        '{"question": "Why is customer@example.com shipment blocked?", '
                        '"provider_name": "gemini"}'
                    ),
                    "now": now,
                },
            )
            connection.execute(
                text(
                    "INSERT INTO ai_resolutions "
                    "(id, request_hash, purpose, case_id, field_name, source_identity, provider_name, "
                    "model_name, resolver_version, prompt_schema_version, request_json, response_json, "
                    "accepted, confidence, validation_reason, provider_calls, created_at, updated_at) "
                    "VALUES (:id, :request_hash, 'EXTRACTION', 'case-legacy', 'port_of_loading', "
                    "'sha256:abc|SI|doc-1', 'gemini', 'gemini-2.5-flash', 'resolver-v1', 'schema-v1', "
                    "CAST(:request_json AS jsonb), CAST(:response_json AS jsonb), true, 0.97, "
                    "'AI_RESOLUTION_ACCEPTED', 1, :now, :now)"
                ),
                {
                    "id": resolution_id,
                    "request_hash": "a" * 64,
                    "request_json": (
                        '{"case_id":"case-legacy","field":"port_of_loading",'
                        '"document_role":"SI","document_id":"doc-1",'
                        '"content_identity":"sha256:abc","evidence":"Port of Loading: Port Klang",'
                        '"deterministic_candidates":[],"escalation_reason":"UNRESOLVED_EXTRACTION"}'
                    ),
                    "response_json": (
                        '{"value":"Port Klang","normalized_value":"PORT KLANG",'
                        '"equivalent":null,"evidence":{"provider_evidence":"Port of Loading: Port Klang"}}'
                    ),
                    "now": now,
                },
            )

        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=ROOT,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )

        with engine.connect() as connection:
            request_json = connection.execute(
                text("SELECT request_json FROM ai_resolutions WHERE id=:id"),
                {"id": resolution_id},
            ).scalar_one()
            event_details = connection.execute(
                text("SELECT details FROM human_review_events WHERE id=:id"),
                {"id": event_id},
            ).scalar_one()

        assert request_json["legacy_payload_redacted"] is True
        assert request_json["field"] == "port_of_loading"
        assert "evidence" not in request_json
        assert raw_evidence not in str(request_json)
        assert request_json["disclosed_fields"] == ["port_of_loading"]

        assert event_details["legacy_question_redacted"] is True
        assert event_details["question_length"] == len(raw_question)
        assert "question" not in event_details
        assert raw_question not in str(event_details)
    finally:
        Base.metadata.drop_all(engine)
        with engine.begin() as connection:
            connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
        engine.dispose()
