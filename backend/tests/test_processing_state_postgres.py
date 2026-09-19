import os
import pytest
from sqlalchemy import create_engine, text, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from backend.app.ingestion.models import EmailMessage, AttachmentMetadata
from backend.app.storage.database import Base
from backend.app.storage.models import EmailMessageRecord, ClassificationResultRecord, ProcessingEventRecord, HumanReviewCaseRecord
from backend.app.storage.transitions import PROCESSING_STATUSES, transition
from backend.app.sync.service import SyncService

pytestmark = pytest.mark.skipif(not os.environ.get("HOLYSHIP_TEST_DATABASE_URL"), reason="HOLYSHIP_TEST_DATABASE_URL is required")

@pytest.fixture()
def db():
    engine = create_engine(os.environ["HOLYSHIP_TEST_DATABASE_URL"])
    Base.metadata.drop_all(engine); Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    try: yield factory
    finally: Base.metadata.drop_all(engine); engine.dispose()

def message(eid, subject, body, attachments=()):
    return EmailMessage(external_message_id=eid, source_type="INCOMING_API", sender="a@b", recipients=["c@d"], subject=subject, body=body, attachments=[AttachmentMetadata(filename=x, source_reference=x, content_type="text/plain", external_attachment_id=x) for x in attachments], source_metadata={"origin":"test"}, content_hash=eid.ljust(64,"x"))

@pytest.mark.req("STA-01")
def test_status_vocabulary_and_database_constraint(db):
    assert PROCESSING_STATUSES == {"NEW","QUEUED","CLASSIFYING","CLASSIFIED","AWAITING_DOCUMENTS","RETRIEVING_ATTACHMENTS","EXTRACTING","COMPARING","COMPLETED","BLOCKED","FAILED"}
    with db() as s:
        row = EmailMessageRecord(source_type="TEST", external_message_id="bad", subject="", body="", recipients=[], content_hash="z"*64)
        s.add(row); s.commit()
        with pytest.raises(IntegrityError):
            s.execute(text("UPDATE email_messages SET processing_status='NOT_A_REAL_STATUS' WHERE id=:id"), {"id": row.id}); s.commit()

def _events(s, eid): return list(s.scalars(select(ProcessingEventRecord).join(EmailMessageRecord).where(EmailMessageRecord.external_message_id==eid).order_by(ProcessingEventRecord.created_at, ProcessingEventRecord.id)))

@pytest.mark.req("STA-04")
@pytest.mark.req("STA-06")
def test_completed_events_noop_and_input_immutable(db):
    with db() as s:
        m=message("normal","Invoice","Please clarify this payment amount on the invoice.",["source.txt"]); snapshot=(m.subject,m.body,m.attachments[0].filename,m.attachments[0].source_reference)
        SyncService(s).sync_one(m); s.commit()
    with db() as s:
        row=s.scalar(select(EmailMessageRecord).where(EmailMessageRecord.external_message_id=="normal")); events=_events(s,"normal")
        assert [(e.old_status,e.new_status) for e in events]==[("NEW","QUEUED"),("QUEUED","CLASSIFYING"),("CLASSIFYING","CLASSIFIED"),("CLASSIFIED","COMPLETED")]
        assert row.processing_status=="COMPLETED" and (row.subject,row.body,row.attachments[0].filename,row.attachments[0].source_reference)==snapshot
        count=len(events); assert not transition(s,row,"COMPLETED","NOOP"); s.commit(); assert len(_events(s,"normal"))==count
        with pytest.raises(ValueError): transition(s,row,"BAD","BAD")

@pytest.mark.req("STA-02")
def test_awaiting_persists(db):
    with db() as s: SyncService(s).sync_one(message("await","Draft BL","Please assist to send the draft BL for booking 42 for checking asap.")); s.commit()
    with db() as s:
        r=s.scalar(select(EmailMessageRecord).where(EmailMessageRecord.external_message_id=="await")); c=s.scalar(select(ClassificationResultRecord).where(ClassificationResultRecord.email_id==r.id)); assert (c.category,c.comparison_readiness,r.processing_status)==("document_comparison","AWAITING_DOCUMENTS","AWAITING_DOCUMENTS")

@pytest.mark.req("STA-07")
def test_unresolved_persists_blocked_without_review(db):
    with db() as s: SyncService(s).sync_one(message("unresolved","Check BL","Please check draft BL details.")); s.commit()
    with db() as s:
        r=s.scalar(select(EmailMessageRecord).where(EmailMessageRecord.external_message_id=="unresolved")); c=s.scalar(select(ClassificationResultRecord).where(ClassificationResultRecord.email_id==r.id)); e=_events(s,"unresolved")[-1]
        assert (c.category,c.comparison_readiness,r.processing_status,e.new_status,e.reason_code)==("document_comparison","UNRESOLVED","BLOCKED","BLOCKED","READINESS_UNRESOLVED")
        assert s.scalar(select(HumanReviewCaseRecord).where(HumanReviewCaseRecord.email_id==r.id)) is None
