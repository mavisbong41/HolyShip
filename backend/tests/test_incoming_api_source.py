from datetime import datetime, timezone

from backend.app.ingestion.models import IncomingAttachmentInput, IncomingEmailPayload
from backend.app.ingestion.sources import IncomingApiSource, map_incoming_payload


def test_incoming_payload_maps_to_unified_email_message():
    payload = IncomingEmailPayload(
        external_message_id="msg-123",
        sender="customer@example.com",
        recipients=["ops@example.com"],
        subject="Please review",
        body="Please compare the attached SI and draft BL.",
        received_at=datetime(2026, 9, 19, 12, 30, tzinfo=timezone.utc),
        attachments=[
            IncomingAttachmentInput(
                filename="draft-bl.pdf",
                source_reference="incoming/draft-bl.pdf",
                external_attachment_id="att-1",
            )
        ],
        source_metadata={"mailbox": "demo"},
    )

    message = map_incoming_payload(payload)

    assert message.external_message_id == "msg-123"
    assert message.source_type == "INCOMING_API"
    assert message.sender == "customer@example.com"
    assert message.recipients == ["ops@example.com"]
    assert message.received_at == datetime(2026, 9, 19, 12, 30, tzinfo=timezone.utc)
    assert message.attachments[0].content_type == "application/pdf"
    assert message.attachments[0].source_reference == "incoming/draft-bl.pdf"
    assert message.source_metadata == {"mailbox": "demo"}
    assert len(message.content_hash) == 64


def test_incoming_payload_generates_stable_external_id_when_missing():
    payload = IncomingEmailPayload(
        sender="customer@example.com",
        subject="Question",
        body="Hello",
        attachments=[IncomingAttachmentInput(filename="note.txt")],
    )

    first = map_incoming_payload(payload)
    second = map_incoming_payload(payload)

    assert first.external_message_id.startswith("incoming_")
    assert first.external_message_id == second.external_message_id
    assert first.content_hash == second.content_hash


def test_incoming_api_source_iterates_payloads():
    source = IncomingApiSource(
        [
            IncomingEmailPayload(external_message_id="one", subject="One"),
            IncomingEmailPayload(external_message_id="two", subject="Two"),
        ]
    )

    messages = list(source.iter_messages())

    assert [message.external_message_id for message in messages] == ["one", "two"]
    assert source.get_message("two").subject == "Two"

