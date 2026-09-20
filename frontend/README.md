# HolyShip Dashboard

React + TypeScript + Vite Dashboard for the HolyShip product API.

## Setup

```bash
cd frontend
npm install
```

Create local env from `.env.example` when needed:

```bash
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

## Run

```bash
npm run dev
```

## Quality

```bash
npm run typecheck
npm run test
npm run build
npm run check
```

## Backend Contract

The Dashboard uses `/api/v1` endpoints documented in `../docs/dashboard_api_contract.md`.

It does not perform frontend business comparison logic. `MATCH`, `MISMATCH`, and `UNRESOLVED` are displayed from the backend comparison result.
