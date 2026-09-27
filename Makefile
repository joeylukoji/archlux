# Figures of results/ (PLAN.md phase 2). The runner is portable: on Windows, call
# `python scripts/results.py` directly with the same options.
PYTHON ?= python

.PHONY: results check-results results-corpus

results:
	$(PYTHON) scripts/results.py

check-results:
	$(PYTHON) scripts/results.py --check

# make results-corpus MSD=/path/mds_V2_5.372k.csv HD=/path/j8_plans.jsonl LABEL=etoile
results-corpus:
	$(PYTHON) scripts/results.py $(if $(MSD),--msd $(MSD)) $(if $(HD),--hd $(HD) --label $(or $(LABEL),etoile))
