from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from backend.app.ingestion.polling import SqlAlchemyPollingStateStore
from backend.app.storage.database import Base
from backend.app.storage.models import IngestionCheckpointRecord


pytestmark = pytest.mark.skipif(
    not os.environ.get("HOLYSHIP_TEST_DATABASE_URL"),
    reason="HOLYSHIP_TEST_DATABASE_URL is required",
)


@pytest.fixture()
def db_factory():
    engine = create_engine(os.environ["HOLYSHIP_TEST_DATABASE_URL"], pool_pre_ping=True)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.mark.req("ING-08")
def test_checkpoint_survives_worker_restart(db_factory):
    with db_factory() as session:
        SqlAlchemyPollingStateStore(session).record_success(
            source_key="STATIC_BUNDLE:/demo/bundle",
            source_type="STATIC_BUNDLE",
            last_seen_external_id="email_003",
            last_seen_content_hash="c" * 64,
        )

    with db_factory() as session:
        checkpoint = session.scalar(
            select(IngestionCheckpointRecord).where(
                IngestionCheckpointRecord.source_key == "STATIC_BUNDLE:/demo/bundle"
            )
        )
        assert checkpoint is not None
        assert checkpoint.poll_count == 1
        assert checkpoint.last_seen_external_id == "email_003"
        assert checkpoint.last_seen_content_hash == "c" * 64
