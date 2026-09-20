from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.documents.models import UnifiedDocument
from backend.app.extraction.extractor import DeterministicDocumentExtractor
from backend.app.extraction.models import DocumentExtractionResult
from backend.app.storage.models import DocumentExtractionRecord
from backend.app.storage.repositories import (
    DocumentExtractionRepository,
    ExtractedFieldRepository,
)


@dataclass(frozen=True)
class ExtractionTarget:
    document: UnifiedDocument
    content_sha256: str
    extraction: DocumentExtractionRecord


@dataclass(frozen=True)
class ExtractionOutcome:
    extraction_id: UUID
    status: Literal["SUCCEEDED", "FAILED"]
    cache_hit: bool
    error: str | None = None


@dataclass(frozen=True)
class ExtractionBatchResult:
    outcomes: tuple[ExtractionOutcome, ...]
    computations: int
    cache_hits: int
    cache_misses: int

    @property
    def failed(self) -> tuple[ExtractionOutcome, ...]:
        return tuple(outcome for outcome in self.outcomes if outcome.status == "FAILED")


class DocumentFieldExtractionService:
    """Compute at most two document payloads concurrently and persist serially.

    Worker threads only receive immutable/materialized ``UnifiedDocument`` values.
    All SQLAlchemy access is performed by the caller thread after futures finish.
    """

    def __init__(
        self,
        session: Session,
        extractor: DeterministicDocumentExtractor | None = None,
        *,
        max_workers: int = 2,
    ) -> None:
        if not 1 <= max_workers <= 2:
            raise ValueError("Phase-3 SI/BL extraction workers must be between 1 and 2")
        self.session = session
        self.extractor = extractor or DeterministicDocumentExtractor()
        self.max_workers = max_workers
        self.extraction_repo = DocumentExtractionRepository(session)
        self.field_repo = ExtractedFieldRepository(session)

    def extract(self, targets: list[ExtractionTarget]) -> ExtractionBatchResult:
        if not 1 <= len(targets) <= 2:
            raise ValueError("extraction orchestration expects one SI/BL work item per side")

        version = self.extractor.version
        outcomes: dict[UUID, ExtractionOutcome] = {}
        pending_by_key: dict[tuple[str, str], list[ExtractionTarget]] = {}
        excluded = {target.extraction.id for target in targets}
        cache_hits = 0
        cache_misses = 0

        # Cache reads and current-row idempotency checks stay on the caller thread.
        for target in targets:
            if (
                target.extraction.extraction_status == "EXTRACTED"
                and target.extraction.extractor_version == version
                and self.field_repo.has_complete_result(target.extraction.id)
            ):
                outcomes[target.extraction.id] = ExtractionOutcome(
                    extraction_id=target.extraction.id,
                    status="SUCCEEDED",
                    cache_hit=True,
                )
                cache_hits += 1
                continue

            cached = self.extraction_repo.find_cached_by_content(
                content_sha256=target.content_sha256,
                extractor_version=version,
                exclude_extraction_ids=excluded,
            )
            if cached is not None:
                try:
                    with self.session.begin_nested():
                        self._persist_cached(target, cached)
                except Exception as exc:
                    error = f"{type(exc).__name__}: {exc}"
                    self._persist_failure(target, error)
                    outcomes[target.extraction.id] = ExtractionOutcome(
                        extraction_id=target.extraction.id,
                        status="FAILED",
                        cache_hit=False,
                        error=error,
                    )
                else:
                    outcomes[target.extraction.id] = ExtractionOutcome(
                        extraction_id=target.extraction.id,
                        status="SUCCEEDED",
                        cache_hit=True,
                    )
                    cache_hits += 1
                continue

            key = (target.content_sha256, version)
            if key in pending_by_key:
                cache_hits += 1
            else:
                cache_misses += 1
            pending_by_key.setdefault(key, []).append(target)

        futures: dict[tuple[str, str], Future[DocumentExtractionResult]] = {}
        if pending_by_key:
            workers = min(self.max_workers, len(pending_by_key), 2)
            with ThreadPoolExecutor(
                max_workers=workers,
                thread_name_prefix="holyship-extract",
            ) as executor:
                for key, grouped_targets in pending_by_key.items():
                    futures[key] = executor.submit(
                        self.extractor.extract,
                        grouped_targets[0].document,
                    )

                # Future resolution and every persistence operation happen here,
                # after submission, on the owning/caller thread.
                for key, grouped_targets in pending_by_key.items():
                    future = futures[key]
                    try:
                        result = future.result()
                    except Exception as exc:
                        error = f"{type(exc).__name__}: {exc}"
                        for target in grouped_targets:
                            self._persist_failure(target, error)
                            outcomes[target.extraction.id] = ExtractionOutcome(
                                extraction_id=target.extraction.id,
                                status="FAILED",
                                cache_hit=False,
                                error=error,
                            )
                        continue

                    for index, target in enumerate(grouped_targets):
                        try:
                            with self.session.begin_nested():
                                self._persist_fresh(
                                    target,
                                    result,
                                    reused_in_batch=index > 0,
                                    source_extraction_id=(
                                        grouped_targets[0].extraction.id if index > 0 else None
                                    ),
                                )
                        except Exception as exc:
                            error = f"{type(exc).__name__}: {exc}"
                            self._persist_failure(target, error)
                            outcomes[target.extraction.id] = ExtractionOutcome(
                                extraction_id=target.extraction.id,
                                status="FAILED",
                                cache_hit=False,
                                error=error,
                            )
                        else:
                            outcomes[target.extraction.id] = ExtractionOutcome(
                                extraction_id=target.extraction.id,
                                status="SUCCEEDED",
                                cache_hit=index > 0,
                            )

        ordered = tuple(outcomes[target.extraction.id] for target in targets)
        return ExtractionBatchResult(
            outcomes=ordered,
            computations=len(pending_by_key),
            cache_hits=cache_hits,
            cache_misses=cache_misses,
        )

    def _persist_cached(
        self,
        target: ExtractionTarget,
        cached: DocumentExtractionRecord,
    ) -> None:
        self.field_repo.clear_result(target.extraction.id)
        self.field_repo.copy_result(
            source_extraction_id=cached.id,
            target_extraction_id=target.extraction.id,
        )
        target.extraction.extraction_status = "EXTRACTED"
        target.extraction.extractor_version = self.extractor.version
        self._set_cache_metadata(
            target,
            status="HIT",
            source_extraction_id=cached.id,
        )
        self.extraction_repo.register_cache_entry(
            content_sha256=target.content_sha256,
            extractor_version=self.extractor.version,
            source_extraction_id=cached.id,
        )
        self.session.flush()

    def _persist_fresh(
        self,
        target: ExtractionTarget,
        result: DocumentExtractionResult,
        *,
        reused_in_batch: bool,
        source_extraction_id: UUID | None,
    ) -> None:
        if result.extractor_version != self.extractor.version:
            raise ValueError("extractor result version does not match cache identity")
        self.field_repo.clear_result(target.extraction.id)
        self.field_repo.create_result(target.extraction.id, result)
        target.extraction.extraction_status = "EXTRACTED"
        target.extraction.extractor_version = self.extractor.version
        self._set_cache_metadata(
            target,
            status="HIT_IN_BATCH" if reused_in_batch else "MISS",
            source_extraction_id=source_extraction_id,
        )
        cache_source = self.extraction_repo.register_cache_entry(
            content_sha256=target.content_sha256,
            extractor_version=self.extractor.version,
            source_extraction_id=target.extraction.id,
        )
        if cache_source.id != target.extraction.id:
            self.field_repo.clear_result(target.extraction.id)
            self.field_repo.copy_result(
                source_extraction_id=cache_source.id,
                target_extraction_id=target.extraction.id,
            )
            self._set_cache_metadata(
                target,
                status="HIT_RACE_RECOVERY",
                source_extraction_id=cache_source.id,
            )
        self.session.flush()

    def _persist_failure(self, target: ExtractionTarget, error: str) -> None:
        self.field_repo.clear_result(target.extraction.id)
        target.extraction.extraction_status = "FAILED"
        target.extraction.extractor_version = self.extractor.version
        metadata = dict(target.extraction.metadata_json or {})
        metadata["field_extraction"] = {
            "cache_key": {
                "content_sha256": target.content_sha256,
                "extractor_version": self.extractor.version,
            },
            "cache_status": "MISS",
            "reason_code": "DOCUMENT_FIELD_EXTRACTION_FAILED",
            "error": error,
        }
        target.extraction.metadata_json = metadata
        self.session.flush()

    def _set_cache_metadata(
        self,
        target: ExtractionTarget,
        *,
        status: str,
        source_extraction_id: UUID | None,
    ) -> None:
        metadata = dict(target.extraction.metadata_json or {})
        metadata["field_extraction"] = {
            "cache_key": {
                "content_sha256": target.content_sha256,
                "extractor_version": self.extractor.version,
            },
            "cache_status": status,
            "cache_source_extraction_id": (
                str(source_extraction_id) if source_extraction_id is not None else None
            ),
        }
        target.extraction.metadata_json = metadata
