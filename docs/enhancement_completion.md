# Enhancement completion and production setup

## Current implementation status

- Dashboard and Outlook use the same persisted multi-action Review Plan API. AI and reviewer-authored manual items can be approved, edited, rejected, or removed before one explicit confirmation. Confirmation writes the selected overrides once and runs exactly one re-comparison; retry after `APPLY_FAILED` does not duplicate overrides.
- Manual category records (`resolved_at_stage=human_override`) remain the effective category in queue, detail, AI context, and later processing. Subsequent machine predictions remain classification history.
- Microsoft Graph reply sending is server-side, confirmation-gated, response-verified, failure-preserving, and idempotent.
- Microsoft Graph delta pages ingest unknown messages through the shared `SyncService`, reconcile read/category/folder/delete/restore state on the same record, and persist `nextLink`/`deltaLink` in `ingestion_checkpoints`. The cursor advances only after the page commits; a failed page retains the prior cursor and an error for retry.
- Graph subscriptions are created, renewed before expiration, and recreated after expiration. The webhook validates `clientState` and only wakes delta reconciliation; notification order and duplication never mutate mailbox state directly.
- Smart Reply summary/draft/refine calls Gemini only through `SecureAIGateway` with purpose-specific disclosure and deterministic fallback.
- Queue sorting is server-side before pagination. Official-label and performance tools remain isolated from production logic.

## Database migration and verification

Run:

```powershell
python -m alembic upgrade head
```

The current head is `20260925_0019`. Revision `0018` adds Review Plans; `0019` adds durable provider cursor and checkpoint metadata. On 2026-09-25 an empty isolated PostgreSQL test database upgraded through the complete chain to `0019` successfully. PostgreSQL integration tests verify Review Plan constraints/history, lifecycle persistence, cursor restart behavior, and duplicate protection.

## Microsoft Graph deployment

See [microsoft_graph_setup.md](microsoft_graph_setup.md). Graph send, delta ingestion, lifecycle reconciliation, subscription management, and notification validation are implemented and mock/integration verified. They are **not live-tenant verified** because tenant credentials were unavailable.

## AI privacy

`ENTERPRISE_PRIVACY_MODE` defaults to `true`. Minimum Necessary Disclosure is enforced and tested:

- summary: bounded relevant email excerpt, comparison status, and affected field names;
- draft: human-approved key points;
- refine: approved points, current draft, and the human instruction.

Attachment bodies, unrelated field values, full audit history, reviewer identity, and credentials are not automatically disclosed. Raw request/response payloads are not persisted; audit records retain sanitized metadata such as purpose, provider/model, disclosed categories, payload hash/size, status, and latency.

## Evaluation evidence

The current code was run repeatedly from clean isolated evaluation databases over all 520 public emails. Each generated the same submission SHA-256 (`D59FA8DA8651265D6FA08F2076DCA4ECEBEA6CA66CCC038F2161D85B8B28D4C1`). The latest run processed 520/520 successfully with 0 failures and 0 unhandled exceptions in 20.291 seconds (25.627 emails/s), P50 0.043128 s and P95 0.160608 s.

Official ground truth is unavailable. No accuracy, precision, recall, F1, or confusion matrix was calculated or inferred. The authorized command remains:

```powershell
make official-eval GROUND_TRUTH=C:\secure\ground_truth.json
```

`reports/latest/performance_paths.json` and `.md` distinguish measured deterministic results from unmeasured AI results. No Gemini credential was available, so live Gemini performance is **NOT VERIFIED**; gateway/provider behavior is covered with injected/mock tests.

## Data lifecycle production readiness

Safe defaults remain `DATA_LIFECYCLE_DRY_RUN=true` and `DATA_LIFECYCLE_RUN_ON_STARTUP=false`. Before activation, run cleanup manually in dry-run mode, review the protected-record summary, approve retention values and backups, then explicitly enable apply/scheduling. Human Review history, overrides, comparison history, and audit events remain protected.

## External verification limits

- Microsoft Graph behavior is implemented and mock/integration verified, but not verified against a live tenant.
- Live Gemini latency and acceptance behavior were not measured because credentials were unavailable.
- Official quality metrics remain blocked by withheld organizer labels.
