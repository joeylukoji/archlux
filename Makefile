# Figures of resultats/ (PLAN.md phase 2). The runner is portable: on Windows, call
# `python scripts/resultats.py` directly with the same options.
PYTHON ?= python

.PHONY: resultats check-resultats resultats-corpus

resultats:
	$(PYTHON) scripts/resultats.py

check-resultats:
	$(PYTHON) scripts/resultats.py --check

# make resultats-corpus MSD=/path/mds_V2_5.372k.csv HD=/path/j8_plans.jsonl LABEL=etoile
resultats-corpus:
	$(PYTHON) scripts/resultats.py $(if $(MSD),--msd $(MSD)) $(if $(HD),--hd $(HD) --label $(or $(LABEL),etoile))
