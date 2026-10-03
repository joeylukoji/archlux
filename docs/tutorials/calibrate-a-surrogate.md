# Calibrate a surrogate

Training and the gradient checkpoint are in
[milestone 4](train-a-surrogate.md). Here: freeze, score, bound.

Do not open the calibration set before the weights are frozen. Reading the
calibration set during training makes the conformal coverage **wrong**, and no
loss test reports it.

The blocks of this page run in order, as is, in a few seconds.
The data sets are drawn at random and labelled by the frozen oracle
`SplitFluxOracle`; in a real project, they are read from the `train/`,
`calibration/` and `test/` directories.

## 0. Starting point: a trained model

The plan, the context and the model of the [previous tutorial](train-a-surrogate.md),
shorter:

```python
from pathlib import Path

import numpy as np

import archlux as ax
from archlux.light.base import DenseSurrogate
from archlux.light.split_flux import SplitFluxOracle

outline = ((0.0, 0.0), (12.0, 0.0), (12.0, 9.0), (0.0, 9.0))
plan = ax.Plan(
    rooms=(
        ax.Room(id="living_room", type="living_room", x=0.0, y=0.0, w=6.05, h=9.0),
        ax.Room(id="bedroom", type="bedroom", x=6.0, y=0.0, w=6.0, h=5.0),
        ax.Room(id="bathroom", type="bathroom", x=6.0, y=5.03, w=6.0, h=3.97),
    ),
    walls=(),
    openings=(),
    outline=outline,
)
ctx = ax.Context(
    structure=ax.Structure(load_bearing_walls=()),
    orientation=ax.Orientation(deg=12.0),
    outline=outline,
    regulation=ax.Regulation(min_areas=(("bathroom", 5.0),), min_width=1.0),
)


def layout(rng: np.random.Generator) -> np.ndarray:
    """Living room on the left, bedroom and bathroom stacked on the right."""
    w, h = rng.uniform(4.0, 8.0), rng.uniform(3.0, 6.0)
    return np.array([0, 0, w, 9, w, 0, 12 - w, h, w, h, 12 - w, 9 - h], dtype=float)


oracle = SplitFluxOracle()
rng = np.random.default_rng(17)
xs = tuple(layout(rng) for _ in range(80))
ys = np.array([oracle.evaluate(x, ctx.orientation) for x in xs])
model = DenseSurrogate(largeur=8)
model.fit(xs, ys, (ctx.orientation,) * len(xs), seed=17, epoques=30)

for subdirectory in ("train", "calibration", "test"):
    Path("splits/v1", subdirectory).mkdir(parents=True, exist_ok=True)
```

## 1. Freeze, then issue the token

```python
from archlux.uq.registry import DataManagement, freeze_and_issue

token = freeze_and_issue(model, timestamp="2026-09-09T12:00:00Z")
calibration = DataManagement("splits/v1").for_calibration(token, model)
```

If a weight moves after the freeze, `for_calibration(..., model)` raises
`ModelModified`.

## 2. Fit one calibrator per indicator

```python
from archlux.uq.conformal import ConformalCalibrator

calibration_plans = [layout(rng) for _ in range(200)]  # never seen during training
predictions = np.array([model.evaluate(x, ctx.orientation) for x in calibration_plans])
truths = np.array([oracle.evaluate(x, ctx.orientation) for x in calibration_plans])
uncertainties = np.array([model.uncertainty(x, ctx.orientation) for x in calibration_plans])

cal = ConformalCalibrator(indicator="sDA")
cal.fit(predictions, truths, uncertainties, alpha=0.10)

x_new = layout(rng)  # drawn like the calibration set: exchangeable with it
prediction = model.evaluate(x_new, ctx.orientation)
sigma = model.uncertainty(x_new, ctx.orientation)
bound = cal.borne(prediction, sigma, ">=", regime="exchangeable")
assert bound.lower <= prediction <= bound.upper
# bound.lower, bound.coverage, bound.n_calibration
```

The rank is \(\lceil(n+1)(1-\alpha)\rceil\), not `np.quantile(s, 0.90)`. ASE
is fitted separately, with `sens="<="`. `regime` is mandatory: `"exchangeable"`
for a plan drawn like the calibration set, `"selected"` for a plan chosen by an
optimizer, whose coverage is then not guaranteed.

## 3. Pessimistic objective

```python
from archlux.light.objective import Daylight

objective = Daylight(model, q_chapeau=cal.q)  # pessimiste=True by default
q = ax.legalize(
    plan, ctx, objective=objective, calibration=cal.snapshot(), budget=0.5, tiling=True
)
assert q.certificate is not None and q.certificate.performance is not None
assert q.certificate.performance.regime == "selected"
print(q.certificate.report())
```

`q.certificate.performance` then carries the conformal interval of the returned plan,
in the `"selected"` regime: the optimizer chose this plan, where the
surrogate overestimates the most (winner's curse), so the nominal coverage
is **not** guaranteed. The report says so. To publish a coverage,
re-evaluate the plan with the oracle.

## 4. Drift and `NOT EVALUABLE`

The production scores are those of plans returned after calibration, once their
true value is known: \(|y - \hat{y}| / \hat{\sigma}\), as at fitting time.

```python
from archlux.certify.bound import build_bound
from archlux.uq.drift import check_drift

production_plans = [layout(rng) for _ in range(50)]
production_scores = np.array(
    [
        abs(oracle.evaluate(x, ctx.orientation) - model.evaluate(x, ctx.orientation))
        / model.uncertainty(x, ctx.orientation)
        for x in production_plans
    ]
)
drift = check_drift(production_scores, cal.snapshot(), seed=17)
certificate_bound = build_bound(
    prediction, cal.snapshot(), drift, uncertainty=sigma, regime="exchangeable"
)
```

These plans are drawn like the calibration set: the test detects no drift and
`certificate_bound` is an interval. Errors three times larger, on the other hand, are
detected:

```python
strong_drift = check_drift(3.0 * production_scores, cal.snapshot(), seed=17)
assert not strong_drift.echangeable
assert (
    build_bound(
        prediction, cal.snapshot(), strong_drift, uncertainty=sigma, regime="exchangeable"
    )
    is None
)
```

If `drift.echangeable` is false, `build_bound` returns `None`: the report
writes `NOT EVALUABLE` rather than an interval. The converse is not a proof:
`echangeable=True` means "drift not detected", and with a small sample the test
has almost no power.

Frozen oracle: `SplitFluxOracle` (split-flux closed form). Not Radiance, not ground truth.

**See also:** [Conformal prediction](../concepts/conformal-prediction.md),
[Statistics](../formulas/statistics.md),
[The two guarantees](../concepts/two-guarantees.md).
