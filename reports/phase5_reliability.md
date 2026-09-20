# Phase 5 Reliability Report

Date: 2026-09-20  
Branch: `phase5`  
Base: `feature/email-classification` at `67f00f2`

## Verification environment

- Temporary local PostgreSQL 18.6 binary cluster on `127.0.0.1:55432`.
- Separate databases: `holyship_dev`, `holyship_test`, and `holyship_eval`, all owned by the non-superuser `holyship`.
- No repository production infrastructure was changed. The temporary server was used only for isolated verification.

## Evidence summary

| Scenario | Observed result | Status | Evidence |
|---|---|---|---|
| Clean Alembic upgrade | All migrations applied through `20260920_0010` | PASS | `python -m alembic -c alembic.ini upgrade head` |
| Phase 5 migration downgrade/upgrade | Downgrade to `20260920_0008`, then upgrade to `20260920_0010` succeeded | PASS | Alembic output and live schema query |
| Repeated initial sync | Two runs converged to one email/job/classification graph per source message | PASS | `test_repeated_initial_sync_converges_without_duplicate_graph` |
| Provider-message idempotency | Repeated provider identity resolves to one logical email/case | PASS | PostgreSQL reliability suite |
| Concurrent duplicate ingestion | Two concurrent ingesters produced one email, one job, and one classification; no uncaught error | PASS | `test_concurrent_duplicate_ingestion_creates_one_logical_case` |
| Restart/resume | Persisted `CLASSIFYING` work resumed to `COMPLETED` without a new email or duplicate graph | PASS (service-level restart simulation) | `test_restart_resumes_interrupted_classification_without_new_email` |
| Single worker vs parallel | Database snapshots and official submission output matched | PASS | Phase 5 PostgreSQL suite plus worker evaluation |
| Cache same-version reuse | Exact content/version reused safely with current document provenance | PASS | `test_sha_version_cache_reuses_payload_with_current_document_provenance` |
| Cache version invalidation | Changed extractor version recomputed instead of reusing stale extraction | PASS | Same PostgreSQL cache test |
| Cache concurrency/identity | PostgreSQL cache/pipeline suite passed; extraction graph remained distinct and consistent | PASS | `backend/tests/test_phase3_parallel_cache_postgres.py` (6 passed) |
| Failure isolation | Full suite and reliability suite passed; malformed/corrupt/parser/resolver/partial-side paths remained structured | PASS | Full pytest plus Phase 5 reliability tests |
| Evaluation unhandled exceptions | `0` in clean evaluations and worker comparisons | PASS | `reports/latest/eval.json` |

## Target results

- `mingw32-make reliability`: **14 passed**.
- `mingw32-make test`: **222 passed**, 1 pre-existing HTTP-client deprecation warning, 0 skipped.
- `python -m pytest backend/tests/test_phase3_parallel_cache_postgres.py -q`: **6 passed**.
- `python -m pytest backend/tests/test_phase5_retry_timeout.py backend/tests/test_phase5_reliability.py -q`: **11 passed**.
- Full `mingw32-make check`: **PASS**; its test, evaluation, reliability, performance, and trace stages all completed successfully.

## Targeted defect found and fixed

The first live PostgreSQL run exposed that the duplicate-protection insert flushed an `EmailMessageRecord` before assigning its required `content_hash`. The repository now initializes `content_hash` in the insert object, preserving the existing savepoint/conflict-recovery design. The focused PostgreSQL suite then passed 4/4, including concurrent ingestion.

## Remaining limits

- The restart test is a persisted-state/service-level resume simulation, not an OS process kill and restart.
- Peak RSS was not measured because the repository has no cross-platform process-metrics dependency.
- A real provider cursor/polling deployment remains outside Phase 5.
- No Phase 5 scoreboard call was made.
