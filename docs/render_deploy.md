# Render + Neon Deployment

This guide deploys HolyShip with:

- Frontend: Render Static Site
- Backend: Render Web Service
- Database: Neon PostgreSQL

## 1. Data Folder

The demo dataset lives in:

```text
data/bundle
```

The backend Docker image copies it to:

```text
/app/data/bundle
```

Set this backend environment variable on Render:

```ini
ORGANIZER_BUNDLE_PATH=/app/data/bundle
```

## 2. Neon

Create a Neon project and database, then copy the direct connection string.

Use SQLAlchemy psycopg format:

```ini
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST/DBNAME?sslmode=require
```

## 3. Render Backend

Create a Render Web Service from this repository.

Settings:

```text
Runtime: Docker
Dockerfile Path: backend/Dockerfile
Health Check Path: /api/health
```

Environment variables:

```ini
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST/DBNAME?sslmode=require
ORGANIZER_BUNDLE_PATH=/app/data/bundle
CORS_ALLOWED_ORIGINS=https://YOUR_FRONTEND.onrender.com,http://localhost:5173,http://127.0.0.1:5173
INITIAL_SYNC_ON_STARTUP=false
CONTINUOUS_POLLING_ENABLED=false
AI_ESCALATION_ENABLED=false
AI_PROVIDER=disabled
AI_MODEL=none
```

After deploy, verify:

```text
https://YOUR_BACKEND.onrender.com/api/health
https://YOUR_BACKEND.onrender.com/api/v1/summary
```

## 4. Render Frontend

Create a Render Static Site from this repository.

Settings:

```text
Root Directory: frontend
Build Command: npm install && npm run build
Publish Directory: dist
```

Environment variable:

```ini
VITE_API_BASE_URL=https://YOUR_BACKEND.onrender.com/api/v1
```

After the frontend URL is created, return to the backend service and update:

```ini
CORS_ALLOWED_ORIGINS=https://YOUR_FRONTEND.onrender.com,http://localhost:5173,http://127.0.0.1:5173
```

Redeploy the backend after changing CORS.

## 5. Initial Sync

Open:

```text
https://YOUR_FRONTEND.onrender.com
```

Click `Initial Sync`, or run:

```bash
curl -X POST https://YOUR_BACKEND.onrender.com/api/v1/sync/initial \
  -H "Content-Type: application/json" \
  -d '{"source":"static"}'
```

Expected summary after the public demo bundle is processed:

```json
{
  "total_emails": 520,
  "completed_count": 317,
  "awaiting_documents_count": 91,
  "human_review_open_count": 112
}
```

## 6. Common Checks

If the frontend shows `Failed to fetch`, check:

```ini
VITE_API_BASE_URL=https://YOUR_BACKEND.onrender.com/api/v1
CORS_ALLOWED_ORIGINS=https://YOUR_FRONTEND.onrender.com
```

If `Initial Sync` returns zero emails, check that `data/bundle` is present in the repository and that the backend has:

```ini
ORGANIZER_BUNDLE_PATH=/app/data/bundle
```
