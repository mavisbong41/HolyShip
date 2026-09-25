# HolyShip Enhancement Requirements

**Document Type:** Technical Product & Implementation Requirements  
**Project:** HolyShip  
**Status:** Enhancement Specification  
**Primary Audience:** Development Team  
**Scope:** Outlook Integration, Human-in-the-Loop AI, End-to-End Workflow, Enterprise Security, Synchronisation, Reliability & Performance  
**Out of Current Scope:** Multi-user / RBAC pending mentor confirmation

---

# 1. Objective

This document defines the next enhancement phase for HolyShip.

The goal is to evolve HolyShip from a dashboard-centric document verification system into a fully integrated, enterprise-ready workflow where:

- Outlook and the Dashboard can both perform operational actions.
- Both interfaces stay synchronised through the backend as the single source of truth.
- AI assists users but never silently changes business-critical data.
- Human Review can convert AI suggestions into approved structured overrides.
- Approved changes trigger re-comparison automatically.
- Reply generation becomes an end-to-end, human-controlled workflow.
- Email lifecycle status in HolyShip remains aligned with Outlook.
- Enterprise document data is protected through minimum-necessary disclosure and a secure AI gateway.
- Reliability and performance are quantitatively evaluated over the complete provided dataset.

---

# 2. Core Product Principles

## 2.1 Backend Is the Single Source of Truth

The Dashboard and Outlook Add-in must not maintain independent business state.

All classification, comparison, review, override, reply, synchronisation and audit events must be persisted through the backend.

```text
Outlook Add-in
       \
        -> HolyShip Backend / Database
       /
Dashboard
```

Changes made in either client must become visible in the other after synchronisation.

---

## 2.2 Human-in-the-Loop by Default

AI must never silently alter verified shipping data.

Required control model:

```text
AI proposes
    ↓
Human reviews
    ↓
Human edits if necessary
    ↓
Human confirms
    ↓
System applies approved override
    ↓
System re-compares
    ↓
Result + audit trail updated
```

No AI-generated correction may be auto-applied without explicit user confirmation.

---

## 2.3 Deterministic First, AI Only Where Necessary

HolyShip should use deterministic validation and comparison wherever possible.

Preferred decision order:

```text
Exact / deterministic rule
        ↓
Normalization
        ↓
Dictionary / known mappings
        ↓
Semantic AI resolution only when still unresolved
        ↓
Human Review when required
```

This supports reliability, performance, explainability and privacy.

---

# 3. Priority Overview

| Priority | Requirement Area | Status |
|---|---|---|
| P0 | Quantitative Reliability Evaluation | Required |
| P0 | End-to-End Workflow Completion | Required |
| P0 | AI-Assisted Human Review + Structured Implementation Plan | Required |
| P0 | Full Outlook Operational Workflow | Required |
| P0 | Outlook ↔ Dashboard State Synchronisation | Required |
| P0 | Delete / Restore / Email Status Synchronisation | Required |
| P1 | Enterprise Privacy Mode | Required |
| P1 | Secure AI Gateway | Required |
| P1 | Minimum Necessary Disclosure | Required |
| P1 | Smart Reply End-to-End Workflow | Required |
| P1 | Performance Evaluation | Required |
| P1 | Data Lifecycle / Scheduled Cleanup | Required |
| P2 | Outlook Manual Category Correction | Required |
| P2 | Advanced Filters / Sorting / History Views | Required |
| Deferred | Multi-user / Team Queue / RBAC | Pending mentor confirmation |

---

# 4. Canonical End-to-End Workflow

The target business workflow is:

```text
Incoming Outlook Email
        ↓
Synchronise into HolyShip
        ↓
Email Intent Classification
        ↓
Readiness Check
        ↓
Document Routing
        ↓
OCR / Parsing when required
        ↓
Seven-field Extraction
        ↓
Normalization
        ↓
SI–BL Comparison
        ↓
MATCH / MISMATCH / UNRESOLVED
        ↓
Human Review when needed
        ↓
AI Assistance / Proposed Plan
        ↓
Human Edit + Confirmation
        ↓
Apply Human-Approved Override
        ↓
RE-COMPARE
        ↓
Updated Result
        ↓
Optional Reply Workflow
        ↓
Human Confirm + Send
        ↓
Outlook / Dashboard Synchronisation
        ↓
Persistent Audit Trail
```

## Why Re-Compare Is Mandatory

Re-comparison must occur after an approved override.

Without re-comparison:

- the system may continue showing an outdated MISMATCH;
- Dashboard and Outlook may display inconsistent states;
- analytics may count resolved cases as unresolved;
- the Human Review workflow has no deterministic completion point.

Therefore:

> Every applied comparison-field override must trigger re-comparison of the affected case.

---

# 5. Outlook Add-in Enhancement

## 5.1 Goal

The Outlook Add-in must no longer act primarily as an "Open Dashboard" shortcut.

Users should be able to complete the same main review operations directly inside Outlook.

The Dashboard remains the broader operational control centre.

### Outlook role

Focused on the currently selected email / case.

### Dashboard role

Focused on all cases, monitoring, analytics, queue management and history.

---

## 5.2 Outlook Case View

For the selected email, Outlook should be able to display:

- HolyShip classification
- processing status
- readiness status
- comparison result
- mismatch count
- mismatch fields
- SI extracted values
- BL extracted values
- normalized values when relevant
- AI suggestion
- Human Review status
- previous human overrides
- review history
- reply status
- last synchronised timestamp

The Outlook experience should provide substantially the same case-level information as the Dashboard.

---

## 5.3 Outlook Direct Actions

Users must be able to perform the following without opening the Dashboard:

- inspect comparison results;
- inspect mismatch fields;
- open Human Review;
- request/view AI assistance;
- edit AI-proposed values;
- approve or reject individual suggested actions;
- confirm an implementation plan;
- apply approved overrides;
- trigger re-comparison;
- manually correct classification;
- view case history;
- generate reply summary;
- edit reply key points;
- regenerate a reply;
- refine the generated message;
- manually edit the reply;
- confirm before sending.

---

# 6. Outlook ↔ Dashboard Synchronisation

## 6.1 Single Shared State

Both clients must use backend state.

Example:

```text
User approves correction in Outlook
        ↓
Backend persists override
        ↓
Re-comparison runs
        ↓
Case becomes MATCH
        ↓
Dashboard reflects MATCH
```

And:

```text
User changes category in Dashboard
        ↓
Backend persists category override
        ↓
Outlook displays corrected category
        ↓
Outlook native category may also update
```

---

## 6.2 Synchronisation Requirement

The implementation mechanism may use webhook, Graph subscription, delta sync, polling fallback or another reliable mechanism.

The core product requirement is:

> HolyShip's email lifecycle status must remain consistent with Outlook.

Implementation technology is secondary to state correctness.

---

# 7. Email Lifecycle Synchronisation

At minimum, HolyShip should synchronise:

- email exists / deleted;
- restored;
- read / unread;
- Outlook category;
- last sync timestamp.

Where technically practical, also synchronise:

- folder movement;
- archive state.

---

# 8. Delete and Restore Behaviour

## 8.1 Delete

When an Outlook email is deleted:

1. HolyShip detects the deletion.
2. The email is marked `DELETED` or equivalent.
3. It disappears from normal active queues.
4. Historical processing data is preserved.
5. Human Review history is preserved.
6. Human overrides are preserved.
7. Comparison history is preserved.
8. Audit events are preserved.
9. The deletion itself becomes an audit event.

Do not hard-delete operational evidence merely because an email disappears from the Outlook inbox.

---

## 8.2 Restore

When a deleted Outlook email is restored:

1. HolyShip detects the restoration.
2. The record becomes active again.
3. Existing historical comparison/review data remains.
4. The email is visible again in the appropriate active views.
5. The restore action is audited.

The restored record must not be recreated as a completely unrelated duplicate if it can be matched to the original message identity.

---

# 9. Human Review AI

## 9.1 Goal

The AI assistant must evolve from a passive explanation tool into a structured Human Review assistant.

It must still remain advisory.

---

## 9.2 Structured AI Review Plan

The AI response should be converted into intuitive structured actions rather than only free-form text.

Each proposed action should support fields such as:

```json
{
  "field": "consignee",
  "current_value": "ABC Logistic",
  "proposed_value": "ABC Logistics",
  "reason": "Likely normalization / naming variation",
  "confidence": 0.91,
  "action": "REPLACE"
}
```

Exact schema may differ, but the interaction must support:

- current value;
- proposed value;
- reason;
- confidence where available;
- action type;
- approve;
- reject;
- edit.

---

## 9.3 User Editing

Before implementation, the user must be able to:

- edit proposed values;
- remove an action;
- reject an action;
- approve an action;
- add a manual correction if required.

The UX should be intuitive and form-based rather than requiring users to edit JSON.

---

## 9.4 Confirmation

After the user finalises the plan:

```text
Review Proposed Changes
        ↓
Edit / Accept / Reject
        ↓
Confirm Implementation
        ↓
Apply
```

A final confirmation step is required before modifying HolyShip's reviewed values.

---

# 10. Human Overrides

## 10.1 No Original Document Mutation

Applying a review plan must not silently rewrite original SI or BL source documents.

The approved value should be stored as a Human Review override / corrected canonical value.

Example conceptual model:

```text
source_value
normalized_value
ai_proposed_value
human_override_value
effective_value
```

The exact schema may differ.

---

## 10.2 Effective Value

For downstream comparison:

```text
if human_override_value exists:
    effective_value = human_override_value
else:
    effective_value = normalized/extracted value
```

The system must preserve the original extracted value for auditability.

---

# 11. Mandatory Re-Comparison

After approved changes are implemented:

1. persist human overrides;
2. record audit event;
3. re-run the relevant comparison;
4. calculate new result;
5. update MATCH / MISMATCH / UNRESOLVED status;
6. update Human Review status;
7. update Outlook;
8. update Dashboard;
9. update analytics.

The old comparison result must remain accessible in history where feasible.

---

# 12. Smart Reply: End-to-End Human-Controlled Workflow

## 12.1 Goal

Reply generation should become a controlled workflow rather than a one-click AI reply.

Target flow:

```text
Case / Email Context
        ↓
AI Summary
        ↓
AI Extracted Reply Key Points
        ↓
Human Reviews / Edits Key Points
        ↓
Generate Draft
        ↓
Refine
        ↓
Manual Edit
        ↓
Final Human Confirmation
        ↓
Send through Outlook
        ↓
Sync Sent Status
        ↓
Audit
```

---

## 12.2 Summary

The assistant should generate a concise case summary containing only important points.

Example:

```text
Customer requests a revised BL after a consignee correction.
Current case contains one unresolved consignee mismatch.
```

---

## 12.3 Editable Reply Key Points

AI must extract the intended reply facts / key points from the email and case.

Example:

```text
[✓] Acknowledge the discrepancy
[✓] Confirm consignee correction
[✓] State that revised BL will be prepared
[ ] Mention processing timeline
```

Users must be able to:

- edit a key point;
- remove a key point;
- add a key point;
- approve selected key points.

These approved key points become the basis of generated reply content.

---

## 12.4 Reply Generation

The draft must be generated from the approved key points and relevant case context.

AI must not introduce unsupported commitments or facts that were not present in approved context.

---

## 12.5 Refine Message

The user should be able to refine the reply after generation.

Examples:

- clearer;
- shorter;
- more professional;
- friendlier;
- more concise;
- grammar correction.

Users must also be able to manually edit the text directly.

---

## 12.6 Sending

AI must never automatically send the email.

Required flow:

```text
Generate
   ↓
Review
   ↓
Edit
   ↓
Final confirmation
   ↓
User explicitly clicks Send
```

Sending must be attributable to a user action.

The send event should be audited.

---

# 13. Email Classification and Manual Category Correction

## 13.1 Supported HolyShip Categories

Current canonical categories:

- `BL_COMPARISON`
- `SI_REQUEST`
- `INVOICE_QUERY`
- `GENERAL`
- `SPAM`

---

## 13.2 Manual Override

A user may correct a classification in Outlook or Dashboard.

After manual correction:

- the backend must store the human-selected category;
- subsequent AI processing must not silently overwrite it;
- the original AI category should remain in history;
- the change must be audited.

Conceptually:

```text
AI classification: GENERAL
Human override: BL_COMPARISON
Effective category: BL_COMPARISON
```

---

# 14. Outlook Native Categories

Where Microsoft Graph / Outlook integration permits, HolyShip categories should also map to Outlook native categories/tags.

Example:

```text
BL_COMPARISON
SI_REQUEST
INVOICE_QUERY
GENERAL
SPAM
```

Colour mapping may be configurable and is not a core logic dependency.

Manual category changes should remain consistent between Outlook and HolyShip where technically supported.

---

# 15. Outlook / Dashboard Filters and Sorting

At minimum, support operational filtering by:

- All
- Mismatch
- Needs Human Review
- Unresolved
- Reviewed / Completed
- Deleted
- History

Recommended additional filter where relevant:

- Awaiting Documents

Recommended sorting:

- newest first;
- oldest first;
- priority;
- status;
- category;
- last updated.

These filters are operational views and must not create conflicting business states.

---

# 16. Review History

Users should be able to inspect previously reviewed cases.

History should show, where available:

- original extracted value;
- AI-proposed value;
- human-edited value;
- final override;
- old comparison result;
- new comparison result;
- reviewer;
- timestamp;
- related reply/send action.

---

# 17. Enterprise Privacy Mode

## 17.1 Goal

Protect sensitive enterprise shipping data while still allowing Gemini-assisted processing when necessary.

Production should default to Enterprise Privacy Mode enabled.

Recommended behaviour:

```text
Production:
ENTERPRISE_PRIVACY_MODE=true

Development:
Configurable through environment settings
```

The mode should not depend on a casual end-user toggle.

---

# 18. Secure AI Gateway

All Gemini calls must pass through one controlled server-side gateway.

Do not allow frontend code or unrelated backend modules to make unrestricted Gemini requests.

Target architecture:

```text
Feature / Service
      ↓
Secure AI Gateway
      ↓
Purpose validation
      ↓
Data minimization
      ↓
Redaction / sanitization
      ↓
Policy checks
      ↓
Gemini
      ↓
Response validation
      ↓
Structured output
      ↓
Audit metadata
```

---

# 19. Minimum Necessary Disclosure

## 19.1 Core Rule

Only send Gemini the minimum information required to perform the current task.

Example semantic comparison:

Instead of:

```text
Entire email
Entire SI
Entire BL
All customer data
All shipment details
```

Prefer:

```text
Purpose: Compare Port of Loading
SI value: Port Klang
BL value: PORT KLANG, MALAYSIA
```

---

## 19.2 Full Document Restriction

For field-level semantic comparison:

> Do not send entire emails or entire documents when two or a small number of fields are sufficient.

---

## 19.3 Reply / Summary Exception

Reply generation and summarisation may require broader context.

Even then:

- send only relevant message content;
- remove unnecessary document fields;
- exclude unrelated customer/shipment data;
- avoid attachments unless required;
- apply sanitisation / redaction first.

---

# 20. Gemini Data Retention

Avoid long-term persistence of complete raw AI prompts or complete raw Gemini payloads unless required for a justified debugging mode.

Recommended persistent audit metadata:

- request purpose;
- model used;
- timestamp;
- fields/categories of data disclosed;
- request status;
- response status;
- latency;
- feature invoking the request;
- structured approved result where necessary.

Avoid persisting unnecessary raw conversational payloads.

---

# 21. Secrets and Provider Security

Gemini API credentials must:

- remain server-side;
- never be embedded in Outlook frontend code;
- never be embedded in Dashboard frontend code;
- never be committed to the repository;
- come from secure environment configuration.

Logs must not expose secrets.

---

# 22. Audit Requirements

Audit logs must remain append-only in normal application flow.

Relevant events include:

- email synced;
- email deleted;
- email restored;
- classification generated;
- classification manually changed;
- comparison completed;
- Human Review created;
- AI plan generated;
- plan edited;
- plan confirmed;
- override applied;
- re-comparison completed;
- reply generated;
- reply edited/refined;
- reply sent;
- record lifecycle cleanup event;
- processing failure.

Each event should include sufficient metadata to reconstruct the business sequence.

---

# 23. Data Lifecycle Management

## 23.1 Goal

Prevent uncontrolled database/storage growth while preserving necessary business evidence.

Retention periods should be configurable rather than hard-coded.

---

## 23.2 Candidate Cleanup Targets

Scheduled cleanup may apply to:

- raw email bodies;
- old attachments;
- OCR temporary files;
- AI temporary payloads;
- transient extraction artefacts;
- caches;
- old low-value operational logs;
- temporary processing files.

---

## 23.3 Data That Must Not Be Casually Purged

Do not automatically delete:

- audit history;
- Human Review history;
- human overrides;
- critical comparison history.

If future enterprise policy requires deletion, it should be a separately defined retention/compliance rule.

---

## 23.4 Scheduled Cleanup Job

Implement a scheduled retention process.

Example conceptual behaviour:

```text
Scheduled Retention Job
    ↓
Find expired transient records
    ↓
Verify not protected
    ↓
Delete / archive
    ↓
Record cleanup summary
```

Retention durations should be configurable by environment / policy.

---

# 24. Reliability Evaluation

## 24.1 Mandatory Full-Dataset Evaluation

Evaluation must run against the complete provided dataset:

```text
520 / 520 emails
```

Do not report reliability from only a small demo subset if the full evaluation is available.

---

## 24.2 Ground Truth

Use the official project ground truth / scoring logic as the evaluation authority.

Current expected source:

```text
ground_truth.json
```

and the official reliability scoring logic where applicable.

---

## 24.3 Required Metrics

### Classification

Report:

- total cases;
- accuracy;
- precision;
- recall;
- F1;
- confusion matrix;
- per-category metrics where practical.

### Discrepancy Detection

Report:

- precision;
- recall;
- F1;
- false positives;
- false negatives;
- total evaluated cases.

### Human Review / Escalation

Report:

- escalation precision;
- escalation recall;
- escalation F1;
- correctly escalated cases;
- unnecessary escalations;
- missed escalations.

### Reliability / Processing

Also report:

- processing failures;
- coverage;
- unresolved count;
- successful processing count.

---

# 25. Evaluation Output

The evaluation pipeline should produce at least:

```text
reports/latest/eval.json
reports/latest/eval.md
```

The Markdown report should be judge-readable.

The JSON report should be machine-readable.

The reported Dashboard metrics must not contradict the official evaluation output.

---

# 26. Reliability Error Analysis

The report should include examples of:

- false classifications;
- false mismatch detection;
- missed mismatch;
- unnecessary Human Review;
- missed Human Review;
- processing/OCR failure;
- unresolved cases.

The purpose is to demonstrate awareness of system limitations instead of claiming unsupported perfect accuracy.

---

# 27. Performance Evaluation

Performance testing should cover both individual workflow latency and full-dataset behaviour.

---

## 27.1 Required Performance Metrics

Measure where feasible:

- single-email end-to-end latency;
- 520-email batch throughput;
- deterministic-only path latency;
- Gemini-assisted path latency;
- API response latency;
- P50 latency;
- P95 latency;
- failure rate;
- peak memory usage if easily measurable.

---

## 27.2 With-AI vs Without-AI Comparison

Where possible, provide a comparison between:

### Deterministic path

```text
No Gemini invocation
```

and:

### AI-assisted path

```text
Gemini invoked for semantic / uncertain case
```

This provides evidence for the design claim that deterministic-first processing reduces unnecessary AI cost and latency.

---

# 28. Performance Reporting Rules

Do not advertise unsupported numbers.

Every published metric should be reproducible from:

- test configuration;
- dataset size;
- test environment;
- measured output.

Prefer:

```text
P50
P95
throughput
coverage
```

over a single best-case latency number.

---

# 29. Backend Requirements

The backend must support, directly or via equivalent services:

- shared Outlook/Dashboard state;
- Human Review plan storage;
- human override storage;
- re-comparison trigger;
- classification override;
- lifecycle sync state;
- deleted/restored state;
- AI gateway;
- Gemini request policy enforcement;
- reply draft lifecycle;
- audit logging;
- retention/cleanup jobs;
- evaluation reporting.

Exact endpoint names are implementation-dependent.

---

# 30. Suggested API Capability Areas

These are capability requirements, not mandatory route names.

```text
GET    case details
PATCH  case category
GET    comparison
POST   human-review AI proposal
PATCH  review plan
POST   confirm review plan
POST   apply approved override
POST   recompare
GET    review history
POST   reply summary/key-points
POST   reply generate
POST   reply refine
POST   reply send
GET    sync status
POST   Outlook sync/reconcile
GET    audit history
```

Existing endpoints should be extended where possible rather than duplicating equivalent logic.

---

# 31. Suggested Data Concepts

Use existing schema where possible.

Potential concepts include:

```text
email
case
classification
classification_override
document
extracted_field
comparison
comparison_result
human_review
review_plan
review_plan_item
human_override
reply_draft
sync_state
audit_event
retention_event
```

Avoid unnecessary schema expansion if existing tables can represent these concepts cleanly.

---

# 32. State Consistency Rules

## 32.1 Human Override Wins

If a confirmed human override exists, AI may not silently replace it.

---

## 32.2 Manual Category Wins

If a user manually changes classification, future classifier runs may suggest a different classification but may not silently overwrite the effective manual category.

---

## 32.3 Re-Comparison Is Required

Any comparison-affecting override must cause the comparison state to become stale until re-comparison finishes.

Suggested conceptual state:

```text
MISMATCH
   ↓
OVERRIDE_APPLIED
   ↓
RECOMPARING
   ↓
MATCH / MISMATCH / UNRESOLVED
```

---

# 33. Error Handling

The system must fail safely.

Examples:

### Gemini unavailable

- deterministic workflow remains operational;
- case may become UNRESOLVED / require Human Review;
- do not fabricate an AI result.

### Outlook synchronisation failure

- preserve existing backend data;
- expose stale/sync-error status;
- retry/reconcile;
- do not silently delete records.

### Re-comparison failure

- retain the approved override;
- mark processing failure visibly;
- allow retry;
- keep previous comparison history.

### Reply send failure

- retain draft;
- show failed status;
- do not mark as sent;
- allow user retry.

---

# 34. User Feedback / UI States

Any asynchronous operation should expose a clear state:

- processing;
- completed;
- failed;
- needs review;
- syncing;
- stale;
- deleted;
- restored.

Avoid UI states where the user clicks Apply or Send but cannot tell whether the operation succeeded.

---

# 35. Acceptance Criteria — Outlook

Outlook enhancement is accepted when:

- a user can view case-level comparison information;
- mismatch fields are visible;
- Human Review can be completed without opening Dashboard;
- AI plan can be edited;
- user confirmation is required;
- approved changes trigger re-comparison;
- updated result appears in Outlook;
- Dashboard reflects the same result;
- reply can be generated, edited and sent with human confirmation;
- manual category correction is available;
- review history can be accessed;
- deleted/restored state remains consistent with Outlook.

---

# 36. Acceptance Criteria — Human Review

Human Review is accepted when:

- AI suggestions are structured;
- individual proposed changes are editable;
- individual changes are rejectable;
- user confirmation is required;
- source values remain preserved;
- applied values are stored as human overrides;
- audit events are written;
- re-comparison occurs;
- new result is persisted;
- both clients show the new result.

---

# 37. Acceptance Criteria — Smart Reply

Smart Reply is accepted when:

- AI summary is generated;
- key reply facts are extracted;
- facts/key points are editable;
- users can add/remove key points;
- reply is generated from approved points;
- refine options exist;
- manual text editing remains possible;
- no automatic sending occurs;
- explicit user confirmation is required;
- sent status is synchronised;
- send action is audited.

---

# 38. Acceptance Criteria — Security

Security enhancement is accepted when:

- Gemini access is routed through one secure backend gateway;
- frontend clients never expose Gemini API secrets;
- field-level tasks do not send entire documents unnecessarily;
- request payload is minimized;
- Enterprise Privacy Mode exists;
- production defaults to privacy mode enabled;
- unnecessary raw AI payload is not persistently stored;
- disclosure purpose and metadata can be audited.

---

# 39. Acceptance Criteria — Synchronisation

Synchronisation is accepted when:

- Outlook delete becomes HolyShip deleted;
- deleted emails leave active queues;
- history remains accessible;
- Outlook restore reactivates the same logical email;
- read/unread is synchronised where supported;
- categories stay aligned where supported;
- last-sync state is visible;
- synchronisation failure does not silently corrupt business state.

---

# 40. Acceptance Criteria — Reliability

Reliability work is accepted when:

- all 520 emails are processed in the evaluation run;
- official ground truth/scoring logic is used;
- classification metrics are reported;
- discrepancy metrics are reported;
- escalation metrics are reported;
- confusion/error analysis is available;
- JSON and Markdown reports are produced;
- reported numbers are reproducible.

---

# 41. Acceptance Criteria — Performance

Performance work is accepted when:

- single-email latency is measured;
- batch throughput is measured;
- P50/P95 are reported;
- deterministic and Gemini-assisted paths are distinguishable;
- failure rate is reported;
- metrics are based on reproducible tests.

---

# 42. Recommended Implementation Order

Implement in this order to reduce dependency risk:

```text
1. Freeze state model + backend source-of-truth rules
2. Complete reliability evaluation against 520 emails
3. Complete end-to-end processing flow
4. Implement Human Review structured plan
5. Implement human overrides
6. Implement mandatory re-comparison
7. Connect Dashboard to new Human Review flow
8. Connect Outlook to same Human Review APIs
9. Add Outlook direct comparison/review operations
10. Add full email lifecycle synchronisation
11. Add delete + restore reconciliation
12. Add Smart Reply key-point workflow
13. Add human-confirmed Outlook send
14. Add Enterprise Privacy Mode
15. Centralise Gemini through Secure AI Gateway
16. Enforce minimum-necessary disclosure
17. Add performance test suite
18. Add retention / cleanup lifecycle
19. Add classification correction + Outlook categories
20. Add advanced filters, sorting and review history polish
```

Security gateway work may be brought earlier if current Gemini calls are spread throughout the application.

---

# 43. Suggested Demo Story

A final demo should show one continuous journey.

```text
1. A real Outlook email arrives.
2. HolyShip synchronises and classifies it.
3. SI / BL documents are processed.
4. A mismatch is detected.
5. The user opens the email in Outlook.
6. HolyShip shows the mismatch directly in the Add-in.
7. AI proposes a structured correction plan.
8. User edits one proposed value.
9. User confirms the plan.
10. HolyShip applies a human override.
11. Re-comparison runs.
12. Status changes from MISMATCH to MATCH / resolved state.
13. Dashboard updates automatically.
14. HolyShip creates reply summary + key points.
15. User edits a key point.
16. AI generates a revised reply.
17. User refines / edits it.
18. User explicitly confirms and sends.
19. Sent status is synchronised.
20. Audit history shows the entire sequence.
```

This demonstrates a genuine end-to-end workflow instead of isolated features.

---

# 44. Judge-Facing Evidence

The enhanced system should be able to support claims such as:

- full-dataset quantitative evaluation;
- deterministic-first processing;
- uncertainty escalation instead of forced guessing;
- human-controlled AI corrections;
- zero silent auto-apply;
- Outlook-native review workflow;
- traceable audit history;
- minimum-necessary AI disclosure;
- measurable deterministic vs AI-assisted performance.

Do not publish unsupported claims such as perfect accuracy or unrealistic latency.

---

# 45. Deferred: Multi-user / RBAC

**Status:** Pending mentor confirmation.

Do not prioritise implementation yet.

Possible future scope:

- My Queue;
- Team Queue;
- case claiming;
- reviewer ownership;
- reassignment;
- personal summary;
- team summary;
- role-based permissions.

This section is intentionally non-binding until mentor feedback is received.

---

# 46. Definition of Done

This enhancement phase is complete when HolyShip can demonstrate:

1. a complete email-to-resolution workflow;
2. meaningful direct operation inside Outlook;
3. consistent Outlook and Dashboard state;
4. structured AI-assisted Human Review;
5. human-approved override application;
6. automatic re-comparison after approved corrections;
7. human-controlled end-to-end reply generation and sending;
8. delete/restore/status synchronisation with Outlook;
9. persistent audit evidence;
10. enterprise-grade Gemini data minimisation controls;
11. scheduled data lifecycle management;
12. full 520-email reliability evaluation;
13. reproducible performance measurements.

The intended product identity is:

> **HolyShip is not an AI system that automatically changes shipping documents. It is a trusted verification workflow where deterministic checks do the majority of work, AI assists only where useful, humans control business-critical decisions, and every action remains traceable.**
