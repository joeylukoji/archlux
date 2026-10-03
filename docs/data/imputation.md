# Opening imputation

**Code:** `data.imputation.impute_openings`.

The simulated corpus often lacks the windows; the one that has the windows lacks the
simulations.

Rule: a centred window (`s=0.5`) on each wall without an opening, relative width
\(0{,}30\) (`DEFAULT_OPENING_RATIO`). Windows already present are left intact.

To measure the effect: calibrate (milestone 5) separately on the subset with observed
windows and on the imputed set, and **publish both** coverages. A coverage obtained
only on the imputed set is not a coverage on the real one.
