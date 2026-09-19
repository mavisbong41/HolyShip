# Phase 1 cross-layer consistency audit

Audit date: 2026-09-20

Scope: Phase 1 authoritative email categories, comparison readiness, processing statuses, Stage 2 output, Human Review freeze, and backward-compatibility boundaries.

No private ground truth or evaluator data was used.

## Result

PASS. Current runtime, persistence metadata, development database, API schemas, migrations, tests, and documentation use the Phase 1 vocabularies consistently. Legacy category strings and Human Review records remain only at documented compatibility boundaries.

## Email category

Authoritative internal values:

- `document_comparison`
- `new_si_request`
- `invoice_query`
- `general_message`
- `spam`

Evidence:

- `backend.app.classification.signals.EmailCategory` has exactly these five values and no aliases.
- `CATEGORY_SIGNALS`, classifier output validation, and final classifier tests use the same set.
- `classification_results.category` is protected by `ck_classification_category`.
- `ClassificationOut.category` is a five-value Pydantic `Literal` contract.
- Alembic `20260920_0003` converts historical uppercase categories, including `GENERAL_MAIL` and `UNCERTAIN`, before the current constraint is installed.
- The submission adapter converts current internal values to the public participant vocabulary. Historical serialized inputs are accepted only by that export boundary and never become authoritative runtime enum members.

Development database stored values after migration: `document_comparison=214`, `new_si_request=136`, `invoice_query=83`, `general_message=61`, `spam=26`. No unsupported category is stored.

## Comparison readiness

Authoritative values:

- `READY_FOR_COMPARISON`
- `AWAITING_DOCUMENTS`
- `UNRESOLVED`

Evidence:

- Runtime constants and `evaluate_readiness` use exactly these values and return readiness only for `document_comparison`.
- `classification_results.comparison_readiness` is nullable for non-comparison mail and protected by `ck_classification_readiness` when populated.
- `ClassificationOut.comparison_readiness` exposes exactly these three values or null.
- Alembic `20260920_0003` adds the field; `20260920_0004` maps historical comparison/readiness rows to processing states.
- Pattern A, Pattern B, READY, AWAITING, and UNRESOLVED executable tests remain substantive evidence.

The existing development baseline predates readiness evaluation and therefore has 520 null historical readiness values. This is valid under the nullable compatibility contract; new processing persists a readiness value for every current `document_comparison` result.

## Processing status

Authoritative values:

- `NEW`
- `QUEUED`
- `CLASSIFYING`
- `CLASSIFIED`
- `AWAITING_DOCUMENTS`
- `RETRIEVING_ATTACHMENTS`
- `EXTRACTING`
- `COMPARING`
- `COMPLETED`
- `BLOCKED`
- `FAILED`

Evidence:

- `PROCESSING_STATUSES`, `EmailMessageRecord.processing_status`, and `transition()` use this exact set.
- `ck_email_processing_status` contains all and only these 11 states.
- `ProcessingEventRecord` persists old/new state chronology and machine-readable reason codes.
- `EmailOut` and `EmailListItem` expose the same 11-value Pydantic contract.
- Alembic `20260920_0004` adds, backfills, constrains, and indexes the state/event model.
- PostgreSQL processing-state tests cover database rejection, chronology, reload, no-op suppression, and readiness transitions.

Development database stored status aggregates: `CLASSIFIED=214`, `COMPLETED=306`; no invalid or null status exists.

## Stage 2 contract

- Final category validation accepts only the five internal categories.
- Confidence must be finite and within `[0, 1]`; both runtime validation and `ck_classification_confidence` enforce the contract.
- A non-empty reason code is required before a Stage 2 result becomes a `ClassificationOutput`.
- Classification reason codes are now persisted in the non-null `classification_results.reason_code` column and exposed by `ClassificationOut`.
- Alembic `20260920_0005` backfills historical reason codes and installs category, readiness, and confidence constraints.
- Malformed Stage 2 category, range, NaN, infinity, empty-reason, and malformed-object tests prove invalid output cannot reach persistence/API processing.

Development database reason-code aggregates after backfill: `CLASSIFICATION_RESOLVED=21`, `STAGE1_CONFIDENT=274`, `STAGE2_RESOLVED=225`.

## Human Review freeze (SCP-01)

- `EmailCategory` cannot emit `UNCERTAIN`.
- Current Stage 2 always returns one validated five-category result and does not attach Human Review metadata.
- The PostgreSQL SCP test processes an obvious non-comparison, Pattern A, unresolved readiness, and Stage 2 ambiguity, then reloads the database and proves zero new `human_review_cases`.
- Unresolved comparison readiness persists `BLOCKED` with `READINESS_UNRESOLVED`, not Human Review.
- Historical `human_review_cases` storage and read-only GET routes remain for compatibility. Development currently contains 21 historical cases; they were not deleted or extended.
- No Human Review UI/workflow files were added in Phase 1.

## Backward compatibility (SCP-07)

- Existing health, sync, email listing/detail/classification, and incoming-email routes remain registered; API regressions pass.
- Alembic `20260920_0003` converts legacy classification values to the five-category model.
- Alembic `20260920_0004` safely backfills historical processing status from existing classification/readiness records.
- Alembic `20260920_0005` is additive: it backfills reason codes before making them non-null, then applies vocabulary/range checks.
- The submission adapter accepts legacy serialized category strings only at export/deserialization boundaries. Runtime enums contain no `GENERAL_MAIL` or `UNCERTAIN` alias.
- Static bundle, organizer HTTP, and incoming API source-adapter regressions remain in the full suite.

## Executable evidence

- `backend/tests/test_phase1_scp_closure.py::test_current_sync_never_creates_new_human_review_cases` (`SCP-01`)
- `backend/tests/test_phase1_scp_closure.py::test_phase1_vocabularies_match_runtime_storage_and_api_contracts` (`SCP-05`)
- `backend/tests/test_phase1_classifier_contract.py::test_stage2_rejects_malformed_output` (`SCP-05`)
- `backend/tests/test_phase1_scp_closure.py::test_legacy_categories_are_confined_to_compatibility_boundaries` (`SCP-07`)
- `backend/tests/test_submission_adapter.py::test_adapter_emits_every_required_public_field_and_supported_category` (`SCP-07`)
- `backend/tests/test_api.py::test_incoming_email_returns_classified_outcome` (`SCP-07`)

Focused SCP/API/compatibility result: 23 passed, 0 failed, 0 skipped, 1 deprecation warning.

## Compatibility boundaries retained

- Historical Human Review table and read-only routes.
- Historical-category conversion in migration `20260920_0003`.
- Legacy serialized-category acceptance in the submission/export adapter.

These boundaries do not alter current runtime enums or create new Human Review work.
