# Figures of results/ (PLAN.md phase 2). The runner is portable: on Windows, call
# `python scripts/results.py` directly with the same options.
PYTHON ?= python
# Empty when archlux is installed (pip install -e .); `make PYTHONPATH_SRC=PYTHONPATH=src`
# otherwise.
PYTHONPATH_SRC ?=

.PHONY: results check-results results-corpus check-complexity reproduce reconcile

# Every bench that runs without the restricted corpora (B1-B5, the selection protocol
# and the ablations), then the reconciliation of the paper's numbers (B1-B9) with the
# raw files. Corpus benches (B6-B9): see docs/formulas/benchmark.md, "Reproduce".
reproduce: results
	$(PYTHONPATH_SRC) $(PYTHON) experiments/j5_selection.py results 400 10
	$(PYTHONPATH_SRC) $(PYTHON) experiments/ablations.py results 90 3
	$(MAKE) reconcile

reconcile:
	$(PYTHONPATH_SRC) $(PYTHON) experiments/reconcile.py results

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
