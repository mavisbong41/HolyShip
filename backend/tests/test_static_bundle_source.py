from collections import Counter

from backend.app.ingestion.sources import StaticBundleSource


ORGANIZER_BUNDLE_PATH = "sdoc-hackathon-bundle"


def test_static_bundle_source_loads_all_organizer_emails():
    source = StaticBundleSource(ORGANIZER_BUNDLE_PATH)

    messages = list(source.iter_messages())

    assert len(messages) == 520
    assert messages[0].external_message_id == "email_001"
    assert messages[0].source_type == "STATIC_BUNDLE"
    assert messages[0].sender
    assert messages[0].subject
    assert messages[0].body
    assert len(messages[0].content_hash) == 64


def test_static_bundle_source_maps_attachment_metadata_without_reading_contents():
    source = StaticBundleSource(ORGANIZER_BUNDLE_PATH)

    message = source.get_message("email_001")

    assert [attachment.filename for attachment in message.attachments] == [
        "email_001_SI.txt",
        "email_001_BL.txt",
    ]
    assert [attachment.source_reference for attachment in message.attachments] == [
        "attachments/email_001_SI.txt",
        "attachments/email_001_BL.txt",
    ]
    assert all(attachment.content_type == "text/plain" for attachment in message.attachments)


def test_static_bundle_source_preserves_observed_attachment_distribution():
    source = StaticBundleSource(ORGANIZER_BUNDLE_PATH)

    messages = list(source.iter_messages())
    attachment_counts = Counter(len(message.attachments) for message in messages)
    extensions = Counter(
        attachment.extension
        for message in messages
        for attachment in message.attachments
    )

    assert attachment_counts == {0: 394, 1: 2, 2: 124}
    assert extensions == {".txt": 192, ".pdf": 28, ".xlsx": 22, ".docx": 8}
