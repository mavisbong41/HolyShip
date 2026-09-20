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
