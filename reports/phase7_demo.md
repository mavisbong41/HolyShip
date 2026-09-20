# Phase 7 Live Demo Report

**Date:** 2026-09-20
**Branch:** `phase7`
**Entry point:** `scripts/demo_phase7.py`

## Intended workflow

```text
GET /api/health
  ↓
POST /api/v1/sync/initial
  ↓
GET /api/v1/emails
  ↓
GET /api/v1/emails/{id}
  ↓
POST /api/v1/ingestion/email  (awaiting-documents message)
POST /api/v1/ingestion/email  (non-comparison message)
  ↓
GET /api/v1/events
GET /api/v1/summary
```

The script uses only supported HTTP APIs. It does not insert database rows or read private reference data. Persisted document scenarios are selected from the public bundle; new-message scenarios use the generic incoming-email endpoint.

## Scenarios

- Initial backlog sync with a generated job identifier and sync counters.
- Existing public-bundle case selected by `external_message_id` search (`email_001` in the demo bundle) and an SI-vs-BL comparison case, including all seven canonical fields.
- `phase7-demo-awaiting-documents`: new document-comparison request without an attachment → `AWAITING_DOCUMENTS`.
- `phase7-demo-spam`: new non-comparison message → classification completes without document extraction.
- Polling-compatible processing events and aggregate summary.

## Execution result

**NOT RUN in this environment.** The repository has no available PostgreSQL service, Docker runtime, or configured `HOLYSHIP_TEST_DATABASE_URL`; therefore a FastAPI server could not be started against a real persisted store for this session.

Run from the repository root after starting the API and configuring a permitted database:

```powershell
python scripts/demo_phase7.py
```

Expected final line:

```text
demo: PASS
```

The script fails loudly on unavailable services or unexpected API responses.
