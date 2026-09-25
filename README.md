<div align="center">

<h1>🚢 HolyShip</h1>

<p><strong>An end-to-end shipping document verification platform that turns incoming email into a trusted SI–BL verification workflow.</strong></p>

<p><strong>Team:</strong> NJHL — Wong Jia Hui · Bong Zi Shan · Lee Mei Shuet · Christ Ting Shin Ling · Gan Rui En</p>

<p><a href="https://holyship.onrender.com/">🌐 Dashboard</a> · <a href="https://holyship-backend.onrender.com">⚙️ Backend API</a> · <a href="https://holyship-backend.onrender.com/docs">📘 API Docs</a> · <a href="https://canva.link/kflchdm6qu1pslv">📑 Presentation Slides</a> · <a href="https://youtu.be/mnfbrDJyGaQ">🎥 Demo Video</a></p>

<p><strong>Outlook Add-in Demo Account:</strong> <code>captain.holyship@outlook.com</code> · Password: <code>captain12</code></p>

</div>

<br>

> HolyShip automates what is certain, escalates what is uncertain, and keeps humans in control of business-critical decisions.

---

## Table of Contents

- [At a Glance](#at-a-glance)
- [Product overview](#product-overview)
- [Outlook and Dashboard](#outlook-and-dashboard)
- [Structured Human Review](#structured-human-review)
- [Enterprise privacy and AI security](#enterprise-privacy-and-ai-security)
- [Architecture](#architecture)
- [Validation and reliability](#validation-and-reliability)
- [Setup and running locally](#setup-and-running-locally)
- [Live prototype / demo](#live-prototype--demo)

---

## At a Glance

- **End-to-end** — Outlook email in, verified SI–BL result out.
- **Human-controlled AI** — zero silent auto-apply; every action is approved, edited, or rejected by a person.
- **Enterprise privacy** — minimum-necessary AI disclosure, routed through a server-side gateway only.
- **Evidence-backed** — 520 / 520 public emails processed with zero technical failures, plus a frozen 40-case labeled stress test measuring classification, discrepancy detection, and escalation.

---

## Product overview

HolyShip is an operational workflow connecting Outlook, a shared backend, a Web Dashboard, and auditable Human Review. It is more than a document comparison tool: it receives email, understands the requested action, waits for the right documents, verifies SI and Draft BL content, and supports an approved response workflow.

```text
Incoming Email
→ Classification
→ Readiness Check
→ Document Processing
→ Seven-field Extraction
→ Normalization
→ SI–BL Comparison
→ Human Review when necessary
→ Human-approved correction
→ Re-comparison
→ Reply / action
→ Audit Trail
```

The core philosophy is **deterministic first → AI only where useful → human control for business-critical decisions**. Clear cases stay on deterministic paths. Semantic AI is used selectively for difficult residual comparisons and reviewer assistance. Uncertain cases remain `UNRESOLVED` or enter Human Review; AI proposes actions, while people approve, edit, or reject them.

---

## What the system verifies

Only these five canonical email categories are used:

- `document_comparison`
- `new_si_request`
- `invoice_query`
- `general_message`
- `spam`

Only `document_comparison` continues into comparison readiness and SI–BL processing. Readiness is explicit: `READY_FOR_COMPARISON`, `AWAITING_DOCUMENTS`, or `UNRESOLVED`.

The SI is the reference document and the BL is the document being checked. The comparison contract contains exactly seven fields:

| Canonical field | Meaning |
| --- | --- |
| `shipper` | Shipping party / exporter |
| `consignee` | Receiving party |
| `notify_party` | Notify party |
| `port_of_loading` | Origin port |
| `port_of_discharge` | Destination port |
| `container_count` | Number of containers |
| `gross_weight_kg` | Gross shipment weight |

Raw values, canonical values, normalized values, labels, confidence, and source evidence are preserved where available. Missing or uncertain values are not silently converted into matches or mismatches.

---

## Layered comparison

```text
L0 — safe/basic normalization
↓
L1 — field-specific deterministic normalization
↓
L2 — semantic resolution only if still uncertain
```

Each field ends as `MATCH`, `MISMATCH`, or `UNRESOLVED`. Definite mismatches are valid completed results; uncertainty is never forced into a confident answer. The high-volume path is deterministic, with L2 reserved for plausible semantic equivalence that survives L0/L1.

---

## Outlook and Dashboard

### Outlook Add-in — the email-level action workspace

From the email currently open in Outlook, users can:

- inspect the current HolyShip case, SI vs Draft BL values, and mismatch fields;
- perform Human Review and work with a multi-action Review Plan;
- approve, edit, reject, or remove proposed actions;
- add manual corrections, confirm implementation, and trigger shared re-comparison;
- manually correct the email category and inspect review history;
- prepare a reply summary, edit reply key points, generate or refine a draft, manually edit it, and explicitly confirm sending.

Outlook is a full email-level workflow surface, not merely an "Open Dashboard" link.

### Web Dashboard — the operations-level control centre

The Dashboard provides overview metrics, the email queue, filtering and sorting, case detail, seven-field comparison, discrepancies, Human Review, Review Plans, manual correction, review history, lifecycle state, and audit trail.

Outlook and Dashboard read and write the same persisted backend case state. Business classification, extraction, normalization, and comparison logic remain backend-owned.

<!-- Add screenshots here to speed up first impressions, e.g.:
![Dashboard overview](docs/screenshots/dashboard-overview.png)
![Human Review Plan](docs/screenshots/human-review-plan.png)
-->

---

## Structured Human Review

Human Review uses a structured multi-action Review Plan:

```text
AI / reviewer proposes actions
→ Review Plan
→ Approve / Edit / Reject each action
→ Add manual corrections if needed
→ Explicit final confirmation
→ Apply approved human overrides
→ Re-compare once
→ Updated result
```

Multiple actions may exist in one plan. AI suggestions are never automatically applied: only approved items are implemented. Reviewer-authored corrections are supported, original extracted values remain unchanged, comparison history is preserved, and a failed re-comparison does not erase the human decision. **Zero silent auto-apply.**

---

## Smart Reply

Smart Reply is an assisted, confirmation-gated workflow:

```text
Email / Case Context
→ Summary
→ Editable Key Points
→ Draft
→ Refine
→ Manual Edit
→ Explicit Send Confirmation
→ Outlook Send
```

AI-extracted key points are editable. Draft generation uses the approved key points, AI cannot send automatically, and send status is recorded only after the provider confirms success. A deterministic fallback is available when Gemini is unavailable.

---

## Microsoft Graph integration

HolyShip implements server-side Microsoft Graph integration for reply sending, delta synchronization, new-message ingestion, delete and restore, read/unread state, category synchronization, durable delta cursors, webhook handling, subscription renewal and expiration handling, and duplicate/out-of-order notification safety.

```text
Graph Webhook
→ wake-up signal
→ Delta Synchronization
→ HolyShip Backend
→ Dashboard / Outlook
```

Webhook notifications are wake-up signals, not the mailbox source of truth. Delta reconciliation remains the convergence mechanism. The integration is covered by mock and PostgreSQL integration tests; live tenant verification is deployment-dependent and requires organization-specific Microsoft app registration and credentials.

---

## Enterprise privacy and AI security

### Enterprise Privacy Mode

Production-default privacy controls keep provider access server-side.

### Secure AI Gateway

All production Gemini calls pass through the centralized server-side `SecureAIGateway`. Frontend clients never receive Gemini API keys or Microsoft Graph secrets.

### Minimum Necessary Disclosure

The gateway sends only the smallest evidence needed for a specific task. For a port comparison, it may send:

```text
Field: port_of_loading
SI: Port Klang
BL: PORT KLANG, MALAYSIA
```

rather than the entire email, SI, BL, and unrelated customer information. Deterministic paths avoid unnecessary external AI disclosure. Raw prompts and provider envelopes are not durably persisted; sanitized audit metadata records purpose, provider/model, disclosed categories, payload hash/size, status, and latency. No formal certification or compliance claim is made here.

---

## Architecture

```text
Microsoft Outlook / Email Sources
              ↓
      Ingestion + Sync
              ↓
       Classification
              ↓
     Comparison Readiness
              ↓
      Document Router
        ↙           ↘
       SI           BL
        ↘           ↙
       Seven-field Extraction
              ↓
      Layered Comparison
        L0 → L1 → L2
              ↓
 MATCH / MISMATCH / UNRESOLVED
              ↓
        Human Review
              ↓
      Structured Review Plan
              ↓
     Human-approved Override
              ↓
          Re-compare
              ↓
    Dashboard + Outlook
              ↓
       Smart Reply / Audit
```

Gemini access follows:

```text
Gemini calls → Secure AI Gateway → Minimum Necessary Disclosure
```

The backend supports source-independent ingestion, initial backlog sync, idempotent processing, lazy attachment loading, controlled concurrency, document hashing and extraction caching, content-based SI/BL role validation, structured extraction, and persisted processing/audit state.

---

## Technical stack

- **Backend:** Python, FastAPI, Pydantic Settings, SQLAlchemy, Alembic, PostgreSQL, `pypdf`, `python-docx`, `openpyxl`, and Tesseract-compatible OCR integration for scanned-document fallback.
- **Dashboard:** React 19, TypeScript, Vite, Vitest, Testing Library.
- **Outlook Add-in:** React, TypeScript, Vite, Office.js, Vitest, Testing Library.
- **Integration:** Microsoft Graph through a backend adapter and delta/checkpoint services; Gemini through the Secure AI Gateway.

---

## Project structure

```text
backend/       FastAPI application, domain pipeline, persistence, migrations, tests
frontend/      React operations Dashboard
outlook-addin/ Outlook task pane client and manifest
docs/          API, setup, scope, and requirements documentation
reports/       Evaluation, reliability, performance, and audit evidence
scripts/       Demo, evaluation, and validation utilities
data/          Public bundle and permitted local fixtures
```

---

## Setup and running locally

> Commands below are shown for Windows PowerShell. On macOS/Linux, replace `py` with `python3`, use forward slashes in paths (e.g. `backend/requirements.txt`), and use `pip3` if `pip` is not aliased.

### 1. Backend and PostgreSQL

```powershell
py -m pip install -r backend\requirements.txt
docker compose up -d postgres
py -m alembic upgrade head
py -m uvicorn backend.app.main:app --reload --port 8000
```

Migrations are managed with Alembic; `alembic upgrade head` always applies the latest schema. Backend integration tests use isolated development, test, and evaluation PostgreSQL databases.

### 2. Dashboard

```powershell
cd frontend
npm install
npm run dev
```

Use `VITE_API_BASE_URL=http://localhost:8000/api/v1` in `frontend/.env` when the default is not suitable.

### 3. Outlook Add-in

```powershell
cd outlook-addin
npm install
npm run dev
```

The local task pane is served at `https://localhost:3200/taskpane.html`. Copy `.env.example` to `.env` and configure `VITE_API_BASE_URL` and `VITE_DASHBOARD_BASE_URL`. Sideload `outlook-addin/manifest.xml` into Outlook on the Web or Outlook Desktop; the manifest currently targets the local HTTPS dev server.

### 4. Optional Microsoft Graph production configuration

Configure Graph secrets only on the backend. See [`docs/microsoft_graph_setup.md`](docs/microsoft_graph_setup.md) for tenant registration, least-privilege mailbox access, webhook validation, durable cursor behavior, subscription renewal, and deployment checks.

```text
MICROSOFT_GRAPH_ENABLED=true
MICROSOFT_GRAPH_TENANT_ID=<tenant-id>
MICROSOFT_GRAPH_CLIENT_ID=<application-id>
MICROSOFT_GRAPH_CLIENT_SECRET=<secret>
MICROSOFT_GRAPH_MAILBOX=<mailbox-user-id-or-address>
MICROSOFT_GRAPH_SYNC_ENABLED=true
MICROSOFT_GRAPH_WEBHOOK_URL=https://<public-host>/api/v1/graph/notifications
MICROSOFT_GRAPH_WEBHOOK_CLIENT_STATE=<random-high-entropy-value>
```

### 5. Optional Gemini configuration

Gemini is optional. Production requests are routed through the backend gateway, with `ENTERPRISE_PRIVACY_MODE=true` by default. Keep provider credentials in server-side environment configuration only; do not place them in Dashboard or Outlook variables.

### Main demo flow

The primary workflow is automatic: initial sync loads the existing backlog, unprocessed emails are queued, results are persisted progressively, and new messages can enter through Graph or the generic ingestion endpoint. A demo can use:

```powershell
python scripts/demo_phase7.py
```

The backend product API includes `POST /api/v1/sync/initial`, `POST /api/v1/ingestion/email`, `GET /api/v1/emails`, `GET /api/v1/summary`, `GET /api/v1/human-review`, `POST /api/v1/human-review/{review_id}/resolve`, and polling-compatible `GET /api/v1/events`.

---

## Validation and reliability

### Public dataset evaluation

The latest clean deterministic evaluation reports:

| Measure | Result |
| --- | ---: |
| Public dataset emails | 520 |
| Coverage | 520 / 520 |
| Successful processing | 520 |
| Technical failures | 0 |
| Unhandled exceptions | 0 |
| Retries | 0 |
| Reader failures | 0 |
| OCR failures | 0 |
| Provider failures | 0 |

Public output:

| Outcome | Count |
| --- | ---: |
| `OK` | 454 |
| `MISMATCH` | 46 |
| `NEEDS_REVIEW` | 20 |

There were 5 unresolved comparisons. This is not the same metric as the 20 Human Review cases: Human Review also includes document and workflow exceptions that are actionable without being unresolved comparisons.

### Independent labeled stress test

Because the public participant dataset does not expose official ground-truth labels, HolyShip also uses a separate team-authored labeled stress test to evaluate decision correctness. The 40 cases were defined and labeled before execution, frozen as version `v1`, and evaluated without changing labels based on system output. The cases deliberately cover classification ambiguity, formatting-only differences, true and multi-field discrepancies, missing or contradictory evidence, wrong or missing documents, document-routing/OCR scenarios, and Human Review escalation decisions.

| Measure | Result |
| --- | ---: |
| Dataset version | `v1` |
| Cases | 40 |
| Classification accuracy | 97.5% |
| Classification macro F1 | 0.9683 |
| Discrepancy detection TP / FP / TN / FN | 17 / 0 / 121 / 2 |
| Discrepancy detection precision / recall / F1 | 1.0000 / 0.8947 / 0.9444 |
| Human Review escalation TP / FP / TN / FN | 7 / 2 / 30 / 1 |
| Human Review escalation precision / recall / F1 | 0.7778 / 0.8750 / 0.8235 |
| Unsafe confident errors | 0 |
| Correct safe abstentions | 3 |

No unsafe confident errors were observed in this frozen stress test: when HolyShip lacked sufficient evidence, it preferred an unresolved or review path rather than forcing an unsupported definite decision. This is a result for this benchmark only, not a universal safety claim.

The benchmark also exposed remaining edge cases in bilingual extraction, conservative entity handling, and contradictory readiness interpretation. These failures remain visible in the evaluation report rather than being removed from the benchmark. Stress-test v1 was frozen before execution and fingerprinted with SHA-256 `afd7b7ac9e81cf3bab1ab1bfc179ae4e45a554d7d326d1b7effce9ca3eced1d1`.

Run the independent benchmark with:

```powershell
make stress-eval
```

Detailed outputs are available in [`reports/latest/stress_test_metrics.md`](reports/latest/stress_test_metrics.md) and [`reports/latest/stress_test_metrics.json`](reports/latest/stress_test_metrics.json).

Repeated clean evaluation produced the same output fingerprint:

```text
D59FA8DA8651265D6FA08F2076DCA4ECEBEA6CA66CCC038F2161D85B8B28D4C1
```

Identical clean-run output provides evidence of reproducible deterministic behavior.

### Automated engineering checks

| Surface | Verification |
| --- | --- |
| Backend | 410 / 410 tests passed |
| Dashboard | 35 / 35 tests passed; typecheck PASS; production build PASS |
| Outlook Add-in | 74 / 74 tests passed; typecheck PASS; production build PASS |

### Current deterministic public-dataset benchmark

```text
520 emails
20.291 seconds
25.627 emails / second
P50: 43.128 ms
P95: 160.608 ms
```

These values describe the deterministic benchmark, not live Gemini-assisted performance. AI-assisted performance is **not measured** because the benchmark environment did not use live Gemini credentials.

The public participant bundle does not expose the organizer's official ground-truth labels. HolyShip therefore does not report official challenge accuracy. The independent stress-test metrics above are team-authored benchmark results, not organizer scores. The repository also includes an isolated evaluation tool that can calculate official-style metrics when authorized ground truth is supplied.

---

## Data lifecycle

Operational retention support includes configurable cleanup, scheduled execution, safe dry-run mode, and protection for Human Review history, overrides, comparison history, and audit evidence.

```text
DATA_LIFECYCLE_DRY_RUN=true
DATA_LIFECYCLE_RUN_ON_STARTUP=false
```

---

## Live prototype / demo

The current public Dashboard deployment is available at [holyship.onrender.com](https://holyship.onrender.com/). The backend API and interactive documentation are available at [holyship-backend.onrender.com](https://holyship-backend.onrender.com) and its [OpenAPI docs](https://holyship-backend.onrender.com/docs).

See the [presentation slides](https://canva.link/kflchdm6qu1pslv) and [demo video](https://youtu.be/mnfbrDJyGaQ) for the end-to-end product walkthrough.

---

## Challenge submission summary

HolyShip is an end-to-end shipping email workflow that classifies incoming messages, checks document readiness, extracts seven SI–BL fields, and produces deterministic `MATCH`, `MISMATCH`, or `UNRESOLVED` outcomes. Rather than forcing every case into an AI decision, HolyShip separates definite results from uncertainty and escalates only what requires human judgment — routing that uncertainty into a structured Human Review Plan where people approve, edit, or reject proposed actions before one re-comparison. Enterprise Privacy Mode, Secure AI Gateway routing, minimum-necessary disclosure, preserved source evidence, and audit history keep AI useful without making it authoritative. Smart Reply supports editable key points, draft refinement, manual editing, and explicit send confirmation.

<!-- ~104 words — confirm this against the competition's submission word limit before final export. -->

---

## Contributors

- Wong Jia Hui
- Bong Zi Shan
- Lee Mei Shuet
- Christ Ting Shin Ling
- Gan Rui En



> **Verify in stages. Explain the evidence. Keep humans in control.**
