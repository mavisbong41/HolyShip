"""Application lifecycle wiring for optional initial sync and polling."""

from __future__ import annotations

import logging
from threading import Event, Thread
from typing import Callable

from sqlalchemy.orm import Session

from backend.app.core.config import Settings
from backend.app.ingestion.polling import ContinuousIngestionWorker
from backend.app.ingestion.sources import EmailSource, OrganizerHttpSource, StaticBundleSource


logger = logging.getLogger(__name__)


def build_polling_source(settings: Settings) -> EmailSource:
    source_type = settings.polling_source_type.upper()
    if source_type == "STATIC_BUNDLE":
        return StaticBundleSource(settings.resolved_bundle_path)
    if source_type == "ORGANIZER_HTTP":
        if not settings.polling_organizer_http_url:
            raise ValueError("polling_organizer_http_url is required for ORGANIZER_HTTP")
        return OrganizerHttpSource(
            settings.polling_organizer_http_url,
            timeout_seconds=settings.organizer_http_timeout_seconds,
            retry_policy=settings.retry_policy,
        )
    raise ValueError(f"Unsupported polling_source_type: {settings.polling_source_type}")


class IngestionRuntime:
    """Own the optional background worker without coupling providers to FastAPI."""

    def __init__(
        self,
        settings: Settings,
        *,
        session_factory: Callable[[], Session],
        source_factory: Callable[[], EmailSource] | None = None,
        processor_factory: Callable[[Session], Callable] | None = None,
        worker_factory: Callable[..., ContinuousIngestionWorker] = ContinuousIngestionWorker,
    ):
        self.settings = settings
        self.session_factory = session_factory
        self.source_factory = source_factory or (lambda: build_polling_source(settings))
        self.processor_factory = processor_factory
        self.worker_factory = worker_factory
        self.stop_event = Event()
        self.worker: ContinuousIngestionWorker | None = None
        self.thread: Thread | None = None

    @property
    def enabled(self) -> bool:
        return self.settings.initial_sync_on_startup or self.settings.continuous_polling_enabled

    def start(self) -> None:
        if not self.enabled:
            return
        if self.processor_factory is None:
            raise ValueError("processor_factory is required when ingestion runtime is enabled")
        self.stop_event.clear()
        self.worker = self.worker_factory(
            source_key=self.source_key,
            session_factory=self.session_factory,
            source_factory=self.source_factory,
            processor_factory=self.processor_factory,
            poll_interval_seconds=self.settings.polling_interval_seconds,
            backoff_initial_seconds=self.settings.polling_backoff_initial_seconds,
            backoff_max_seconds=self.settings.polling_backoff_max_seconds,
            sleeper=self.stop_event.wait,
        )
        self.thread = Thread(target=self._run, name="holyship-ingestion", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread is not None and self.thread.is_alive():
            self.thread.join(timeout=min(5.0, self.settings.polling_interval_seconds + 1.0))

    @property
    def source_key(self) -> str:
        source_type = self.settings.polling_source_type.upper()
        if source_type == "ORGANIZER_HTTP":
            return f"{source_type}:{self.settings.polling_organizer_http_url or ''}"
        return f"{source_type}:{self.settings.organizer_bundle_path.resolve()}"

    def _run(self) -> None:
        assert self.worker is not None
        if self.settings.initial_sync_on_startup:
            try:
                self.worker._poll_from_configured_dependencies()
            except Exception:
                logger.exception("Initial ingestion sync failed")
                if not self.settings.continuous_polling_enabled:
                    return
        if self.settings.continuous_polling_enabled:
            self.worker.run(
                self.stop_event,
                start_immediately=not self.settings.initial_sync_on_startup,
            )
