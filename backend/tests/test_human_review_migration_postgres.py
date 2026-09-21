from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect, text

from backend.app.storage.database import Base
from scripts.database_isolation import database_identity, resolved_urls


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.req("HR-09")
def test_legacy_review_row_survives_0012_to_0013_migration():
    test_url = os.environ.get("HOLYSHIP_TEST_DATABASE_URL")
    if not test_url:
        pytest.skip("HOLYSHIP_TEST_DATABASE_URL is required")
    dev_url, configured_test_url = resolved_urls()
    assert database_identity(test_url) == database_identity(configured_test_url)
    assert database_identity(test_url) != database_identity(dev_url)

    engine = create_engine(test_url)
    environment = os.environ | {"DATABASE_URL": test_url}
    email_id = uuid4()
    case_id = uuid4()
    now = datetime.now(timezone.utc)
    try:
        with engine.begin() as connection:
            connection.execute(text("DROP SCHEMA public CASCADE"))
            connection.execute(text("CREATE SCHEMA public"))
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "20260920_0012"],
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
                    "VALUES (:id, 'legacy-review-email', 'INCOMING_API', NULL, CAST('[]' AS jsonb), "
                    "'Legacy review', '', NULL, CAST('{}' AS jsonb), :hash, 'BLOCKED', :now, :now)"
                ),
                {"id": email_id, "hash": "f" * 64, "now": now},
            )
            connection.execute(
                text(
                    "INSERT INTO human_review_cases "
                    "(id, email_id, document_id, field_name, reason_code, reason_text, "
                    "candidate_scores, evidence, confidence, status, created_at) "
                    "VALUES (:id, :email_id, NULL, NULL, 'LEGACY_REASON', 'Historical case', "
                    "CAST('{}' AS jsonb), CAST('{}' AS jsonb), NULL, 'OPEN', :now)"
                ),
                {"id": case_id, "email_id": email_id, "now": now},
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
            row = connection.execute(
                text(
                    "SELECT id, status, case_origin, workflow_identity, updated_at "
                    "FROM human_review_cases WHERE id=:id"
                ),
                {"id": case_id},
            ).one()
            assert row.id == case_id
            assert row.status == "OPEN"
            assert row.case_origin == "LEGACY"
            assert row.workflow_identity == f"legacy:{case_id}"
            assert row.updated_at is not None
            assert {"human_review_field_overrides", "human_review_events"} <= set(inspect(connection).get_table_names())
    finally:
        Base.metadata.drop_all(engine)
        with engine.begin() as connection:
            connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
        engine.dispose()
