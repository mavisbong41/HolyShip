# Phase 5 Reliability Report

Date: 2026-09-20  
Branch: `phase5`  
Base: `feature/email-classification` at `67f00f2`

## Evidence summary

| Scenario | Expected | Observed | Status | Evidence |
|---|---|---|---|---|
| Finite retry success/exhaustion | Transient failures retry finitely; deterministic failures do not | 3-attempt success, 3-attempt exhaustion, and no-retry deterministic tests passed | PASS | `backend/tests/test_phase5_retry_timeout.py` |
| Timeout boundary | Slow resolver returns structured unresolved without holding the batch | Timeout test returned `SEMANTIC_RESOLUTION_TIMEOUT` within the bound | PASS | `backend/tests/test_phase5_reliability.py` |
| Malformed resolver output | Invalid provider shape becomes unresolved | Returned `SEMANTIC_RESOLUTION_INVALID` | PASS | `backend/tests/test_phase5_reliability.py` |
| HTTP retry diagnostics | Retry transient 5xx with bounded backoff and record attempt type | 503 retried once; structured `HTTPError` event recorded | PASS | `backend/tests/test_phase5_retry_timeout.py` |
| Repeated initial sync | Same unchanged messages converge to one logical graph | PostgreSQL test added; live run unavailable | NOT VERIFIED | `backend/tests/test_phase5_reliability_postgres.py` |
| Concurrent duplicate ingestion | Two concurrent requests create one email/job/classification graph | Database-backed unique/conflict paths implemented; live run unavailable | NOT VERIFIED | Migration `20260920_0009`, PostgreSQL test |
| Restart/resume | Interrupted technical state completes without duplicate email/graph | Resume path and test added; live database unavailable | NOT VERIFIED | `SyncService`, PostgreSQL test |
| Single worker vs parallel | Semantic snapshots are equal | Bounded worker implementation and regression test added; live database unavailable | NOT VERIFIED | `SyncService`, PostgreSQL test |
| Cache same-version reuse | Exact bytes plus extractor version may reuse fields | Durable cache identity and metadata constraints compiled; live migration/cache test unavailable | NOT VERIFIED | Migration `20260920_0010`, existing Phase 3 tests |
| Cache version invalidation | Changed extractor version must recompute | Version remains part of lookup key; live PostgreSQL test unavailable | NOT VERIFIED | `DocumentExtractionRepository` |
| Database concurrency protections | Unique identities plus conflict recovery | ORM metadata contains the five Phase 5 identity constraints | PASS (metadata) / NOT VERIFIED (live DB) | `backend/tests/test_storage_models.py`, migrations |
| Failure isolation | One bad case cannot crash unrelated work | Existing reader/parser unit suite passed; database batch isolation unavailable | PASS (unit) / NOT VERIFIED (batch DB) | Existing reader tests, Phase 5 PostgreSQL tests |
| Evaluation unhandled exceptions | Zero process-wide exceptions | Existing Phase 4 artifact reports 0; Phase 5 clean evaluation was not runnable | NOT VERIFIED | `reports/latest/eval.json` baseline only |

## Database and restart notes

The Phase 5 persistence design uses PostgreSQL uniqueness as the final protection, not an in-memory lock. Insert paths use savepoints and re-fetch the winning row after an `IntegrityError`. New jobs and classifications carry the source content hash; attachment, document, and extraction-cache identities are versioned and additive.

The current host has no `.env`, `DATABASE_URL`, `HOLYSHIP_TEST_DATABASE_URL`, `HOLYSHIP_EVAL_DATABASE_URL`, PostgreSQL service, or Docker executable. Therefore the PostgreSQL-gated duplicate, resume, cache, and worker-equivalence scenarios are explicitly `NOT VERIFIED` here.

## Failure-injection matrix

| Input/failure | Handling | Status |
|---|---|---|
| Corrupt PDF | Composite reader returns structured `FAILED`/`UNREADABLE`/`PARTIAL` result | PASS in existing unit test |
| Zero-byte attachment | Materialization maps empty content to `CORRUPTED_ATTACHMENT` | NOT VERIFIED without PostgreSQL pipeline |
| Large text input | No arbitrary tiny rejection; standard reader path remains bounded by caller policy | NOT VERIFIED as a measured RSS test |
| Odd encoding | Reader boundary returns a structured document outcome rather than crashing the batch | NOT VERIFIED as a dedicated Phase 5 case |
| Unicode filename | UTF-8 filename boundary test passed | PASS |
| Parser exception | Materialization catches reader exception and persists `DOCUMENT_READER_FAILED` | Existing PostgreSQL test is skipped here |
| Transient DB failure | Retry classification is bounded for `OperationalError`; live fault injection unavailable | NOT VERIFIED |
| Resolver timeout | Structured unresolved result within timeout | PASS |
| Malformed resolver output | Structured unresolved result | PASS |
| SI succeeds / BL fails | Existing extraction service preserves completed side; live DB regression unavailable | NOT VERIFIED here |

## Tests and limitations

- `mingw32-make check-fast`: PASS, 34 tests, 0 failures, 1 warning.
- `python -m pytest backend/tests -q`: PASS, 175 passed, 47 skipped, 1 warning. The skips are PostgreSQL-gated.
- `mingw32-make check`: NOT VERIFIED; stopped before pytest because the required database URLs are not configured.
- `git diff --check`: PASS (only line-ending warnings from Git on Windows).
- Alembic migration files compile; applying them to a live database is NOT VERIFIED.
- `make score` was not called. No score-history entry was fabricated.
