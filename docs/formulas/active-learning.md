# Active learning

**Code:** `active.selection`, `active.densite`, `active.loop.Loop`.

## Statement

\[
\mathrm{priority}(Q) \;=\; \hat\sigma(Q)\;\times\;\hat f(Q).
\]

It is a **product**, not a sum: a zero factor discards the candidate. Without the
density, we simulate aberrant plans that the optimizer will never visit; without
the uncertainty, we re-simulate what the model already masters. This is the
"uncertainty × representativeness" weighting of Settles (§6.3.2).

### The density

\(\hat f\) is an isotropic Gaussian kernel estimator on the plans **produced by
the optimizer** — that is, on the region where the surrogate will actually be
queried, not on the training corpus:

\[
\hat f(c) \;=\; \frac{1}{m}\sum_{j=1}^{m}
 \exp\!\left(-\frac{\lVert c-r_j\rVert_2^{2}}{2h^{2}}\right),
\qquad
h \;=\; \bar s_{r}\; m^{-1/(d+4)} ,
\]

where \(\bar s_r\) is the mean per-coordinate standard deviation of the reference and \(d\) the
dimension of the plan vector. The exponent \(-1/(d+4)\) is **Scott's rule**.

The normalization factor \((2\pi h^2)^{-d/2}\) is **deliberately omitted**: the
priority is only used to *rank* candidates, and a common multiplicative
constant changes no ranking. \(\hat f\) is therefore not a
probability density and must not be published as one.

!!! warning "Curse of dimensionality"
    An isotropic kernel in dimension \(d = 4n_{\text{rooms}}\) degrades quickly:
    at \(d = 60\), \(m^{-1/64}\) is almost \(1\) whatever \(m\), and all
    densities collapse to the same value. Selection then tends towards
    uncertainty alone. On plans with more than about ten rooms, reduce the
    dimension (PCA, or a distance on the descriptors of `light.base`) **before**
    estimating the density.

### The loop

After each batch of \(k\) candidates: simulate with the frozen oracle → retrain if
`fit` exists → **recalibrate the conformal predictor**. Recalibration is not
optional: the model has changed, so the previous \(\hat q\) no longer bounds anything.

!!! danger "Exchangeability is broken by construction"
    The added points are **chosen** by the priority criterion. They are
    therefore not exchangeable with an i.i.d. draw, and a calibration set fed
    by the active loop **invalidates the conformal theorem**. The calibration set
    must stay independently drawn. What the loop legitimately improves is
    the interval **width** (through \(\hat\sigma\)), measured at an equal simulation
    budget against `RandomStrategy`.

## Assumptions

- Candidates and reference live in the same vector space, at the same scale.
- The oracle is a deterministic `Surrogate` (`SplitFluxOracle`), not a ray
  tracer — see [ground truth](../data/ground-truth.md).
- Finite simulation budget; comparison **at equal budget** with `RandomStrategy`,
  same root seed.

## Code

| Symbol | Function |
|---|---|
| product \(\hat\sigma\times\hat f\) | `active.selection.UncertaintyTimesDensity` |
| random baseline | `active.selection.RandomStrategy` |
| \(\hat f\) | `active.densite.kernel_density` |
| \(h\) (Scott) | `kernel_density(..., bande=None)` |
| loop | `active.loop.Loop.run` → `ActiveReport` |

## Use cases

| Do | Do not |
|---|---|
| Recalibrate after each cycle | Reuse a calibration token from an earlier model |
| Compare active vs random at equal budget | Add uncertainty and density |
| Measure the final interval width | Optimize only the network's MAE |
| Keep the calibration out of the loop | Add the acquired points to the calibration set |

## Source

Uncertainty × density weighting: Settles (2009), §6.3.2 —
[bibliography](sources.md) no. 26. Bandwidth: Scott (1992), §6.3, no. 24;
isotropic Gaussian kernel: Silverman (1986), §4.3, no. 25.
Repository protocol: `MILESTONE-6.md` §3.
