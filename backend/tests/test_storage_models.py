from backend.app.storage.database import Base
from backend.app.storage import models  # noqa: F401
from backend.app.storage.repositories import DocumentRepository


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


def test_phase5_persistence_identities_are_database_backed():
    expected = {
        "attachments": "uq_attachment_email_source_reference",
        "processing_jobs": "uq_processing_job_email_type_content",
        "classification_results": "uq_classification_email_content_version",
        "documents": "uq_document_attachment_content",
        "extraction_cache": "uq_extraction_cache_content_version",
    }
    for table_name, constraint_name in expected.items():
        table = Base.metadata.tables[table_name]
        assert constraint_name in {constraint.name for constraint in table.constraints}


def test_document_repository_exposes_restart_lookup_on_document_boundary():
    assert callable(getattr(DocumentRepository, "get_by_attachment_content", None))
