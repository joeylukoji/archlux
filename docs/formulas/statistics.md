# Statistics — conformal prediction

**Code:** `uq.conformal.conformal_quantile`, `uq.conformal.ConformalCalibrator`.

This page is the formulary of milestone 5. Duals, Farkas, \(\delta_\infty\)
remain **exact numbers**: they do not belong here.

## Statement

Normalized nonconformity scores, one per calibration plan:

\[
s_i = \frac{\lvert y_i - \hat y_i\rvert}{\hat\sigma_i},\qquad i=1,\ldots,n.
\]

Finite-sample conformal quantile, level \(\alpha\in\,(0,1)\):

\[
k = \bigl\lceil (n+1)(1-\alpha)\bigr\rceil,
\qquad
\hat q = s_{(k)}\ \text{if}\ k\le n,\ \text{otherwise undefined}.
\]

Interval announced at the point \((\hat y, \hat\sigma)\):

\[
\bigl[\hat y - \hat q\,\hat\sigma,\ \hat y + \hat q\,\hat\sigma\bigr].
\]

Under exchangeability of the point with the calibration set,

\[
\mathbb{P}\bigl(y \in [\hat y - \hat q\,\hat\sigma,\ \hat y + \hat q\,\hat\sigma]\bigr)
 \ge 1-\alpha.
\]

## Assumptions

- The \(n+1\) scores (calibration + point to bound) are exchangeable.
- \(\hat\sigma_i > 0\).
- The model is **frozen** before any reading of the calibration set.
- \(k\le n\): otherwise the kernel raises rather than publish an infinite bound.

Plans produced by a maximizer of \(\hat y\) violate exchangeability.
Coverage *under selection* is measured (`uq.drift`); it is not
guaranteed by the theorem.

## Derivation

Rank-based conformal prediction (Vovk, Gammerman & Shafer, 2005) takes the
\((1-\alpha)\)-quantile *over \(n+1\) points*, including the test point of unknown
rank. Replacing \(n+1\) by \(n\) (ordinary empirical quantile) gives
intervals that are too narrow: the actual coverage falls below \(1-\alpha\), and
nothing reports it. Hence \(k=\lceil(n+1)(1-\alpha)\rceil\) and the ban
on `np.quantile(s, 0.90)` alone.

## Code

| Symbol | Function |
|---|---|
| \(s_{(k)}\) | `conformal_quantile` |
| \(\hat q\) | `ConformalCalibrator.fit` / `.q` |
| interval | `ConformalCalibrator.borne` → `PerformanceBound` |
| CRPS | `uq.reliability.crps` |
| \(J=\hat\mu-\hat q\,\hat\sigma\) | `light.objective.Daylight` |

## Use cases

| Do | Do not |
|---|---|
| Calibrate **after** freezing, on a set never seen in training | Read `calibration/` during the `fit` of the weights |
| Display `n_calibration` next to the bound | Publish the network's \(\hat\sigma\) as if it were \(1-\alpha\) |
| One calibrator per indicator, ASE in `<=` | Reuse the sDA's \(q̂\) for the ASE |
| `NOT EVALUABLE` if the exchangeability test rejects | Silently widen the interval |

## Source

Vovk, Gammerman & Shafer (2005), *Algorithmic Learning in a Random World*.
[Bibliography](sources.md) no. 12.

Truth oracle of the milestone: [split-flux](split-flux.md), not an LM-83 sDA.
