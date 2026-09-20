from __future__ import annotations

import threading
from dataclasses import dataclass

import pytest

from backend.app.ingestion.models import EmailMessage
from backend.app.ingestion.runtime import IngestionRuntime


@dataclass
class _Existing:
    content_hash: str
    processing_status: str


class _StateStore:
    def __init__(self) -> None:
        self.existing: dict[tuple[str, str], _Existing] = {}
        self.checkpoints: dict[str, dict[str, object]] = {}
        self.successes: list[dict[str, object]] = []
        self.failures: list[dict[str, object]] = []

    def existing_messages(self, source_type: str) -> dict[str, _Existing]:
        return {
            external_id: state
            for (stored_source, external_id), state in self.existing.items()
            if stored_source == source_type
        }

    def record_success(self, **payload: object) -> None:
        self.successes.append(payload)
        self.checkpoints[str(payload["source_key"])] = dict(payload)

    def record_failure(self, **payload: object) -> None:
        self.failures.append(payload)


class _Source:
    source_type = "INCOMING_API"

    def __init__(self, messages: list[EmailMessage]) -> None:
        self.messages = messages
        self.attachment_reads = 0

    def iter_messages(self):
        yield from self.messages

    def get_message(self, external_message_id: str) -> EmailMessage:
        return next(item for item in self.messages if item.external_message_id == external_message_id)

    def get_attachment_content(self, attachment):
        self.attachment_reads += 1
        return b"content"


def _message(external_id: str) -> EmailMessage:
    return EmailMessage(
        external_message_id=external_id,
        source_type="INCOMING_API",
        subject="General update",
        body="The vessel departed.",
        content_hash=f"hash-{external_id}",
    )


@pytest.mark.req("ING-08")
def test_poll_sequence_processes_only_new_messages_and_persists_checkpoint():
    from backend.app.ingestion.polling import ContinuousIngestionWorker

    state = _StateStore()
    processed: list[str] = []

    def process(message, source):
        processed.append(message.external_message_id)
        state.existing[(message.source_type, message.external_message_id)] = _Existing(
            content_hash=message.content_hash,
            processing_status="COMPLETED",
        )

    worker = ContinuousIngestionWorker(source_key="fake-inbox", poll_interval_seconds=60)
    first = [_message("A"), _message("B")]
    second = [_message("A"), _message("B")]
    third = [_message("A"), _message("B"), _message("C")]

    result_one = worker.poll_once(source=_Source(first), processor=process, state_store=state)
    result_two = worker.poll_once(source=_Source(second), processor=process, state_store=state)
    result_three = worker.poll_once(source=_Source(third), processor=process, state_store=state)

    assert result_one.submitted == 2
    assert result_two.submitted == 0
    assert result_two.skipped_seen == 2
    assert result_three.submitted == 1
    assert processed == ["A", "B", "C"]
    assert state.checkpoints["fake-inbox"]["last_seen_external_id"] == "C"
    assert len(state.successes) == 3


@pytest.mark.req("ING-08")
def test_poll_restart_uses_persisted_state_and_does_not_refetch_attachments():
    from backend.app.ingestion.polling import ContinuousIngestionWorker

    state = _StateStore()
    message = _message("restart-A")
    first_source = _Source([message])
    first_processor_calls: list[str] = []

    def first_process(item, source):
        first_processor_calls.append(item.external_message_id)
        source.get_attachment_content(type("Attachment", (), {"source_reference": "a.txt"})())
        state.existing[(item.source_type, item.external_message_id)] = _Existing(
            content_hash=item.content_hash,
            processing_status="COMPLETED",
        )

    ContinuousIngestionWorker(source_key="restart-source").poll_once(
        source=first_source,
        processor=first_process,
        state_store=state,
    )
    second_source = _Source([message])
    second_processor_calls: list[str] = []
    ContinuousIngestionWorker(source_key="restart-source").poll_once(
        source=second_source,
        processor=lambda item, source: second_processor_calls.append(item.external_message_id),
        state_store=state,
    )

    assert first_processor_calls == ["restart-A"]
    assert second_processor_calls == []
    assert first_source.attachment_reads == 1
    assert second_source.attachment_reads == 0


@pytest.mark.req("ING-08")
def test_polling_backoff_is_bounded_and_resets_after_success():
    from backend.app.ingestion.polling import ContinuousIngestionWorker

    stop = threading.Event()
    delays: list[float] = []
    outcomes = iter([RuntimeError("temporary"), RuntimeError("temporary"), None])

    def poll_once():
        outcome = next(outcomes)
        if outcome is not None:
            raise outcome

    def wait(delay: float) -> None:
        delays.append(delay)
        if len(delays) == 3:
            stop.set()

    worker = ContinuousIngestionWorker(
        source_key="backoff-source",
        poll_interval_seconds=60,
        backoff_initial_seconds=1,
        backoff_max_seconds=4,
        sleeper=wait,
    )
    worker.run(stop, poll_once=poll_once)

    assert delays == [1, 2, 60]


@pytest.mark.req("ING-01")
@pytest.mark.req("ING-03")
def test_polling_settings_are_configurable_and_default_to_sixty_seconds():
    from backend.app.core.config import Settings

    settings = Settings(_env_file=None)
    assert settings.polling_interval_seconds == 60
    assert settings.continuous_polling_enabled is False
    assert settings.initial_sync_on_startup is False


@pytest.mark.req("ING-01")
@pytest.mark.req("ING-03")
def test_ingestion_runtime_is_disabled_by_default():
    from backend.app.core.config import Settings

    settings = Settings(_env_file=None)
    created = []
    runtime = IngestionRuntime(
        settings,
        session_factory=lambda: None,
        processor_factory=lambda _session: lambda _message, _source: None,
        worker_factory=lambda **kwargs: created.append(kwargs),
    )

    runtime.start()
    runtime.stop()

    assert created == []


@pytest.mark.req("ING-01")
def test_ingestion_runtime_runs_configured_initial_sync_once():
    from backend.app.core.config import Settings

    settings = Settings(_env_file=None, initial_sync_on_startup=True)
    calls = []

    class FakeWorker:
        def __init__(self, **kwargs):
            calls.append(("constructed", kwargs))

        def _poll_from_configured_dependencies(self):
            calls.append(("initial", None))

        def run(self, *_args, **_kwargs):
            calls.append(("run", None))

    runtime = IngestionRuntime(
        settings,
        session_factory=lambda: None,
        processor_factory=lambda _session: lambda _message, _source: None,
        worker_factory=FakeWorker,
    )
    runtime.start()
    assert runtime.thread is not None
    runtime.thread.join(timeout=2)
    runtime.stop()

    assert [kind for kind, _ in calls] == ["constructed", "initial"]
