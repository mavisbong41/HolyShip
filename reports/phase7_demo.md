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

`POST /api/v1/sync/initial` is synchronous in this repair. Its `progress`
object is the completed request snapshot; the returned job identifier is an
audit/request identifier, not a background-job polling promise.

The script uses only supported HTTP APIs. It does not insert database rows or read private reference data. Persisted document scenarios are selected from the public bundle; new-message scenarios use the generic incoming-email endpoint.

## Scenarios

- Initial backlog sync with a generated job identifier and sync counters.
- New incoming text SI-vs-BL comparison submitted through the API with base64 attachment content, including all seven canonical fields.
- New incoming XLSX SI-vs-BL comparison submitted through the API.
- New incoming wrong-document pair, expected to stop with `WRONG_DOCUMENT_TYPE` / `BLOCKED`.
- New incoming scanned/image-only PDF pair, expected to exercise the routed scanned-document path without fabricating a comparison.
- `phase7-demo-awaiting-documents`: new document-comparison request without an attachment → `AWAITING_DOCUMENTS`.
- `phase7-demo-spam`: new non-comparison message → classification completes without document extraction.
- Polling-compatible processing events and aggregate summary.

## Execution result

**NOT RUN in this environment.** The repository has no available PostgreSQL
service, Docker/Podman runtime, shell executable for `scripts/demo.sh`, or
configured `HOLYSHIP_TEST_DATABASE_URL`; therefore a FastAPI server could not
be started against a real persisted store for this session. Direct execution
of `python scripts/demo_phase7.py` failed at `GET /api/health` with Windows
connection-refused (`WinError 10061`).

Run from the repository root after starting the API and configuring a permitted database:

```powershell
python scripts/demo_phase7.py
# or, from a POSIX-compatible shell:
sh scripts/demo.sh
```

Expected final line:

```text
demo: PASS
```

The script fails loudly on unavailable services or unexpected API responses.

## Service-backed execution — 2026-09-20

The historical unavailable-service result above is retained. With the existing repository Compose PostgreSQL service healthy and the actual Uvicorn API running on `127.0.0.1:8000`, the wrapper was executed through Git Bash:

```text
export PATH=/usr/bin:/bin:$PATH
cd /d/dunno/0.AVERIS/HolyShip
./scripts/demo.sh
```

The wrapper returned exit code 0 and `demo: PASS`. It processed the 520-email public backlog, then asserted these incoming scenarios through HTTP:

- normal text SI/BL → `document_comparison`, persisted comparison state;
- XLSX SI/BL → `document_comparison`, persisted comparison state;
- readable wrong document → `document_comparison` / `BLOCKED` with `WRONG_DOCUMENT_TYPE` evidence;
- scanned/image-only PDF → `document_comparison` / `BLOCKED` with inconclusive document validation;
- legitimate no-attachment future draft request → `document_comparison` / `AWAITING_DOCUMENTS`;
- obvious prize promotion → `spam` / `COMPLETED` without document processing.

The script also asserted observable processing events and a persisted summary. The run emitted expected pypdf warnings for malformed public sample PDFs, but the wrapper completed successfully and did not inject final results into the database or access private reference data.
