# Performance legalization

After [classic legalization](getting-started.md), one can choose, *among the
valid plans with the same order*, the one the surrogate judges brightest.

## Problem

The L1 repairer ignores orientation. Two identical apartments, north and
south, receive the same repair. We want to prefer daylight **without** leaving
the polytope.

## Solution

```python
import archlux as ax
from archlux.light.analytic import AnalyticSurrogate

outline = ((0.0, 0.0), (12.0, 0.0), (12.0, 9.0), (0.0, 9.0))
plan = ax.Plan(
    rooms=(
        ax.Room(id="living_room", type="living_room", x=0.0, y=0.0, w=7.0, h=9.0),
        ax.Room(id="bedroom", type="bedroom", x=6.0, y=0.0, w=6.0, h=9.0),
    ),
    walls=(),
    openings=(),
    outline=outline,
)
ctx = ax.Context(
    structure=ax.Structure(()),
    orientation=ax.Orientation(0.0),
    outline=outline,
    regulation=ax.Regulation((), 1.0),
)

q = ax.legalize(plan, ctx, objective=AnalyticSurrogate())
assert q.certificate.geometry.valid
assert q.certificate.performance is None  # bound via certify.bound, not via api
```

The analytic surrogate learns nothing: useful depth, an 8-sector table,
placement towards the south. It serves to validate the flow (polytope → Frank-Wolfe →
proof) before any simulation.

`objective=None` (the default) stays strictly milestone 2. An object that does not
implement `Surrogate` raises `TypeError`.

## What to remember

The network (`LearnedSurrogate`) is [milestone 4](train-a-surrogate.md).
The conformal bound is attached after calibration:
[calibrate a surrogate](calibrate-a-surrogate.md).
Compare methods with `bench.compare(..., evaluate_by=oracle)` — never
with the surrogate itself.

**See also:** [Compare two methods](../gallery/02-compare-two-methods.md),
[Shared oracle](../concepts/shared-oracle.md).
