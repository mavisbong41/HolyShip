# HolyShip

HolyShip ingests shipping-operation email, classifies it, materializes SI and draft BL documents, extracts seven canonical fields, compares them deterministically, and exposes the persisted workflow through a React Dashboard and Outlook Add-in. Actionable blocked cases can be corrected through an auditable Human Review workflow without changing original extraction evidence.

## Local setup

1. Copy `.env.example` to `.env` and keep `holyship_dev`, `holyship_test`, and `holyship_eval` as three separate PostgreSQL databases.
2. Install backend dependencies into a virtual environment from `backend/requirements.txt`.
3. Install client dependencies with `npm ci` in `frontend/` and `outlook-addin/`.
4. Apply migrations with `python -m alembic upgrade head`.
5. Start the API with `python -m uvicorn backend.app.main:app --reload --port 8000`.
6. Start the Dashboard with `npm --prefix frontend run dev`.
7. Start the Outlook Add-in HTTPS development server with `npm --prefix outlook-addin run dev`.

The participant bundle belongs only in `data/bundle/`. Private evaluator answers and `data_v2` must never be placed in the repository or read by application code.

## Validation

```text
make check-fast PYTHON=<path-to-venv-python>
make check PHASE=F PYTHON=<path-to-venv-python>
```

The full root check covers backend tests, isolated evaluation, reliability, traceability, Dashboard typecheck/tests/build, and Outlook Add-in typecheck/tests/build. See `docs/human_review.md`, `docs/product_ui.md`, and `docs/dashboard_api_contract.md` for product contracts.
