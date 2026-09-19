from backend.app.storage.database import Base
from backend.app.storage import models  # noqa: F401


def test_batch2_database_metadata_contains_required_document_tables():
    table_names = set(Base.metadata.tables)

    assert {
        "documents",
        "document_extractions",
        "extracted_fields",
    }.issubset(table_names)


def test_documents_table_has_foreign_keys_and_indexes():
    table = Base.metadata.tables["documents"]
    col_names = {c.name for c in table.columns}
    assert {"id", "email_id", "attachment_id", "document_type", "format", "filename", "source_reference"}.issubset(col_names)

    index_cols = {col.name for idx in table.indexes for col in idx.columns}
    assert "email_id" in index_cols
    assert "document_type" in index_cols


def test_document_extractions_table_has_fields():
    table = Base.metadata.tables["document_extractions"]
    col_names = {c.name for c in table.columns}
    assert {"id", "document_id", "reader_used", "extraction_status", "raw_text", "pages_count", "metadata_json"}.issubset(col_names)


def test_extracted_fields_table_has_fields_and_indexes():
    table = Base.metadata.tables["extracted_fields"]
    col_names = {c.name for c in table.columns}
    assert {"id", "extraction_id", "field_name", "raw_value", "status", "confidence", "evidence", "extraction_method"}.issubset(col_names)

    index_cols = {col.name for idx in table.indexes for col in idx.columns}
    assert "extraction_id" in index_cols
    assert "field_name" in index_cols


def test_human_review_cases_has_document_and_field_columns():
    table = Base.metadata.tables["human_review_cases"]
    col_names = {c.name for c in table.columns}
    assert "document_id" in col_names
    assert "field_name" in col_names
