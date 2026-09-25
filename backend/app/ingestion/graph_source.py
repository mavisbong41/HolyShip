"""Provider-isolated Microsoft Graph payload adapter.

The Phase 7 product contract only needs a source boundary. This adapter maps
already-fetched Graph payloads and deliberately contains no OAuth/client or
network code; a production connector can supply the payload iterator later.
"""

from __future__ import annotations

import base64
from collections.abc import Iterable
from datetime import datetime
from typing import Any

from backend.app.ingestion.models import (
    AttachmentMetadata,
    EmailMessage,
    SourceType,
    build_content_hash,
)
from backend.app.ingestion.sources import EmailSource


class MicrosoftGraphSource(EmailSource):
    source_type: SourceType = "MICROSOFT_GRAPH"

    def __init__(self, payloads: Iterable[dict[str, Any]]):
        self.payloads = list(payloads)
        self._attachments: dict[str, bytes] = {}

    def iter_messages(self) -> Iterable[EmailMessage]:
        for payload in self.payloads:
            yield self._map_payload(payload)

    def get_message(self, external_message_id: str) -> EmailMessage:
        for message in self.iter_messages():
            if message.external_message_id == external_message_id:
                return message
        raise KeyError(f"Microsoft Graph email not found: {external_message_id}")

    def get_attachment_content(self, attachment: AttachmentMetadata) -> bytes:
        try:
            return self._attachments[attachment.source_reference]
        except KeyError as exc:
            raise FileNotFoundError(
                f"Graph attachment content was not supplied: {attachment.source_reference}"
            ) from exc

    def _map_payload(self, payload: dict[str, Any]) -> EmailMessage:
        message_id = str(payload["id"])
        body = payload.get("body") or {}
        sender = ((payload.get("from") or {}).get("emailAddress") or {}).get("address")
        recipients = [
            (item.get("emailAddress") or {}).get("address")
            for item in payload.get("toRecipients") or []
            if (item.get("emailAddress") or {}).get("address")
        ]
        attachment_metadata: list[AttachmentMetadata] = []
        references: list[str] = []
        for item in payload.get("attachments") or []:
            attachment_id = str(item.get("id") or item.get("name") or "attachment")
            reference = f"graph://{message_id}/{attachment_id}"
            references.append(reference)
            encoded = item.get("contentBytes")
            if encoded:
                self._attachments[reference] = base64.b64decode(encoded)
            attachment_metadata.append(
                AttachmentMetadata(
                    filename=str(item.get("name") or attachment_id),
                    source_reference=reference,
                    content_type=item.get("contentType"),
                    external_attachment_id=attachment_id,
                )
            )
        subject = str(payload.get("subject") or "")
        text = str(body.get("content") or "")
        received_at = payload.get("receivedDateTime")
        parsed_received_at = (
            datetime.fromisoformat(received_at.replace("Z", "+00:00"))
            if isinstance(received_at, str)
            else None
        )
        return EmailMessage(
            external_message_id=message_id,
            source_type=self.source_type,
            sender=sender,
            recipients=recipients,
            subject=subject,
            body=text,
            received_at=parsed_received_at,
            attachments=attachment_metadata,
            source_metadata={
                "provider": "microsoft_graph",
                "payload_kind": "message",
                "graph_message_id": message_id,
                "internet_message_id": payload.get("internetMessageId"),
                "outlook_read_state": "READ" if payload.get("isRead") else "UNREAD",
                "outlook_categories": list(payload.get("categories") or []),
                "outlook_folder_id": payload.get("parentFolderId"),
            },
            content_hash=build_content_hash(
                source_type=self.source_type,
                external_message_id=message_id,
                subject=subject,
                body=text,
                attachment_references=references,
            ),
        )
