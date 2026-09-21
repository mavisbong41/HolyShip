# HolyShip Outlook Add-in

Outlook task pane Add-in for the HolyShip shipping document verification system.  
Shows the HolyShip case status of the currently selected email directly inside Outlook.

## Visual Identity

The Add-in is the compact sibling of the HolyShip Dashboard:
- Same orange / grey / charcoal / white color tokens
- Same badge system and status semantics
- Same typography hierarchy (Inter)
- Same comparison table field labels
- Same backend enum values for all statuses and categories

---

## Stack

| Tool | Version |
|------|---------|
| TypeScript | ^5.9 |
| React | ^19 |
| Vite | ^7 |
| Office.js | CDN (appsforoffice.microsoft.com) |
| Vitest | ^3 |
| @testing-library/react | ^16 |

---

## Local Development

### 1. Install dependencies

```bash
cd outlook-addin
npm install
```

### 2. Set environment variables

Copy `.env.example` to `.env` and adjust:

```bash
cp .env.example .env
```

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_BASE_URL` | `http://localhost:8000/api/v1` | HolyShip backend URL |
| `VITE_DASHBOARD_BASE_URL` | `http://localhost:5173` | HolyShip Dashboard URL |

### 3. Start the dev server

```bash
npm run dev
```

The task pane is served at: **https://localhost:3200/taskpane.html**

Open this URL in a browser to develop/inspect the UI without an Outlook runtime.  
The Office.js context will be unavailable, so the "Not in HolyShip" state will render.

### 4. Ensure the backend is running

```bash
# From the repo root
mingw32-make dev PYTHON=py
```

---

## Sideloading into Outlook (Local Dev)

> **Note**: The Vite development server uses its basic local HTTPS certificate so
> the manifest and task pane use the same secure origin.

### Outlook on the Web (OWA / Microsoft 365)

1. Open Outlook on the Web.
2. Open **Settings** → **View all Outlook settings** → **Mail** → **Customize actions** → **Add-ins**.
3. Or navigate directly to: `https://outlook.office.com/mail/options/mail/manageAddIns`
4. Click **+ Add a custom add-in** → **Add from file**.
5. Upload `outlook-addin/manifest.xml`.
6. Open any email → the **HolyShip** button appears in the ribbon.

### Outlook Desktop (Windows)

1. Open Outlook desktop.
2. Go to **File** → **Manage Add-ins** (or **Get Add-ins**).
3. Click **My add-ins** tab.
4. Click **Add a custom add-in** → **Add from file**.
5. Upload `outlook-addin/manifest.xml`.
6. Restart Outlook if needed.
7. Open any email → **HolyShip** button appears in the message ribbon.

> **Important**: The manifest currently points to `https://localhost:3200`.
> The Vite dev server must be running for the task pane to load.

---

## Project Structure

```
outlook-addin/
  src/
    api/
      client.ts         — Backend API client (emailDetail, search, findByMessageId)
    office/
      OfficeContextProvider.ts   — Real Office.js context reader
      FakeContextProvider.ts     — Test/dev fake context (no Office.js needed)
      IdentityAdapter.ts         — Resolves Outlook message → HolyShip case
    components/
      TaskPane.tsx       — Main task pane UI (full state machine)
      ComparisonTable.tsx — 7-field SI vs BL comparison table
      StatusBadge.tsx    — Shared badge component
    types/
      product.ts         — Backend product API types
      context.ts         — Office context abstraction types
    lib/
      labels.ts          — Presentation label mappings (same as Dashboard)
      config.ts          — Dashboard URL / deep-link helpers
    styles/
      tokens.css         — HolyShip design tokens
      pane.css           — Task pane styles
    main.tsx             — Entry point (Office.onReady + React mount)
  tests/
    fixtures.ts          — Test fixtures for all case states
    identity.test.ts     — IdentityAdapter + FakeContextProvider tests
    TaskPane.test.tsx    — TaskPane state rendering tests
    ComparisonTable.test.tsx — Comparison table tests
    labels.test.ts       — Label mapping + config tests
  taskpane.html          — HTML entry point (loads Office.js CDN)
  manifest.xml           — Outlook Add-in manifest (dev sideload)
  .env.example           — Environment template
  vite.config.ts
  tsconfig.json
  package.json
```

---

## Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Start the HTTPS Vite dev server (port 3200) |
| `npm run build` | TypeScript check + production build |
| `npm run typecheck` | TypeScript check only |
| `npm run test` | Run unit tests |
| `npm run check` | typecheck + test + build (CI gate) |

---

## Architecture

### Separation of concerns

```
Office.js (Outlook runtime)
         ↓
OfficeCurrentMailContextProvider  ← reads item metadata
         ↓
IdentityAdapter                   ← resolves message → HolyShip case
         ↓
API Client (client.ts)            ← talks to HolyShip backend
         ↓
TaskPane (React)                  ← renders results
```

### No business logic in the client

The Add-in is a **client only**. It does not:
- Classify emails
- Extract shipping fields
- Compare SI vs BL
- Normalize values
- Determine MATCH/MISMATCH/UNRESOLVED locally

All decisions come from the backend.

---

## Identity Limitation (Current Branch)

> See also: `docs/outlook_addin_identity.md`

This branch does **not** implement real Microsoft Graph ingestion.

Identity resolution uses:
1. **Internet Message-ID** — most reliable, works when the backend preserved the header
2. **Subject text search** — low-confidence fallback

Live Graph OAuth identity linkage is **deferred** to the next integration branch.

When no match is found, the task pane shows:
> *This email has not been processed by HolyShip, or it could not be identified.*

---

## Deferred Work (Next Branch)

- Real Microsoft Graph OAuth
- Live Outlook mailbox ingestion
- Live Graph identity linkage (accurate message-id → case mapping)
- Add-in-native Human Review write actions (the Dashboard now provides the active review workflow)
- Field correction backend
- Replacement SI/BL upload
- Production AppSource submission

---

## Tests

Tests run without any Office.js runtime using `FakeCurrentMailContextProvider`.

```bash
npm run test
```

Test files:
- `tests/identity.test.ts` — context providers and identity adapter
- `tests/TaskPane.test.tsx` — all UI states
- `tests/ComparisonTable.test.tsx` — comparison table rendering
- `tests/labels.test.ts` — label mappings and config

---

## Production Notes

- Replace `https://localhost:3200` in `manifest.xml` with your production HTTPS domain
- Update `VITE_API_BASE_URL` and `VITE_DASHBOARD_BASE_URL` for the target environment
- Ensure backend CORS allows the Add-in origin
- Do **not** commit real credentials or Graph tokens
