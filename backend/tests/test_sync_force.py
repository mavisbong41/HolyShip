from __future__ import annotations

import inspect
from unittest.mock import MagicMock, patch

import pytest

from backend.app.ingestion.models import AttachmentMetadata, EmailMessage
from backend.app.ingestion.sources import EmailSource
from backend.app.sync.service import EmailSyncOutcome, SyncReport, SyncService


class DummyListSource(EmailSource):
    def __init__(self, messages: list[EmailMessage]):
        self._messages = messages

    def iter_messages(self):
        return iter(self._messages)

    def get_message(self, external_message_id: str):
        for msg in self._messages:
            if msg.external_message_id == external_message_id:
                return msg
        raise FileNotFoundError(external_message_id)


def _make_msg(ext_id: str) -> EmailMessage:
    return EmailMessage(
        external_message_id=ext_id,
        source_type="INCOMING_API",
        subject="Test subject",
        body="Test body",
        attachments=[],
        content_hash="h" * 64,
    )


def test_sync_service_signature_accepts_force_keyword():
    sig = inspect.signature(SyncService.sync)
    assert "force" in sig.parameters
    assert sig.parameters["force"].default is False
    assert sig.parameters["force"].kind == inspect.Parameter.KEYWORD_ONLY


def test_sync_sequential_propagates_force():
    mock_session = MagicMock()
    service = SyncService(mock_session)

    source = DummyListSource([_make_msg("msg1")])

    with patch.object(service, "_process_one") as mock_process:
        mock_process.return_value = EmailSyncOutcome(external_message_id="msg1", status="CLASSIFIED")
        report = service.sync(source, force=False)
        assert report.total == 1
        mock_process.assert_called_once_with(source._messages[0], source, force=False)

    source2 = DummyListSource([_make_msg("msg2")])
    with patch.object(service, "_process_one") as mock_process:
        mock_process.return_value = EmailSyncOutcome(external_message_id="msg2", status="CLASSIFIED")
        report = service.sync(source2, force=True)
        assert report.total == 1
        mock_process.assert_called_once_with(source2._messages[0], source2, force=True)


def test_sync_parallel_propagates_force():
    mock_session = MagicMock()
    mock_session_factory = MagicMock()
    service = SyncService(mock_session, max_workers=2, session_factory=mock_session_factory)

    source = DummyListSource([_make_msg("msg_par")])

    with patch.object(service, "_process_parallel_one") as mock_par_one:
        mock_par_one.return_value = EmailSyncOutcome(external_message_id="msg_par", status="CLASSIFIED")
        report = service.sync(source, force=True)
        assert report.total == 1
        mock_par_one.assert_called_once_with(source._messages[0], source, force=True)
