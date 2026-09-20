# Phase 7 Product-Facing API Implementation Plan

> **For agentic workers:** This plan is executed inline in the current Phase 7 branch. Each task follows a failing-test → minimal implementation → focused verification loop.

**Goal:** Add a stable, persisted-data-only product API and reproducible live demo while preserving legacy routes and Phase 6 processing semantics.

**Architecture:** Add explicit v1 Pydantic schemas and a product query/composition module. Use SQL aggregate/window subqueries for queue/summary and eager/bulk loading for detail/review. Keep POST v1 routes as thin aliases over the existing `SyncService`; GET routes never invoke processing.

**Tech Stack:** Python 3.14, FastAPI, Pydantic, SQLAlchemy/PostgreSQL, pytest, existing ingestion/sync/submission adapter.

## Global Constraints

- Final categories remain exactly `document_comparison`, `new_si_request`, `invoice_query`, `general_message`, `spam`.
- Required fields remain exactly the seven canonical fields and SI remains the reference.
- Preserve `MATCH`, `MISMATCH`, `UNRESOLVED`; never map `BLOCKED` to mismatch.
- Preserve legacy `/api/*` behavior and do not add a migration unless persistence is genuinely required.
- GET product endpoints read persisted results only and do not call document readers, OCR, extractors, resolvers, or comparison recomputation.
- No secrets, prompts, provider credentials, private evaluator data, or cache identities are exposed.

### Task 1: Product schemas and queue/summary contracts

**Files:**
- Create: `backend/app/api/product_schemas.py`
- Create: `backend/app/api/product_queries.py`
- Test: `backend/tests/test_phase7_product_api.py`

- [ ] Write failing tests for queue pagination/filter validation, stable ordering, and summary fields.
- [ ] Implement explicit queue/summary enums and response models.
- [ ] Implement aggregate/window query helpers for latest classification/comparison/review and attachment counts.
- [ ] Run focused tests and the inherited API subset.

### Task 2: Unified detail/review/evidence contracts

**Files:**
- Modify: `backend/app/api/product_schemas.py`
- Modify: `backend/app/api/product_queries.py`
- Test: `backend/tests/test_phase7_product_api.py`

- [ ] Write failing tests for documents, extraction fields, seven comparison fields, evidence, processing timeline, review context, AI provenance, partial rows, and 404s.
- [ ] Implement select-inloaded detail composition and bounded AI/review queries.
- [ ] Keep canonical field ordering and preserve nullable/partial states.
- [ ] Run focused tests and PostgreSQL integration tests when configured.

### Task 3: v1 router aliases and polling events

**Files:**
- Modify: `backend/app/api/router.py`
- Modify: `backend/app/api/schemas.py`
- Test: `backend/tests/test_phase7_product_api.py`

- [ ] Write failing route tests for v1 queue, summary, detail, review, events, sync, ingestion, and technical reprocess errors.
- [ ] Add the v1 routes with FastAPI validation and additive legacy compatibility.
- [ ] Ensure event rows are product-shaped and do not expose raw logs.
- [ ] Run focused route tests and OpenAPI startup smoke test.

### Task 4: Provider/demo/export documentation

**Files:**
- Create: `backend/app/ingestion/graph_source.py`
- Create: `backend/tests/test_phase7_provider_contract.py`
- Create: `scripts/demo_phase7.py`
- Create: `reports/phase7_demo.md`
- Modify: `backend/README.md`, `.env.example`, `implement.md`, `docs/requirements_matrix.md`

- [ ] Write failing contract test for a fake Microsoft Graph payload mapped through the source interface without credentials.
- [ ] Add the isolated adapter skeleton and deterministic demo client.
- [ ] Document startup, routes, scenarios, limitations, and actual validation results.
- [ ] Run the demo against a live local API when PostgreSQL is available.

### Task 5: Final gates and handoff

**Files:**
- Modify: `implement.md`, `reports/phase7_api_audit.md`, `reports/phase7_demo.md`

- [ ] Run compile, focused Phase 7 tests, inherited `check-fast` equivalent, full `make check` equivalent, PostgreSQL integration, migration inspection, and security/overfit scans.
- [ ] Verify no GET path invokes processing, no secret leakage, and Phase 6 runtime wiring remains configured.
- [ ] Review diff, commit stable Phase 7 work, push `origin/phase7` if network permits, and report exact evidence.
