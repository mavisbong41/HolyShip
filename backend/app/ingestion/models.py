from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


SourceType = Literal["STATIC_BUNDLE", "ORGANIZER_HTTP", "INCOMING_API"]


class AttachmentMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)

    filename: str
    source_reference: str
    content_type: str | None = None
    external_attachment_id: str | None = None

    @property
    def extension(self) -> str:
        return Path(self.filename).suffix.lower()


class EmailMessage(BaseModel):
    model_config = ConfigDict(frozen=True)

    external_message_id: str
    source_type: SourceType
    sender: str | None = None
    recipients: list[str] = Field(default_factory=list)
    subject: str
    body: str
    received_at: datetime | None = None
    attachments: list[AttachmentMetadata] = Field(default_factory=list)
    source_metadata: dict[str, Any] = Field(default_factory=dict)
    content_hash: str


class IncomingAttachmentInput(BaseModel):
    filename: str
    source_reference: str | None = None
    content_type: str | None = None
    external_attachment_id: str | None = None


class IncomingEmailPayload(BaseModel):
    external_message_id: str | None = None
    sender: str | None = None
    recipients: list[str] = Field(default_factory=list)
    subject: str
    body: str = ""
    received_at: datetime | None = None
    attachments: list[IncomingAttachmentInput] = Field(default_factory=list)
    source_metadata: dict[str, Any] = Field(default_factory=dict)


def build_content_hash(
    *,
    source_type: SourceType,
    external_message_id: str,
    subject: str,
    body: str,
    attachment_references: list[str],
) -> str:
    payload = {
        "source_type": source_type,
        "external_message_id": external_message_id,
        "subject": subject,
        "body": body,
        "attachment_references": attachment_references,
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
