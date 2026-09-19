import os
from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from backend.app.ingestion.models import IncomingEmailPayload, IncomingAttachmentInput, EmailMessage
from backend.app.ingestion.sources import map_organizer_record, map_incoming_payload
from backend.app.classification.adapters import email_message_to_classification_input
from backend.app.classification.pipeline import classify_email
from backend.app.storage.database import Base
from backend.app.storage.repositories import EmailRepository
from backend.app.sync.service import SyncService
from backend.app.storage.models import EmailMessageRecord

@pytest.mark.req("ING-06")
@pytest.mark.req("ING-07")
def test_cross_source_normalizes_to_canonical_email_without_fabricated_time():
    record={"email_id":"same","from":"a@b","subject":" Subject  ","body":" Body  ","attachments":["attachments/a.pdf"]}
    static=map_organizer_record(record,source_type="STATIC_BUNDLE")
    incoming=map_incoming_payload(IncomingEmailPayload(external_message_id="same",sender="a@b",subject=" Subject  ",body=" Body  ",attachments=[IncomingAttachmentInput(filename="a.pdf",source_reference="attachments/a.pdf")]))
    assert isinstance(static,EmailMessage) and isinstance(incoming,EmailMessage)
    assert static.subject==incoming.subject==" Subject  " and static.body==incoming.body==" Body  "
    assert static.received_at is None and incoming.received_at is None and static.recipients==incoming.recipients==[]
    assert email_message_to_classification_input(static).external_message_id=="same"

@pytest.mark.req("ING-07")
def test_received_at_is_preserved_when_supplied_and_none_when_absent():
    supplied="2025-01-02T03:04:05Z"
    organizer=map_organizer_record({"email_id":"time","from":None,"subject":"s","body":"b","attachments":[],"received_at":supplied},source_type="ORGANIZER_HTTP")
    incoming=map_incoming_payload(IncomingEmailPayload(external_message_id="time2",subject="s",body="b",received_at=datetime(2025,1,2,3,4,5,tzinfo=timezone.utc)))
    absent=map_organizer_record({"email_id":"none","from":None,"subject":"s","body":"b","attachments":[]},source_type="STATIC_BUNDLE")
    assert organizer.received_at==datetime(2025,1,2,3,4,5,tzinfo=timezone.utc)
    assert incoming.received_at==datetime(2025,1,2,3,4,5,tzinfo=timezone.utc)
    assert absent.received_at is None

@pytest.mark.req("CLS-13")
def test_classification_uses_attachment_metadata_without_content_loader():
    message=map_incoming_payload(IncomingEmailPayload(external_message_id="x",subject="",body="Please compare the attached SI and draft BL.",attachments=[IncomingAttachmentInput(filename="SI.pdf",source_reference="never-read.pdf"),IncomingAttachmentInput(filename="BL.xlsx",source_reference="never-read.xlsx")]))
    result=classify_email(email_message_to_classification_input(message))
    assert result.category=="document_comparison"

@pytest.mark.req("ING-07")
def test_repository_identity_is_scoped_by_source():
    if not os.environ.get("HOLYSHIP_TEST_DATABASE_URL"): pytest.skip("test database unavailable")
    engine=create_engine(os.environ["HOLYSHIP_TEST_DATABASE_URL"]); Base.metadata.drop_all(engine); Base.metadata.create_all(engine); S=sessionmaker(bind=engine)
    try:
        with S() as s:
            repo=EmailRepository(s); a=map_incoming_payload(IncomingEmailPayload(external_message_id="id",subject="a")); b=map_organizer_record({"email_id":"id","from":None,"subject":"b","body":"","attachments":[]},source_type="STATIC_BUNDLE")
            first,changed=repo.upsert_message(a); again,changed_again=repo.upsert_message(a); other,other_changed=repo.upsert_message(b); s.commit()
            assert changed and not changed_again and other_changed and first.id!=other.id
    finally: Base.metadata.drop_all(engine); engine.dispose()

@pytest.mark.req("CLS-02")
def test_non_comparison_categories_complete_without_readiness(monkeypatch):
    if not os.environ.get("HOLYSHIP_TEST_DATABASE_URL"): pytest.skip("test database unavailable")
    engine=create_engine(os.environ["HOLYSHIP_TEST_DATABASE_URL"]); Base.metadata.drop_all(engine); Base.metadata.create_all(engine); S=sessionmaker(bind=engine)
    import backend.app.classification.pipeline as pipeline
    calls=[]
    original=pipeline.evaluate_readiness
    monkeypatch.setattr(pipeline,"evaluate_readiness",lambda *args: calls.append(args) or original(*args))
    cases=[("si","Please prepare shipping instruction."),("invoice","Please clarify invoice charges."),("general","FYI operational update."),("spam","Congratulations you have won! Click here to claim.")]
    try:
        with S() as s:
            for eid,body in cases: SyncService(s).sync_one(map_incoming_payload(IncomingEmailPayload(external_message_id=eid,subject="",body=body)))
            s.commit(); rows=list(s.scalars(select(EmailMessageRecord).order_by(EmailMessageRecord.external_message_id)))
            assert len(rows)==4 and all(r.processing_status=="COMPLETED" for r in rows) and calls==[]
    finally: Base.metadata.drop_all(engine); engine.dispose()
