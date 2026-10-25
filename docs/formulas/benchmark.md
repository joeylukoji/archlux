# Benchmark

**Code:** `bench.run`, `bench.compare`, `bench.report`, `bench.stats`.

## Statement

Every run produces a **manifest** (version, seed, fingerprints, `ModelTrace`)
**before** the results. The **raw results** are written **before** any aggregation.
The report is **stratified by orientation** (8-sector rose) — never a global mean
alone: two methods can have the same mean and cross over in the south.

### Paired bootstrap

For two methods evaluated on the **same** plans, \(d_i = a_i - b_i\). We
resample the \(d_i\) \(B\) times with replacement and take the
\(\alpha/2\) and \(1-\alpha/2\) percentiles of the resampled means:

\[
\mathrm{CI}_{1-\alpha}
 = \bigl[\,q_{\alpha/2}(\bar d^{*}),\; q_{1-\alpha/2}(\bar d^{*})\,\bigr],
\qquad B = 9\,999 .
\]

Pairing is what removes the between-plan variance: it is the
difference, not the two means, that is resampled.

### TOST — equivalence

**Not rejecting \(H_0\) does not demonstrate equivalence.** To conclude "the two
methods differ by no more than \(\delta\)", two one-sided tests are needed
(Schuirmann):

\[
t_{-}=\frac{\bar d+\delta}{s/\sqrt{n}},\qquad
t_{+}=\frac{\delta-\bar d}{s/\sqrt{n}},\qquad
p=\max\bigl(P(T_{n-1}>t_{-}),\,P(T_{n-1}>t_{+})\bigr).
\]

Equivalence is declared if \(p<\alpha\). \(\delta\) is a **margin decided before
seeing the data**, never adjusted afterwards.

### Holm–Bonferroni — multiple comparisons

A stratified table compares \(m\) cells. Without correction, the probability that at
least one test comes out by chance is \(1-(1-\alpha)^m\): already \(0.56\) for
\(m=16\), \(\alpha=0.05\). Holm sorts the p-values in increasing order and rejects
\(p_{(i)}\) as long as

\[
p_{(i)} \le \frac{\alpha}{m-i+1},
\]

stopping at the first failure. It controls the **FWER without an independence
assumption** — unlike Benjamini–Hochberg, which only controls the FDR
and therefore does not suit a claim of the type "method A wins on this
stratum".

### Power

Approximation by a non-central \(t\), Cohen's \(d\) parameter. It serves **before**
the experiment to size \(n\); invoking it *after* a non-significant
result ("observed power") has no inferential value.

### Cluster bootstrap — the statistical unit

Sixteen corruptions of one dwelling, or eight azimuths of one plan, are **one**
statistical unit, not sixteen or eight. A Wilson interval on the rows treats them as
independent and comes out too narrow. `bench.stats.cluster_bootstrap_proportion`
resamples the \(k\) clusters \(g\) (source plans) with replacement:

\[
\hat p^{*} = \frac{\sum_{g \in G^{*}} s_g}{\sum_{g \in G^{*}} n_g},
\qquad G^{*} \sim \mathrm{Unif}(G)^{k},
\]

with \(s_g\) the successes and \(n_g\) the rows of cluster \(g\), and takes the
percentiles of \(\hat p^{*}\). The statistical unit of every bench is stated in
`results/RECONCILIATION.md`.

## Benches of the paper (B1 to B9)

| Paper | Experiment | Raw file | Statistical unit |
|---|---|---|---|
| B1 | `experiments/j2_validity.py` | `j2_validity_raw.csv` | case = plan x amplitude; 90 plans |
| B2 | `experiments/j3_orientation.py` | `j3_orientation.csv` | 1 plan x 8 azimuths (illustrative) |
| B3 | `experiments/j4_gradient.py` | `j4_gradient.csv` | 20 points per azimuth |
| B4 | `experiments/j5_coverage.py`, `j5_selection.py` | `j5_coverage.csv`, `j5_selection_raw.csv` | calibration draw (repetition); source plan |
| B5 | `experiments/j6_active.py`, `j6_ifc.py` | `j6_active.csv`, `j6_ifc.csv` | campaign; plan |
| B6 | `experiments/j7_msd_*.py` | `j7_repair_raw.csv` (+ summary) | corruption, clustered in 300 dwellings |
| B7 | `experiments/j7_sd_*.py` | summaries only | dwelling (split by site); room |
| B8 | `experiments/j8_generation.py` | `j8_{etoile,plausible,divers}_raw.csv` | generated plan (etoile/plausible paired) |
| B9 | `experiments/j9_orientation.py` | `orientation/hd*.md` (timing: none) | variant = plan x azimuth; 6 plans |

`experiments/reconcile.py` recomputes every number the paper prints from these files
and writes `results/RECONCILIATION.md` / `reconciliation.json`, one verdict per number
(`consistent`, `article_wrong`, `ambiguous`, `cannot_verify`).
`tests/unit/test_reconcile.py` fails when a raw file moves a published number.

## Coverage after selection

`bench.selection.run_selection_protocol` (see
[conformal prediction](../concepts/conformal-prediction.md)) splits on **source
plans** (`data.provenance.split_by_group`: train / validation / calibration / test,
`check_no_group_leakage` refuses a source in two sets) and measures, on the same test
set, the passive calibrator, the same calibrator on the frozen policy's outputs, and a
calibration on the outputs of the policy frozen before it. Coverage is given with a
cluster interval (conditional on the calibrations) and a Student interval over the
repetitions (the marginal guarantee averages over calibration draws, so repetitions
are its units).

## Ablations

`bench.ablation` runs every configuration on **the same** corrupted plans, contexts and
azimuths: initial, repair only, repair + Frank-Wolfe on the surrogate (with and without
the \(-\hat q\hat\sigma\) penalty), repair + Frank-Wolfe on the frozen reference
itself, and displacement budgets; several corruption seeds per plan measure stability.
Gains are paired against "repair only". "Confirmed" means confirmed by the frozen
closed-form oracle, **not** by a physical simulation. An iteration-budget sweep is not
possible through `legalize` (Frank-Wolfe's `max_iter` is not exposed); iterations and
stop status are recorded per run instead.

## Reproduce

| What | Command | Data |
|---|---|---|
| B1-B5 (synthetic) | `make results` (`make check-results` checks the bytes) | none |
| coverage after selection | `python experiments/j5_selection.py results 400 10` | none |
| ablations | `python experiments/ablations.py results 90 3` | none |
| reconciliation B1-B9 | `make reconcile` | `results/` |
| all of the above | `make reproduce` | none |
| B6 (MSD) | `python experiments/j7_msd_repair.py MSD_CSV 300`, `j7_msd_idempotence.py MSD_CSV 400`, `j7_msd_summary.py` | MSD, not redistributed |
| B7 (Swiss Dwellings) | `experiments/j7_sd_labels.py`, `j7_sd_per_room.py` | Swiss Dwellings, not redistributed |
| B8 (HouseDiffusion) | `make results-corpus HD=plans.jsonl LABEL=etoile` (and `plausible`, `divers`) | generated plans |
| B9 | `experiments/j9_orientation.py` | generated plans |

Every new run writes a record (`bench.repro.record`): git commit and dirty flag,
dependency versions, platform, seed, command, every algorithm parameter, and the
SHA-256 of its inputs and outputs (restricted corpora hashed and flagged
`redistributable: false`). The B9 timing table of the paper has **no** raw file: it
cannot be reproduced from `results/` until the timing rows are published.

## Assumptions

- `evaluate_by` is an **external** oracle — never the surrogate being optimized,
  otherwise one measures the model's error against itself.
- Mandatory root seed; sub-seeds through `bench.seeds.derive`.
- The bootstrap assumes the \(d_i\) exchangeable between plans; it does **not** correct
  a dependence between plans from the same building. On a real corpus
  (several floors of the same building), resample by **cluster**
  (`cluster_bootstrap_proportion`). The same holds for variants of one plan
  (corruptions, azimuths): a McNemar or Wilcoxon test on them overstates the
  significance.
- Exact geometry outside the benchmark; the light scores are **estimates**,
  never a proof.

## Code

| Symbol | Function |
|---|---|
| manifest | `bench.manifest.emit` / `ModelTrace` |
| orchestration | `bench.run` → `Result` |
| comparison | `bench.compare` |
| report | `bench.report` |
| bootstrap \(\mathrm{CI}\) | `bench.stats.paired_bootstrap` |
| cluster bootstrap | `bench.stats.cluster_bootstrap_proportion` |
| paper reconciliation | `bench.reconcile.reconcile` |
| coverage after selection | `bench.selection.run_selection_protocol` |
| ablations | `bench.ablation.run_ablations` |
| run record | `bench.repro.record` |
| split by source, leakage | `data.provenance.split_by_group`, `check_no_group_leakage` |
| equivalence | `bench.stats.tost` |
| multiplicity | `bench.stats.holm` |
| sizing | `bench.stats.power` |

## Use cases

| Do | Do not |
|---|---|
| Fix \(\delta\) and \(\alpha\) before the experiment | Choose \(\delta\) after seeing \(\bar d\) |
| Stratify by orientation, then apply Holm | Publish 16 uncorrected p-values |
| Resample by cluster on a real corpus | Treat floors of the same building as independent |
| Write the raw results before aggregating | Publish a mean without its data |

## Source

Bootstrap: Efron & Tibshirani (1993), ch. 13 — [bibliography](sources.md) no. 20.
TOST: Schuirmann (1987), no. 21. Holm: Holm (1979), no. 22.
Power: Cohen (1988), ch. 2, no. 23. Repository protocol: `MILESTONE-6.md` §5.
