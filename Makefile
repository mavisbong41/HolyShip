PYTHON ?= python

.PHONY: test check-fast eval reliability perf trace check score

test:
	$(PYTHON) scripts/run_tests.py

check-fast:
	$(PYTHON) -m compileall -q backend/app backend/tests
	$(PYTHON) -m pytest backend/tests/test_api.py backend/tests/test_submission_adapter.py backend/tests/test_phase5_retry_timeout.py backend/tests/test_phase5_reliability.py backend/tests/test_storage_models.py -q
	git diff --check

eval:
	$(PYTHON) scripts/run_baseline.py

reliability:
	$(PYTHON) scripts/run_tests.py backend/tests/test_sync_service.py backend/tests/test_repositories_postgres.py backend/tests/test_phase5_reliability_postgres.py -q

perf: eval

trace:
	$(PYTHON) scripts/trace_phase0.py $(PHASE)

check: test eval reliability perf trace

score: check
	$(PYTHON) scripts/score_submission.py
