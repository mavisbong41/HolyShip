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

The Dashboard also provides the active Human Review queue and detail workflow:

- filter and open current `OPEN` / `IN_REVIEW` cases;
- inspect the email, documents, seven SI/BL fields, overrides, and audit actions;
- claim a case, save a separate reviewer correction, resolve and recompare, or dismiss with a reason;
- open an email directly with `?email=<backend-email-id>` or a review with `?review=<review-case-id>`.

Reviewer corrections are sent to the backend override API. The Dashboard never edits extraction rows or decides comparison outcomes locally. `AWAITING_DOCUMENTS` remains an operational waiting state, while technical `FAILED` cases expose retry/reprocess rather than Human Review.
