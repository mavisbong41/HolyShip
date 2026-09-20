# Phase 7 API Verification

**Date:** 2026-09-20
**Branch:** `phase7` (Phase R repair pushed as `c713384`)

## Automated verification

| Check | Result |
|---|---|
| Phase R polling + product API + provider + exporter focused tests | 30 passed, 1 existing Starlette/httpx deprecation warning |
| Phase R polling suite including PostgreSQL checkpoint test | 20 passed, 1 skipped because `HOLYSHIP_TEST_DATABASE_URL` is unset |
| Full repository test collection | 221 passed, 60 skipped (database-dependent), 1 existing deprecation warning |
| PostgreSQL product/checkpoint integration tests | Skipped: `HOLYSHIP_TEST_DATABASE_URL` is unset; no PostgreSQL/Docker/Podman executable is available |
| Python compileall | Passed for `backend/app`, `backend/tests`, and `scripts` |
| Alembic heads | `20260920_0012 (head)` |
| SQLAlchemy PostgreSQL compilation | Queue and count statements compile successfully |
| `git diff --check` | Passed |
| Phase 7 trace | Not PASS: `ING-08` remains TODO because its PostgreSQL persistence evidence is skipped |
| Live `scripts/demo.sh` | Blocked: no shell/API/PostgreSQL service; direct Python demo reached connection-refused health failure |
| Full `make check`/evaluation | Failed at required database prerequisite; `DATABASE_URL` and `HOLYSHIP_TEST_DATABASE_URL` are unset |
| Push | Passed: `c713384` is on `origin/phase7` |

## Safety checks

- Product GET paths compose persisted rows only; they do not invoke readers, OCR, extractors, resolution providers, or comparison services.
- Product schemas omit AI request payloads, prompts, cache identities, and credentials.
- Microsoft Graph support is an adapter-only payload mapper with no SDK, OAuth, or network dependency.
- Phase R adds only additive migration `20260920_0012_ingestion_checkpoints`; no Phase 0–6 processing tables or semantics were changed.
- No runtime path reads `ground_truth.json` or private evaluator answers.

## Phase R continuous-ingestion evidence

- Unit tests cover three source listings (`A/B`, `A/B`, `A/B/C`), restart with
  persisted fake state, zero duplicate attachment reads, bounded backoff
  (`1s`, `2s`, then configured `60s`), and reset after success.
- FastAPI lifespan tests cover disabled-by-default startup and a configured
  one-shot initial sync. Runtime shutdown uses an event-aware sleeper so a
  60-second poll interval does not delay shutdown.
- `SqlAlchemyPollingStateStore` and migration `20260920_0012` are implemented,
  but the PostgreSQL checkpoint-restart test was skipped because
  `HOLYSHIP_TEST_DATABASE_URL` is unset. This is the remaining trace/gate
  blocker, not a claimed database pass.

## Remaining verification

Run the PostgreSQL integration/checkpoint tests, apply migration `20260920_0012`, start the API, execute `scripts/demo.sh`, and run the repository's full check/evaluation gates in a service-enabled environment. Until then the final phase status is blocked by environment verification, not by a claimed passing database gate.

## Service-backed re-verification — 2026-09-20

The historical blocked result above is retained. The same `phase7` checkout was then verified against the repository PostgreSQL service using three isolated databases (`holyship_dev`, `holyship_test`, `holyship_eval`). Docker Desktop was running PostgreSQL 16.15 in the existing `holyship-postgres-1` Compose service with a healthy status and host port `5432`.

### Migration and PostgreSQL tests

- `python -m alembic heads` → `20260920_0012 (head)`.
- A clean isolated dev schema upgraded through `20260920_0012`; live inspection confirmed `ingestion_checkpoints` and its checkpoint/error columns.
- Focused Phase 7 PostgreSQL/API/polling suite → 23 passed, 1 warning, 0 skipped when the three URLs were configured.
- Full repository collection after resetting only the dedicated test schema → 284 passed, 0 failed, 0 skipped, 1 existing Starlette/httpx deprecation warning.

### ING-08 live sequence

The DB-backed polling coordinator was exercised with a real PostgreSQL state store:

| Poll | Source | Submitted | Skipped | Attachment reads | Result |
|---|---|---:|---:|---:|---|
| 1 | A, B | 2 | 0 | 2 | A/B completed; checkpoint persisted |
| 2 | A, B | 0 | 2 | 0 | no reader, extraction, comparison, OCR, or AI rerun |
| Restart | persisted DB state | 0 | 2 | 0 | checkpoint survived a new worker lifecycle |
| 3 | A, B, C | 1 | 2 | 1 | only C processed; checkpoint advanced to C |

Backoff evidence passed at `1s`, `2s`, capped `60s`, followed by reset after success. The PostgreSQL checkpoint-restart test also executed rather than being skipped. `ING-08` is now PASS in `docs/requirements_matrix.md`.

### Live API and safety checks

- Real Uvicorn HTTP server: `/api/health`, `/openapi.json`, all `/api/v1` routes, queue/detail/events/summary returned successfully.
- Queue filters `status`, `category`, `received_from`, `received_to`, and `has_mismatch` returned persisted results or a valid empty page; skip/limit bounds returned the documented 422 responses.
- A live container-count mismatch exposed exactly the seven canonical fields, SI/reference and BL/candidate values separately, and `MISMATCH` only for `container_count`. A live unresolved party-value case remained `UNRESOLVED`/`BLOCKED`, not a forced mismatch.
- GET purity was checked through the product GET regression test and persisted-only query paths. Direct PostgreSQL query counts were bounded: queue 3, detail 12, summary 2.
- Live reprocess requests for COMPLETED, AWAITING_DOCUMENTS, and BLOCKED cases returned 409; the FAILED-only success path passed in the PostgreSQL-backed API test suite.

### Defects found and corrected during verification

- `/api/v1/events` selected whole ranked subqueries and failed with `ValueError: too many values to unpack`; the query now selects the event/category/mismatch columns explicitly and has a PostgreSQL regression test.
- `scripts/demo_phase7.py` failed when run through the shell wrapper because its script execution context did not include the repository root; it now establishes the root import path and has a subprocess regression test.
- The required obvious prize-promotion demo message classified as `general_message`; the generalizable `win a prize` signal and a regression test now preserve the required `spam` result.

### Gate evidence

- `scripts/demo.sh` executed through Git Bash with the repository wrapper and returned `demo: PASS`: normal text SI/BL, XLSX, wrong document, scanned/image, legitimate `AWAITING_DOCUMENTS`, and spam scenarios all asserted final API states; events and summary also passed.
- Official persisted-results evaluation with `AI_ESCALATION_ENABLED=false` completed 520 public emails with 0 failed/0 unhandled. `reports/latest/submission.json` SHA-256 was `37b33169797c6aef6b781fbcbf1ba99cb92d3a8d96ac184235eeda167d2a4eab`.
- The official exporter path in `scripts/run_baseline.py` built the public submission from persisted classification/comparison/event rows, validated the public sample shape, and wrote `reports/latest/submission.json`; no second reader, extractor, OCR, AI, or comparison pass was invoked by export.
- `mingw32-make reliability` → 14 passed. `mingw32-make perf` → PASS; final Phase 7 check evaluation recorded 16.351s / 31.803 emails/s, p50 `0.034048s`, p95 `0.141978s`, with peak RSS unavailable by declared dependency design.
- `mingw32-make check-fast` → PASS: 34 passed plus compileall and diff check. The first full-test attempt encountered stale test-schema DDL collision; after resetting only `holyship_test`, the full collection passed 284/0/0. This was not reproduced in the clean rerun.
- `mingw32-make trace PHASE=7` → PASS: 103 PASS, 0 TODO, 0 FAIL. `mingw32-make check PHASE=7` → PASS: 284 tests passed, clean evaluation passed, reliability passed, perf/eval passed, and trace passed. No scoreboard call was made.
