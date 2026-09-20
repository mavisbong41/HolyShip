from __future__ import annotations

import io
import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.documents.models import DocumentType
from backend.app.documents.readers.xlsx_reader import XlsxReader
from backend.app.extraction.extractor import DeterministicDocumentExtractor
from backend.app.extraction.models import CanonicalField, MappingMethod
from backend.app.storage.database import Base
from backend.app.storage.models import AttachmentRecord, EmailMessageRecord
from backend.app.storage.repositories import (
    DocumentExtractionRepository,
    DocumentRepository,
    ExtractedFieldRepository,
)


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


def _xlsx_document():
    import openpyxl

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Shipment"
    for row in (
        ("SHIPPING INSTRUCTION", None),
        ("Shipper", "Persisted Shipper Ltd"),
        ("Consignee", "Persisted Consignee Ltd"),
        ("Notify Party", "Persisted Notify Ltd"),
        ("POL", "Port Klang"),
        ("POD", "Singapore"),
        ("Container Count", 6),
        ("Gross Weight", 22000),
    ):
        sheet.append(row)
    payload = io.BytesIO()
    workbook.save(payload)
    document = XlsxReader().read(payload.getvalue(), "persist.xlsx", "memory/persist.xlsx")
    document.document_type = DocumentType.SI
    return document


@pytest.mark.req("EXT-01")
@pytest.mark.req("EXT-04")
@pytest.mark.req("MAP-04")
def test_seven_fields_and_structured_provenance_reload_from_fresh_postgres_session(db_factory):
    result = DeterministicDocumentExtractor().extract(_xlsx_document())

    with db_factory() as session:
        email = EmailMessageRecord(
            external_message_id="phase3-persistence",
            source_type="INCOMING_API",
            sender="sender@example.com",
            recipients=[],
            subject="comparison",
            body="compare",
            source_metadata={},
            content_hash="a" * 64,
            processing_status="EXTRACTING",
        )
        session.add(email)
        session.flush()
        attachment = AttachmentRecord(
            email_id=email.id,
            filename="persist.xlsx",
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            source_reference="memory/persist.xlsx",
            retrieval_status="MATERIALIZED",
        )
        session.add(attachment)
        session.flush()
        document = DocumentRepository(session).create(
            email_id=email.id,
            attachment_id=attachment.id,
            document_type="SI",
            format="XLSX",
            filename="persist.xlsx",
            source_reference="memory/persist.xlsx",
            routing_outcome="SI_FOUND",
            role_confidence=1.0,
            validation_outcome="VALID",
        )
        extraction = DocumentExtractionRepository(session).create(
            document_id=document.id,
            reader_used="XlsxReader",
            extractor_version=result.extractor_version,
            raw_text="materialized",
        )
        ExtractedFieldRepository(session).create_result(extraction.id, result)
        extraction_id = extraction.id
        session.commit()

    with db_factory() as session:
        reloaded = DocumentExtractionRepository(session).get(extraction_id)
        fields = {row.field_name: row for row in reloaded.fields}

        assert set(fields) == {field.value for field in CanonicalField}
        assert len(fields) == 7
        gross = fields[CanonicalField.GROSS_WEIGHT_KG.value]
        assert gross.raw_label == "Gross Weight"
        assert gross.raw_value_json == 22000
        assert gross.canonical_value == 22000
        assert gross.mapping_method == MappingMethod.TABLE_STRUCTURE.value
        assert gross.source_location["table_name"] == "Shipment"
        assert gross.source_location["label_cell"] == "A8"
        assert gross.source_location["value_cell"] == "B8"
        assert gross.status == "RESOLVED"
        assert gross.confidence == 1.0
        assert reloaded.extractor_version == result.extractor_version
