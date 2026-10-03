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

## Assumptions

- `evaluate_by` is an **external** oracle — never the surrogate being optimized,
  otherwise one measures the model's error against itself.
- Mandatory root seed; sub-seeds through `bench.seeds.derive`.
- The bootstrap assumes the \(d_i\) exchangeable between plans; it does **not** correct
  a dependence between plans from the same building. On a real corpus
  (several floors of the same building), resample by **cluster**.
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
