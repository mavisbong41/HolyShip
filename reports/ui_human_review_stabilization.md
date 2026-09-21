# UI and Human Review stabilization evidence

This report records the deliberate 2026-09-21 scope expansion and its executable validation. The original SCP-01 and SCP-02 seed wording remains in the matrix and is owner-waived; the active requirements are HR-01 through HR-09 and UI-01.

## Architecture evidence

- The Dashboard and Outlook Add-in are backend API clients; deterministic classification, extraction, and comparison remain backend-owned.
- Outlook links use `?email=<backend-email-id>` and the Dashboard loads that exact ID through `/api/v1/emails/{id}`.
- Human Review corrections are separate rows and recomparison produces a new comparison result.
- `AWAITING_DOCUMENTS` and ordinary `FAILED` states are excluded from automatic Human Review creation.

## Validation record

- Safe branch: `codex/ui-human-review-stabilization`; starting HEAD `7000558834868a91c4e8ad9995c24bee8fa59378`.
- Dev migration: `20260920_0008` → `20260921_0013`; 520 email IDs, 250 attachment IDs, 520 classification IDs, and 21 historical review IDs survived with unchanged identity hashes. Historical reviews are `LEGACY:OPEN`.
- `pg_dump` was unavailable, so no pre-migration local backup was created.
- Focused Human Review/scope tests: 12 passed. Isolated legacy-row migration test: 1 passed.
- Full backend: 299 passed, 0 failed, 0 skipped, 1 warning. Reliability: 14 passed.
- Dashboard: typecheck PASS, 9 tests PASS, production build PASS.
- Outlook Add-in: typecheck PASS, 57 tests PASS, production build PASS; no React `act(...)` warning.
- `make check-fast`: PASS. `make check PHASE=F`: PASS.
- Phase F trace: 114 PASS, 0 TODO, 0 FAIL, 2 owner-waived; 251 cited evidence tests passed.
- Clean eval run 1: 520 emails in 23.308s. Clean eval run 2: 520 emails in 23.722s. Submission SHA-256 both runs `37B33169797C6AEF6B781FBCBF1BA99CB92D3A8D96AC184235EEDA167D2A4EAB`; byte-identical YES. The final root check independently regenerated the same hash.
- Category distribution: BL_COMPARISON 203, SI_REQUEST 141, INVOICE_QUERY 84, GENERAL 66, SPAM 26.
- Public status distribution: OK 317, NEEDS_REVIEW 203, MISMATCH 0.
- Internal operational distribution: COMPLETED 317, AWAITING_DOCUMENTS 91, BLOCKED 112; active automated Human Review cases 112.
- Dev remained at `20260921_0013` with unchanged row counts/identity hashes after tests and eval. Test and eval database identities remained `holyship_test` and `holyship_eval`.

## Evaluator blocker

The organizer archive exists at `C:\Users\User\Downloads\sdoc-hackathon-docker.zip`; its public README documents `docker compose up --build`, `GET /health`, and `POST /submit` on port 8080. No private answer content was opened. Windows has no installed/discoverable `docker` executable, Ubuntu WSL reports that Docker is unavailable, and `http://localhost:8080/health` is unreachable. The downloaded Docker Desktop installer is not a running Docker installation. Consequently no compose service was started and no score POST was performed.
