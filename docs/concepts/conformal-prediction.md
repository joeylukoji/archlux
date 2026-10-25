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
is planned in phase 6.4 of the plan; the calibration on the frozen policy's outputs
below is measured, not yet wired into `legalize`. For an exchangeable plan, if an exchangeability
test rejects, `build_bound` returns `None` and the certificate carries
`NOT EVALUABLE`.

## Exchangeability with grouped data

Variants of one dwelling (its azimuths, its corruptions) are **not** exchangeable with
each other: they share the plan. Two consequences, both enforced by
`bench.selection`:

- the sets are drawn on **source plans** (`data.provenance.split_by_group`), and
  `check_no_group_leakage` refuses a source that reaches two of train, validation,
  calibration and test;
- each calibration uses **one variant per source**; the test set may keep all of
  them, but its intervals then resample sources, not rows.

The guarantee is **marginal**: averaged over the draw of the calibration set and over
plans. It says nothing about a given orientation or prediction level; a stratum may
be far below \(1-\alpha\) while the marginal coverage holds.

## Measured: coverage after selection

Protocol `experiments/j5_selection.py` (`results/j5_selection.md`): 400 synthetic
two-room source plans x 4 azimuths, sets 40 / 10 / 25 / 25 % of the sources, the
analytic surrogate rescaled on train (kept because it wins on validation), the frozen
`SplitFluxOracle` as reference, \(\alpha = 0.10\), 10 repetitions with a fresh split,
50 calibration plans per half. Mean of the repetitions, Student 95 % interval over
them:

| Procedure | Coverage | Mean width | Guarantee |
|---|--:|--:|---|
| passive calibration, passive test plans | 88.6 % [85.9 ; 91.4] | 31.3 | yes (exchangeable) |
| passive calibration, plans chosen by Frank-Wolfe | **76.0 %** [71.9 ; 80.0] | 31.3 | **no** |
| calibration on the frozen policy's outputs | 91.3 % [88.2 ; 94.4] | 38.0 | yes (see below) |

Per stratum (passive calibrator on selected plans): west-facing 39.7 %, south 64.1 %,
highest prediction tercile 49.4 %. Even the passive calibrator covers only 61.7 % of
the south-facing passive plans: marginal coverage, not conditional.

The paper's B4 (89.8 % passive, 87.8 % selected) used intervals 4.7 target standard
deviations wide; with a surrogate rescaled on a training set the intervals narrow and
the selection effect is no longer small. The passive number does **not** carry over
to selected plans, and the size of the drop depends on how precise the surrogate is.

**Calibration on the frozen policy.** Freeze the surrogate and the policy (its
\(\hat q\) comes from the passive half of the calibration set). Run the policy from a
**second, disjoint** half and calibrate on its outputs. Under exchangeable source
plans, the policy's output on a new source is exchangeable with these, and the split
conformal guarantee holds again for that policy, at the price of wider intervals
(+21 % here). It holds for that frozen policy only: a policy re-tuned on these scores,
or a change of surrogate, needs a new calibration.

**When the guarantee is not available**, the system says so rather than publish the
nominal level: `bench.selection.guarantee` returns `refused` below
`minimal_n_conformal(alpha)` and `not guaranteed` for a passive calibrator applied to
selected plans, and `below_target` flags any procedure or stratum whose
repetition-level interval lies under \(1-\alpha\). `legalize` keeps returning
`regime="selected"` until a policy calibration is wired into the certificate.

## Direction of the indicators

- sDA, UDI, view: the **lower bound** is published (`>=`).
- ASE: the **upper bound** is published (`<=`).

One calibrator per indicator: the errors do not have the same scale.

## Pessimistic objective

Frank-Wolfe maximizes \(J = \hat\mu - q̂\,\hat\sigma\), not \(\hat\mu\). Where
\(\hat\sigma\) widens, \(J\) drops, and the optimizer backs off. Class:
`light.objective.Daylight`. The float \(q̂\) is injected: `light` does not import
`uq`.

**Measured limit.** Every shipped surrogate returns a **constant** \(\hat\sigma\)
(`AnalyticSurrogate.sigma_nominal`, `DenseSurrogate.uncertainty`). The penalty is then
a constant shift: it changes \(J\), not its gradient, and the optimizer lands on the
same plan with or without it (`results/ablations.md`: `fw_surrogate` and
`fw_surrogate_no_penalty` give identical outputs on all 270 cases). The pessimistic
objective only backs off once \(\hat\sigma\) varies with the plan.

Formula: [statistics](../formulas/statistics.md).
Tutorial: [calibrate a surrogate](../tutorials/calibrate-a-surrogate.md).
