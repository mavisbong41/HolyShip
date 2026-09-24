"""Application runtime for scheduled Data Lifecycle Management."""

from __future__ import annotations

import logging
from threading import Event, Thread
from typing import Callable

from sqlalchemy.orm import Session

from backend.app.core.config import Settings
from backend.app.data_lifecycle.service import DataLifecyclePolicy, DataLifecycleService


logger = logging.getLogger(__name__)


class DataLifecycleRuntime:
    def __init__(
        self,
        settings: Settings,
        *,
        session_factory: Callable[[], Session],
        sleeper: Callable[[float], bool] | None = None,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.stop_event = Event()
        self.sleeper = sleeper or self.stop_event.wait
        self.thread: Thread | None = None

    @property
    def enabled(self) -> bool:
        return self.settings.data_lifecycle_enabled

    @property
    def interval_seconds(self) -> float:
        return self.settings.data_lifecycle_interval_hours * 3600

    def start(self) -> None:
        if not self.enabled:
            return
        self.stop_event.clear()
        self.thread = Thread(target=self._run, name="holyship-data-lifecycle", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread is not None and self.thread.is_alive():
            self.thread.join(timeout=min(5.0, self.interval_seconds + 1.0))

    def run_once(self) -> None:
        policy = DataLifecyclePolicy.from_settings(self.settings)
        with self.session_factory() as session:
            run = DataLifecycleService(session, policy).run(
                dry_run=self.settings.data_lifecycle_dry_run,
                source="SCHEDULER",
            )
            logger.info(
                "Data lifecycle run completed status=%s dry_run=%s summary=%s",
                run.status,
                run.dry_run,
                run.summary,
            )

    def _run(self) -> None:
        if self.settings.data_lifecycle_run_on_startup:
            self._run_safely()
        while not self.stop_event.is_set():
            if self.sleeper(self.interval_seconds):
                break
            self._run_safely()

    def _run_safely(self) -> None:
        try:
            self.run_once()
        except Exception:
            logger.exception("Scheduled data lifecycle run failed")
