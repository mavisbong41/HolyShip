from backend.app.storage.database import Base
from backend.app.storage import models  # noqa: F401


def test_batch1_database_metadata_contains_required_tables():
    table_names = set(Base.metadata.tables)

    assert {
        "email_messages",
        "attachments",
        "processing_jobs",
        "classification_results",
        "human_review_cases",
    }.issubset(table_names)


def test_email_messages_table_has_idempotency_constraint():
    table = Base.metadata.tables["email_messages"]

    constraint_names = {constraint.name for constraint in table.constraints}

    assert "uq_email_source_external_id" in constraint_names
