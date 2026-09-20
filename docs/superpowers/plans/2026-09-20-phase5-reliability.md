# Phase 5 Reliability and Performance Hardening Implementation Plan

> **For agentic workers:** Execute this plan inline on `phase5`; preserve the Phase 0–4 semantic contracts and stop at the Phase 5 gate.

**Goal:** Add bounded, observable reliability and performance controls to the existing ingestion-to-comparison backend without changing business semantics.

**Architecture:** Keep SQLAlchemy persistence authoritative for idempotency and use database uniqueness plus conflict recovery for duplicate protection. Run email-level work in bounded worker sessions, keep document extraction parallelism bounded, and retain all existing deterministic classification, role validation, extraction, normalization, and comparison behavior. Add small standard-library reliability primitives for retries/timeouts and versioned extraction-cache identity.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy, Alembic, PostgreSQL, pytest, standard-library `concurrent.futures`/`threading`/`urllib`.

## Global Constraints

- Final email categories remain exactly `document_comparison`, `new_si_request`, `invoice_query`, `general_message`, and `spam`.
- Comparison readiness and the seven canonical fields remain unchanged.
- SI remains the comparison reference and unresolved values remain unresolved.
- No Human Review UI, Phase 6 AI provider, Phase 7 frontend, or distributed task framework.
- No private evaluator data, per-email answer rules, filename-only role decisions, or hard-coded mailbox-size assumptions.
- New concurrency, retry, and timeout limits are configurable with safe defaults.
- `implement.md`, reliability/performance reports, migrations, tests, and real validation results must be updated before completion.

---

### Task 1: Establish baseline evidence and reliability test contracts

**Files:**
- Create: `backend/tests/test_phase5_reliability.py`
- Create: `backend/tests/test_phase5_retry_timeout.py`
- Modify: `docs/superpowers/plans/2026-09-20-phase5-reliability.md`

**Interfaces:**
- Tests define `retry_call`, `run_with_timeout`, `RetryPolicy`, and bounded `OrganizerHttpSource` behavior.
- PostgreSQL-only tests define the intended database semantics for duplicate ingestion, resume, cache versioning, and worker equivalence; they skip only when `HOLYSHIP_TEST_DATABASE_URL` is absent.

- [ ] Record the Phase 4 branch/status, `check-fast` baseline, existing evaluation metrics, and SHA-256 submission fingerprint in the Phase 5 reports.
- [ ] Add failing unit tests for finite retry success/exhaustion, retryable-vs-deterministic failures, timeout conversion, malformed semantic output, and Unicode/zero-byte/large-input isolation.
- [ ] Add skipped PostgreSQL regression tests for concurrent duplicate ingestion, repeat sync idempotency, single-worker/parallel semantic equivalence, restart/resume, cache version invalidation, and SI-success/BL-failure preservation.
- [ ] Run the focused new tests and confirm they fail because the Phase 5 APIs/behavior are not present.

### Task 2: Add bounded retry, timeout, configuration, and HTTP-source controls

**Files:**
- Create: `backend/app/core/reliability.py`
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/ingestion/sources.py`
- Modify: `.env.example`
- Test: `backend/tests/test_phase5_retry_timeout.py`

**Interfaces:**
- `RetryPolicy(max_attempts: int, backoff_seconds: float, timeout_seconds: float | None)` validates finite positive bounds.
- `retry_call(operation, *, policy, is_retryable, sleep=time.sleep)` retries only permitted technical failures and raises the final error with attempt diagnostics.
- `run_with_timeout(operation, timeout_seconds)` returns the operation result or raises a bounded `TimeoutError` while daemonizing the helper thread.
- `OrganizerHttpSource` accepts configured timeout/retry settings and retries transient HTTP/network failures only.

- [ ] Implement the smallest standard-library retry/timeout primitives needed by the failing tests.
- [ ] Apply them to organizer JSON/attachment retrieval without retrying 4xx business/resource failures.
- [ ] Add configuration for `SYNC_MAX_WORKERS`, `ORGANIZER_HTTP_TIMEOUT_SECONDS`, `RETRY_MAX_ATTEMPTS`, `RETRY_BACKOFF_SECONDS`, and `SEMANTIC_RESOLVER_TIMEOUT_SECONDS` with safe defaults.
- [ ] Run focused retry/timeout/source tests and then the relevant existing source tests.
- [ ] Commit and push the coherent retry/timeout checkpoint.

### Task 3: Harden persistence identities, duplicate ingestion, and resume

**Files:**
- Create: `backend/alembic/versions/20260920_0009_phase5_idempotency.py`
- Modify: `backend/app/storage/models.py`
- Modify: `backend/app/storage/repositories.py`
- Modify: `backend/app/storage/transitions.py`
- Modify: `backend/app/sync/service.py`
- Modify: `backend/app/core/config.py`
- Test: `backend/tests/test_phase5_reliability.py`
- Test: `backend/tests/test_storage_models.py`
- Test: `backend/tests/test_sync_service.py`

**Interfaces:**
- Persist `source_content_hash`/attempt diagnostics for processing jobs and classification results.
- Add uniqueness for `(email_id, job_type, source_content_hash)`, `(email_id, source_content_hash, classifier_version)`, and attachment identity `(email_id, source_reference)`.
- Add durable document content identity and extraction-cache identity, preserving existing rows through nullable/additive migration defaults.
- `SyncService.sync(..., max_workers, session_factory)` uses one session per worker and resumes only incomplete technical states; completed and business-blocked emails remain idempotently skipped.

- [ ] Add failing repository/integration tests demonstrating two sessions cannot create duplicate logical graph records.
- [ ] Add conflict-safe insert/re-fetch paths using savepoints and `IntegrityError` handling; do not rely on process-local locks.
- [ ] Add bounded email-level concurrency with a bounded in-flight window and per-case failure isolation.
- [ ] Add restart/resume handling for interrupted technical states and bounded retry attempt metadata.
- [ ] Preserve changed-message behavior as a new version while keeping unchanged messages skipped.
- [ ] Run focused persistence tests and PostgreSQL tests when the configured test database exists.
- [ ] Commit and push the idempotency/concurrency checkpoint.

### Task 4: Make materialization, extraction cache, comparison, and resolver boundaries restart-safe

**Files:**
- Create: `backend/alembic/versions/20260920_0010_phase5_cache_identity.py` if the schema split requires it
- Modify: `backend/app/documents/materialization.py`
- Modify: `backend/app/extraction/service.py`
- Modify: `backend/app/comparison/service.py`
- Modify: `backend/app/comparison/persistence.py`
- Modify: `backend/app/storage/repositories.py`
- Modify: `backend/app/core/reliability.py`
- Test: `backend/tests/test_phase5_reliability.py`
- Test: `backend/tests/test_phase3_parallel_cache_postgres.py`
- Test: `backend/tests/test_phase4_comparison_postgres.py`

**Interfaces:**
- Extraction cache identity is at least `(content_sha256, extractor_version)` and never reuses a stale version.
- Materialization reuses the same attachment/content document and extraction graph after interruption.
- Semantic resolver failures, malformed return values, and timeouts become structured `UNRESOLVED` outcomes rather than process-wide failures.

- [ ] Add failing cache-race/version tests and resolver failure tests before changing production code.
- [ ] Persist/recover cache claims with database uniqueness; copy field evidence without discarding raw values or document provenance.
- [ ] Reuse complete current extraction rows and persisted materialization on restart.
- [ ] Wrap injected semantic resolver calls with the configured timeout and validate returned structured output.
- [ ] Preserve successful SI work when BL extraction fails and retain a structured terminal reason.
- [ ] Run focused extraction/comparison tests and the Phase 5 reliability suite.
- [ ] Commit and push the materialization/cache checkpoint.

### Task 5: Instrument, measure, document, and gate Phase 5

**Files:**
- Modify: `backend/app/sync/service.py`
- Modify: `scripts/run_baseline.py`
- Modify: `Makefile`
- Create: `reports/phase5_reliability.md`
- Create: `reports/phase5_performance.md`
- Optional create: `reports/phase5_scale.md`
- Modify: `reports/latest/eval.md`
- Modify: `reports/history.csv`
- Modify: `implement.md`
- Test: `backend/tests/test_phase5_reliability.py`

**Interfaces:**
- Sync reports expose wall time, per-email p50/p95 where measurable, worker count, retry count, cache hits/misses, and unhandled exception count.
- `make check-fast` includes fast Phase 5 reliability tests; `make check` includes all applicable reliability/evaluation/performance/trace gates without requiring a scoreboard endpoint.

- [ ] Add deterministic semantic snapshots and repeat-run fingerprint checks that ignore UUID/timestamp ordering metadata.
- [ ] Update baseline/evaluation metrics from real `SyncReport` values rather than hard-coded external-call counts.
- [ ] Run the full Windows-compatible `mingw32-make check-fast` and `mingw32-make check` equivalents, recording unavailable PostgreSQL/docker/scoreboard checks as `NOT VERIFIED`.
- [ ] Repeat the evaluator-coupling and secret scan, run `git diff --check`, review changed files, and confirm local/remote `phase5` heads match.
- [ ] Update `implement.md` and both required reports with actual commands, metrics, limitations, and checkpoint history.
- [ ] Commit and push the final documentation/gate checkpoint.

