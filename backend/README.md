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
$env:HOLYSHIP_TEST_DATABASE_URL="postgresql+psycopg://holyship:holyship@localhost:5432/holyship"
py -m pytest backend\tests\test_repositories_postgres.py -q
```

