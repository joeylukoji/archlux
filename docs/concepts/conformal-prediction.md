# Conformal prediction

Four steps, one trap, one assumption. Module: `archlux.uq.conformal`.
Source: Vovk, Gammerman & Shafer (2005), [bibliography](../formulas/sources.md) no. 12.

## The four steps

1. **Freeze** the surrogate, issue the token (`freeze_and_issue`). The calibration
   set has never been read during training.
2. **Score** each calibration plan: \(s_i = \lvert y_i - \hat y_i\rvert / \hat\sigma_i\).
3. **Take the rank** \(k = \lceil (n+1)(1-\alpha)\rceil\) in the sorted scores.
   That is \(q̂\). Not the empirical quantile at \(1-\alpha\).
4. **Announce** the interval \(\hat y \pm q̂\,\hat\sigma\) and the target coverage
   \(1-\alpha\), with \(n\) shown.

Worked example. \(n = 100\), \(\alpha = 0{,}10\). The conformal rank is
\(\lceil 101 \times 0{,}90\rceil = 91\). The empirical quantile at 0.90 falls lower
(between ranks 90 and 91, interpolation). The conformal interval is
**strictly wider**. With 1,000 points the difference is tiny; with 100, the
guarantee fails if the correction is omitted.

If \(k > n\) (set too small for \(\alpha\)), `conformal_quantile` raises
`InvariantViolation`. No silent infinite bound.

## The exchangeability assumption

The coverage \(\ge 1-\alpha\) holds if the plan to bound is **exchangeable** with
the \(n\) calibration plans. A plan *selected* by Frank-Wolfe to maximize \(\hat y\)
no longer quite is: the optimizer seeks out the network's errors (winner's curse).
Each bound therefore declares its **regime**: `"exchangeable"` (coverage is
guaranteed) or `"selected"` (plan chosen by the optimizer: the interval is computed
the same way, but its coverage is not guaranteed and the report does not announce
it). `legalize` always returns `"selected"`. A procedure valid under selection
(conformal selection, Jin & Candès 2023; weighted conformal, Fannjiang et al. 2022)
is planned in phase 6.4 of the plan. For an exchangeable plan, if an exchangeability
test rejects, `build_bound` returns `None` and the certificate carries
`NOT EVALUABLE`.

## Direction of the indicators

- sDA, UDI, view: the **lower bound** is published (`>=`).
- ASE: the **upper bound** is published (`<=`).

One calibrator per indicator: the errors do not have the same scale.

## Pessimistic objective

Frank-Wolfe maximizes \(J = \hat\mu - q̂\,\hat\sigma\), not \(\hat\mu\). Where
\(\hat\sigma\) widens, \(J\) drops, and the optimizer backs off. Class:
`light.objective.Daylight`. The float \(q̂\) is injected: `light` does not import
`uq`.

Formula: [statistics](../formulas/statistics.md).
Tutorial: [calibrate a surrogate](../tutorials/calibrate-a-surrogate.md).
