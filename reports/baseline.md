# Phase 0 baseline

The public participant bundle was synced against isolated `holyship_dev`.

- Emails: 520
- Initial sync: 499 classified, 21 human-review outcomes, 0 materialized-email failures, 0 source failures
- Category distribution: BL_COMPARISON 220; SI_REQUEST 136; INVOICE_QUERY 83; GENERAL 41; SPAM 40
- Wall time: 3.978 seconds
- Throughput: 130.720 emails/second
- External LLM/OCR/Vision/cache calls: 0 / 0 / 0 / 0

The repeat runs used by `make check PHASE=0` remained idempotent: all public source IDs were recognized and no duplicate work was created. The detailed current run artifact is `reports/latest/eval.md`; `reports/latest/submission.json` contains every public email ID.

The single permitted score attempt could not reach the organizer at `http://localhost:8080` (connection refused), so no aggregate scoreboard is available. This was recorded in `reports/score_history.jsonl`; it was not retried.
