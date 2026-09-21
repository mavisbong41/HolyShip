# HolyShip Backend

Batch 1 is limited to email ingestion and email classification. The current backend foundation includes source-independent ingestion models and PostgreSQL persistence for emails, attachments, processing jobs, classification results, and classification human-review cases.

## Install

```powershell
py -m pip install -r backend\requirements.txt
```

## PostgreSQL

Start the application database:

```powershell
docker compose up -d postgres
```

Run migrations:

```powershell
py -m alembic upgrade head
```

Start the backend:

```powershell
py -m uvicorn backend.app.main:app --reload --port 8000
```

## Tests

Run tests that do not require a live database:

```powershell
py -m pytest -q
```

Repository integration tests require a PostgreSQL test database:

```powershell
$env:HOLYSHIP_TEST_DATABASE_URL="postgresql+psycopg://holyship:holyship@localhost:5432/holyship_test"
py -m pytest backend\tests\test_repositories_postgres.py -q
```

## Phase 7 product API and demo

The legacy `/api/*` endpoints remain available. Product clients should use the
explicit `/api/v1/*` contract:

```text
GET  /api/v1/emails                         dashboard queue
GET  /api/v1/summary                        dashboard counts
GET  /api/v1/emails/{email_id}              unified email detail
GET  /api/v1/emails/{email_id}/detail       explicit detail alias
GET  /api/v1/human-review                   reviewer queue
GET  /api/v1/human-review/{review_id}       reviewer detail
POST /api/v1/human-review/{review_id}/claim claim an open case
POST /api/v1/human-review/{review_id}/overrides persist a separate field correction
POST /api/v1/human-review/{review_id}/resolve resolve and create a new comparison
POST /api/v1/human-review/{review_id}/dismiss dismiss with an audited reason
GET  /api/v1/events                         polling-compatible updates
POST /api/v1/sync/initial                   initial backlog sync
POST /api/v1/ingestion/email                simulated/generic inbound email
POST /api/v1/emails/{email_id}/reprocess    technical failures only
```

`GET` endpoints compose only persisted email, document, extraction,
comparison, review, AI provenance, and processing-event rows. They do not run
readers, OCR, extraction, AI resolution, or comparison again. Queue filters
include `status`, `category`, `comparison_readiness`, `needs_review`,
`review_status`, `comparison_state`, `has_mismatch`, `search`,
`received_from`, and `received_to`; pagination uses `skip` and `limit`
(maximum 500).

With PostgreSQL running and the API started on port 8000, run the live demo:

```powershell
python -m uvicorn backend.app.main:app --port 8000
python scripts/demo_phase7.py
```

The demo uses the public bundle through `/api/v1/sync/initial`, then exercises
queue/detail/comparison state and submits new awaiting-document and
non-comparison messages through `/api/v1/ingestion/email`.

