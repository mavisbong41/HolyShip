# Scope decision: Dashboard, Outlook Add-in, and Human Review

Date: 2026-09-21  
Authority: project owner

The project owner explicitly expanded the current product scope to include the React Dashboard, the Outlook Add-in, and an active Human Review workflow. This supersedes the earlier milestone restriction recorded by seed requirements SCP-01 and SCP-02 without erasing those historical requirements.

The following boundaries remain authoritative:

- deterministic backend classification, readiness, document routing, extraction, and comparison semantics remain the source of truth;
- the Dashboard consumes backend APIs and does not reproduce business decisions locally;
- the Outlook Add-in is a presentation and integration client, not a processing engine;
- Human Review is additive and auditable: reviewer overrides are stored separately, original extraction evidence and historical comparisons remain immutable, and recomparison creates a new result;
- `AWAITING_DOCUMENTS` is not an active review case, and ordinary technical `FAILED` states use retry/reprocess rather than Human Review;
- private evaluator data, `ground_truth.json`, and `data_v2` must never enter UI or runtime logic.

SCP-01 and SCP-02 therefore remain in the requirements matrix with their original wording and are marked `WAIVED` under the protocol’s human-authorized waiver mechanism. The current behavior is traced by the added HR and UI requirements instead.
