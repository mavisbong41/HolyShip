from __future__ import annotations

import base64

import pytest


@pytest.mark.req("SEC-05")
def test_graph_source_maps_fake_payload_without_credentials():
    from backend.app.ingestion.graph_source import MicrosoftGraphSource

    content = b"Port of Loading: Port Klang"
    source = MicrosoftGraphSource(
        [
            {
                "id": "graph-1",
                "subject": "Draft BL",
                "body": {"content": "Please compare the draft BL."},
                "from": {"emailAddress": {"address": "ops@example.com"}},
                "toRecipients": [{"emailAddress": {"address": "docs@example.com"}}],
                "receivedDateTime": "2026-09-20T10:00:00Z",
                "attachments": [
                    {
                        "id": "attachment-1",
                        "name": "draft-bl.txt",
                        "contentType": "text/plain",
                        "contentBytes": base64.b64encode(content).decode("ascii"),
                    }
                ],
            }
        ]
    )

    message = next(iter(source.iter_messages()))
    assert message.source_type == "MICROSOFT_GRAPH"
    assert message.external_message_id == "graph-1"
    assert message.sender == "ops@example.com"
    assert message.recipients == ["docs@example.com"]
    assert message.attachments[0].external_attachment_id == "attachment-1"
    assert source.get_attachment_content(message.attachments[0]) == content
