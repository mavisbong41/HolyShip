# Leakage audit — Phase 0

Date: 2026-09-20

## Scope

Static search of runtime source, tests, configuration, and repository documentation. The organizer Docker archive was not extracted; `data/bundle/` is the participant-only bundle and contains no `ground_truth.json`.

## Findings

- No runtime source references `ground_truth.json`, `data_v2`, or private answers.
- References to private data occur only in requirements/playbook documentation that prohibits their use.
- `email_###` references are limited to public-fixture tests and public bundle paths; no runtime email-ID dispatch was found.
- `520` occurs in a fixture assertion and documentation, not core runtime logic.
- No source/filename dispatch or expected-answer lookup table exists in runtime code.
- Credentials are supplied through `.env` / environment configuration; `.env` is ignored by Git and no credential literal was found in tracked source.
- Source contains legacy `GENERAL_MAIL`, `UNCERTAIN`, and Human Review code. These are specification conflicts, not private-answer leakage.

## Evidence command

```powershell
rg -n -i "ground_truth\\.json|data_v2|private (answer|reference)|email_[0-9]{3}|\\b520\\b" --glob '!data/bundle/**' --glob '!README_batch1.md' --glob '!backend_requirements_ingestion_to_compare.md' --glob '!AGENTS.md' --glob '!implement.md' --glob '!docs/**' .
```

## Limitation

This is a static audit. Runtime validation is recorded separately in `reports/latest/`.
