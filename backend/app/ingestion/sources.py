from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import datetime
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Iterable

from backend.app.ingestion.models import (
    AttachmentMetadata,
    EmailMessage,
    IncomingEmailPayload,
    SourceType,
    build_content_hash,
)


class EmailSource(ABC):
    @abstractmethod
    def iter_messages(self) -> Iterable[EmailMessage]:
        raise NotImplementedError

    @abstractmethod
    def get_message(self, external_message_id: str) -> EmailMessage:
        raise NotImplementedError

    def get_attachment_content(self, attachment: AttachmentMetadata) -> bytes:
        """Load attachment bytes lazily after comparison readiness is known."""
        raise FileNotFoundError(
            f"Attachment content is unavailable from {type(self).__name__}: "
            f"{attachment.source_reference}"
        )


class StaticBundleSource(EmailSource):
    source_type = "STATIC_BUNDLE"

    def __init__(self, bundle_path: str | Path):
        self.bundle_path = Path(bundle_path)
        self.inbox_path = self.bundle_path / "inbox"
        if not self.inbox_path.exists():
            raise FileNotFoundError(f"Organizer inbox not found: {self.inbox_path}")

    def iter_messages(self) -> Iterable[EmailMessage]:
        for path in sorted(self.inbox_path.glob("email_*.json")):
            yield self._map_record(json.loads(path.read_text(encoding="utf-8")), path)

    def get_message(self, external_message_id: str) -> EmailMessage:
        path = self.inbox_path / f"{external_message_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"Organizer email not found: {external_message_id}")
        return self._map_record(json.loads(path.read_text(encoding="utf-8")), path)

    def get_attachment_content(self, attachment: AttachmentMetadata) -> bytes:
        root = self.bundle_path.resolve()
        path = (root / attachment.source_reference).resolve()
        if not path.is_relative_to(root):
            raise ValueError("Attachment source reference escapes the configured bundle")
        return path.read_bytes()

    def _map_record(self, record: dict[str, Any], source_file: Path) -> EmailMessage:
        return map_organizer_record(
            record,
            source_type=self.source_type,
            source_metadata={
                "bundle_path": str(self.bundle_path),
                "source_file": str(source_file),
            },
        )


class OrganizerHttpSource(EmailSource):
    source_type = "ORGANIZER_HTTP"

    def __init__(self, base_url: str, timeout_seconds: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def iter_messages(self) -> Iterable[EmailMessage]:
        for record in self._get_json("/emails"):
            yield self._map_record(record)

    def get_message(self, external_message_id: str) -> EmailMessage:
        safe_id = urllib.parse.quote(external_message_id, safe="")
        return self._map_record(self._get_json(f"/emails/{safe_id}"))

    def get_attachment_content(self, attachment: AttachmentMetadata) -> bytes:
        safe_path = urllib.parse.quote(attachment.source_reference.lstrip("/"), safe="/")
        with urllib.request.urlopen(
            f"{self.base_url}/{safe_path}",
            timeout=self.timeout_seconds,
        ) as response:
            return response.read()

    def _get_json(self, path: str) -> Any:
        with urllib.request.urlopen(
            f"{self.base_url}{path}",
            timeout=self.timeout_seconds,
        ) as response:
            return json.loads(response.read().decode("utf-8"))

    def _map_record(self, record: dict[str, Any]) -> EmailMessage:
        return map_organizer_record(
            record,
            source_type=self.source_type,
            source_metadata={"base_url": self.base_url},
        )


class IncomingApiSource(EmailSource):
    source_type = "INCOMING_API"

    def __init__(
        self,
        payloads: IncomingEmailPayload | list[IncomingEmailPayload],
        attachment_contents: dict[str, bytes] | None = None,
    ):
        if isinstance(payloads, IncomingEmailPayload):
            self.payloads = [payloads]
        else:
            self.payloads = list(payloads)
        self.attachment_contents = attachment_contents or {}

    def iter_messages(self) -> Iterable[EmailMessage]:
        for payload in self.payloads:
            yield map_incoming_payload(payload)

    def get_message(self, external_message_id: str) -> EmailMessage:
        for message in self.iter_messages():
            if message.external_message_id == external_message_id:
                return message
        raise KeyError(f"Incoming email not found: {external_message_id}")

    def get_attachment_content(self, attachment: AttachmentMetadata) -> bytes:
        try:
            return self.attachment_contents[attachment.source_reference]
        except KeyError as exc:
            raise FileNotFoundError(
                f"Incoming attachment content was not supplied: {attachment.source_reference}"
            ) from exc


def map_organizer_record(
    record: dict[str, Any],
    *,
    source_type: SourceType,
    source_metadata: dict[str, Any] | None = None,
) -> EmailMessage:
    required = {"email_id", "from", "subject", "body", "attachments"}
    missing = required - set(record)
    if missing:
        raise ValueError(f"Malformed organizer email {record.get('email_id', '<unknown>')}; missing {sorted(missing)}")

    attachment_refs = list(record["attachments"] or [])
    attachments = [
        AttachmentMetadata(
            filename=Path(ref).name,
            source_reference=ref,
            content_type=_content_type_for(ref),
            external_attachment_id=ref,
        )
        for ref in attachment_refs
    ]
    subject = record.get("subject") or ""
    body = record.get("body") or ""
    external_message_id = record["email_id"]
    metadata = dict(source_metadata or {})
    metadata["raw_keys"] = sorted(record.keys())

    return EmailMessage(
        external_message_id=external_message_id,
        source_type=source_type,
        sender=record.get("from"),
        recipients=[],
        subject=subject,
        body=body,
        received_at=_parse_received_at(record.get("received_at")),
        attachments=attachments,
        source_metadata=metadata,
        content_hash=build_content_hash(
            source_type=source_type,
            external_message_id=external_message_id,
            subject=subject,
            body=body,
            attachment_references=attachment_refs,
        ),
    )


def map_incoming_payload(payload: IncomingEmailPayload) -> EmailMessage:
    attachment_references = [
        attachment.source_reference or attachment.filename
        for attachment in payload.attachments
    ]
    external_message_id = payload.external_message_id or _generated_incoming_id(
        sender=payload.sender,
        recipients=payload.recipients,
        subject=payload.subject,
        body=payload.body,
        attachment_references=attachment_references,
    )
    attachments = [
        AttachmentMetadata(
            filename=attachment.filename,
            source_reference=attachment.source_reference or attachment.filename,
            content_type=attachment.content_type or _content_type_for(attachment.filename),
            external_attachment_id=attachment.external_attachment_id,
        )
        for attachment in payload.attachments
    ]

    return EmailMessage(
        external_message_id=external_message_id,
        source_type="INCOMING_API",
        sender=payload.sender,
        recipients=payload.recipients,
        subject=payload.subject,
        body=payload.body,
        received_at=payload.received_at,
        attachments=attachments,
        source_metadata=payload.source_metadata,
        content_hash=build_content_hash(
            source_type="INCOMING_API",
            external_message_id=external_message_id,
            subject=payload.subject,
            body=payload.body,
            attachment_references=attachment_references,
        ),
    )


def _generated_incoming_id(
    *,
    sender: str | None,
    recipients: list[str],
    subject: str,
    body: str,
    attachment_references: list[str],
) -> str:
    payload = {
        "sender": sender,
        "recipients": recipients,
        "subject": subject,
        "body": body,
        "attachment_references": attachment_references,
    }
    digest = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    import hashlib

    return f"incoming_{hashlib.sha256(digest.encode('utf-8')).hexdigest()[:16]}"


def _content_type_for(path: str) -> str | None:
    extension = Path(path).suffix.lower()
    return {
        ".txt": "text/plain",
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }.get(extension)


def _parse_received_at(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    raise ValueError("Organizer received_at must be an ISO-8601 timestamp")
