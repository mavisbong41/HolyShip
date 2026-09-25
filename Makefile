PYTHON ?= python
ifeq ($(OS),Windows_NT)
NPM ?= npm.cmd
else
NPM ?= npm
endif

.PHONY: test check-fast frontend-check addin-check eval official-eval performance-paths reliability perf trace check score

test:
	$(PYTHON) scripts/run_tests.py

check-fast:
	$(PYTHON) -m compileall -q backend/app backend/tests
	$(PYTHON) -m pytest backend/tests/test_api.py backend/tests/test_submission_adapter.py backend/tests/test_phase5_retry_timeout.py backend/tests/test_phase5_reliability.py backend/tests/test_storage_models.py -q
	$(NPM) --prefix frontend run typecheck
	$(NPM) --prefix frontend run test
	$(NPM) --prefix outlook-addin run typecheck
	$(NPM) --prefix outlook-addin run test
	git diff --check

frontend-check:
	$(NPM) --prefix frontend run check

addin-check:
	$(NPM) --prefix outlook-addin run check

eval:
	$(PYTHON) scripts/run_baseline.py

official-eval:
	$(PYTHON) scripts/evaluate_official.py --ground-truth $(GROUND_TRUTH)

performance-paths:
	$(PYTHON) scripts/performance_paths.py

reliability:
	$(PYTHON) scripts/run_tests.py backend/tests/test_sync_service.py backend/tests/test_repositories_postgres.py backend/tests/test_phase5_reliability_postgres.py -q

perf: eval

trace:
	$(PYTHON) scripts/trace_phase0.py $(PHASE)

check: test eval reliability perf trace frontend-check addin-check

score: check
	$(PYTHON) scripts/score_submission.py
