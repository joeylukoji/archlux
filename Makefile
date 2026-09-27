# Figures of results/ (PLAN.md phase 2). The runner is portable: on Windows, call
# `python scripts/results.py` directly with the same options.
PYTHON ?= python

.PHONY: results check-results results-corpus check-complexity

results:
	$(PYTHON) scripts/results.py

check-results:
	$(PYTHON) scripts/results.py --check

# make results-corpus MSD=/path/mds_V2_5.372k.csv HD=/path/j8_plans.jsonl LABEL=etoile
results-corpus:
	$(PYTHON) scripts/results.py $(if $(MSD),--msd $(MSD)) $(if $(HD),--hd $(HD) --label $(or $(LABEL),etoile))

# PLAN.md phase 4's exit gate: no function above cyclomatic complexity 10. `radon`
# itself always exits 0, so the failure comes from grep finding a violation line.
check-complexity:
	@out="$$($(PYTHON) -m radon cc src -n C)"; \
	if [ -n "$$out" ]; then echo "$$out"; echo "functions above CC 10 (see docs/plans/phase-4-design-patterns.md)"; exit 1; fi
	@echo "radon: no function above CC 10"
