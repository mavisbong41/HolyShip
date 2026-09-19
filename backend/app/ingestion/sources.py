from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Iterable

from backend.app.ingestion.models import AttachmentMetadata, EmailMessage, build_content_hash


class EmailSource(ABC):
    @abstractmethod
    def iter_messages(self) -> Iterable[EmailMessage]:
        raise NotImplementedError

    @abstractmethod
    def get_message(self, external_message_id: str) -> EmailMessage:
        raise NotImplementedError


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

    def _map_record(self, record: dict[str, Any], source_file: Path) -> EmailMessage:
        required = {"email_id", "from", "subject", "body", "attachments"}
        missing = required - set(record)
        if missing:
            raise ValueError(f"Malformed organizer email {source_file.name}; missing {sorted(missing)}")

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

        return EmailMessage(
            external_message_id=record["email_id"],
            source_type=self.source_type,
            sender=record.get("from"),
            recipients=[],
            subject=subject,
            body=body,
            attachments=attachments,
            source_metadata={
                "bundle_path": str(self.bundle_path),
                "source_file": str(source_file),
                "raw_keys": sorted(record.keys()),
            },
            content_hash=build_content_hash(
                source_type=self.source_type,
                external_message_id=record["email_id"],
                subject=subject,
                body=body,
                attachment_references=attachment_refs,
            ),
        )


def _content_type_for(path: str) -> str | None:
    extension = Path(path).suffix.lower()
    return {
        ".txt": "text/plain",
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }.get(extension)

