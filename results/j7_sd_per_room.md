# Milestone 7: per-room prediction against real simulations

Target `sun_201803211200_mean` (Swiss Dwellings v3.0.0). MSD corpus joined to the
simulations, **room** granularity.

## A. Correlations on the matched set (4,239 rooms)

| predictor | Pearson | Spearman |
|---|--:|--:|
| **floor area alone** | **+0.387** | **+0.590** |
| analytic per room (extensive) | +0.151 | +0.403 |
| analytic / area (intensive) | +0.076 | **+0.085** |
| 1 / area | -0.318 | -0.590 |

## B. Generalization, split **by site** (test 2,346 rooms)

| model | MAE | relative MAE | R2 | Spearman |
|---|--:|--:|--:|--:|
| constant (train mean) | 0.448 | 91.5 % | -0.000 | — |
| **floor area alone** | **0.403** | 82.3 % | **+0.150** | **+0.572** |
| analytic per room | 0.448 | 91.5 % | -0.000 | **-0.342** |

Conformal at alpha = 0.10 on the analytic surrogate: coverage **88.5 %** for a 90 %
target, width 1.554, n_calibration 2,708.

## Reading

**The analytic surrogate predicts only the size of the rooms.** Normalized by area, its
rank drops to `rho = +0.085`: almost nothing is left. All its predictive power comes from
growing with the area, not from its physics: neither the CIBSE depth rule nor the
eight-sector table brings any signal.

**Floor area alone beats it.** `rho = +0.590` against `+0.403`, and `R2 = +0.150` against
`-0.000` in generalization. A trivial variable, available without any model, predicts
better than the surrogate of the repository.

**What little signal there is does not survive a change of site.** On the matched set
the analytic surrogate correlates positively (`rho = +0.403`); on sites **disjoint** from
training, the rank reverses (`rho = -0.342`). This is exactly what the split by site is
meant to reveal, and what a split by apartment would have hidden.

**The conformal coverage dips slightly**: 88.5 % for a 90 % target. The theorem assumes
exchangeability; disjoint sites are not exchangeable. The gap is small and goes in the
expected direction: it is a measured illustration of the limit documented in
`limitations.md`, not an implementation defect.

## Scope

One column out of 126, 2,000 apartments read, an irradiance at a fixed instant that is
not an sDA. These figures say what **this** surrogate is worth on **this** target, not
what a model trained on the glazing and the surroundings would be worth.
