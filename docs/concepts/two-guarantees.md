# The two guarantees

An `archlux` certificate carries **two claims of different kinds**. Confusing them —
presenting a prediction with the confidence of a proof — is the mistake the system is
designed to make hard.

## What the certificate says

| | Geometry | Daylight performance |
|---|---|---|
| **Typical sentence** | "this plan has no overlap" | "this plan will reach at least 51.4 %" |
| **Kind** | Proof | Prediction with a margin |
| **Check** | Finite inspection, \(O(n^2)\) | Coverage \(\ge 1-\alpha\) on a calibration set |
| **Can it be wrong?** | No (up to the rounding tolerance) | Yes, in at most \(\alpha\) of the cases |
| **Type** | `GeometricProof` — no probability field | `PerformanceBound` — `coverage`, `n_calibration` and `regime` mandatory |
| **Banner** | `[EXACT]` | `[PREDICTION: coverage 90 %]` (exchangeable plan) or `[PREDICTION: selected plan, coverage NOT guaranteed]` |

The geometry is a predicate on rectangles: it can be recounted. Daylight is a
**frozen** oracle (`SplitFluxOracle`, BRE split-flux): the bound says "at least nine
times out of ten, the value of *this* oracle will fall above the announced threshold".
It is not an LM-83 sDA, it is not Radiance.

## How to read them side by side

```
GEOMETRY                                        [EXACT]
  Overlap                none          verified

PERFORMANCE                        [PREDICTION: coverage 90 %]
  sDA   >= 51.40   (predicted 56.20, margin 4.80)
  calibration: 1284 evaluations of the frozen oracle

NOT EVALUABLE
  Summer comfort, technical systems, materials: out of scope
```

- If `performance is None`, the prediction section shows `NOT EVALUABLE`: the
  system refuses to invent a coverage.
- `n_calibration` is shown: a bound on 50 points is not worth one on 1,284.
- The **regime** is shown. Coverage is announced only for a plan that is
  exchangeable with the calibration (`regime="exchangeable"`). For a plan chosen by
  the optimizer (`regime="selected"`, which is what `legalize(..., calibration=...)`
  returns), the banner says "coverage NOT guaranteed" and the report asks for the
  plan to be re-evaluated with the oracle.
- Nothing aggregates the two kinds into a single score.

## What to remember

Legalization **proves** that the plan is a valid tiling. The surrogate **predicts** an
indicator and the calibrator **bounds** that prediction. A reader who reads
"51.4 %" the way they read "no overlap" has the wrong guarantee in mind.

**See also:** [Conformal prediction](conformal-prediction.md),
[Read a certificate](../gallery/04-read-a-certificate.md),
[Limitations](../limitations.md).
