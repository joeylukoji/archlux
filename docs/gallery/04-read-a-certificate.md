# Read a certificate

**Problem.** The solver returned a valid plan. We want to know, on one page,
what is **proved** and what is **predicted** — without mixing them.

**Solution.**

```python
import archlux as ax
from archlux.types import PerformanceBound, Manifest

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
    structure=ax.Structure(load_bearing_walls=()),
    orientation=ax.Orientation(deg=12.0),
    outline=outline,
    regulation=ax.Regulation(min_areas=(), min_width=1.0),
)
q = ax.legalize(plan, ctx)
bound = PerformanceBound(
    indicator="sDA",
    value=56.2,
    lower=51.4,
    upper=61.0,
    coverage=0.90,
    n_calibration=1284,
    regime="exchangeable",
)
certificate = ax.Certificate(
    geometry=q.certificate.geometry,
    performance=bound,
    duals=q.certificate.duals,
    manifest=Manifest(version="0.4.0", timestamp="2026-09-09T00:00:00Z", seed=17),
)
print(certificate.report())
```

Here the bound is built by hand to read the template. `regime="exchangeable"`
declares that the plan is exchangeable with the calibration set (a held-out plan,
for example): it is the only case where the 90 % coverage is guaranteed.
`legalize(..., objective=..., calibration=...)` attaches the bound itself, but in the
`"selected"` regime: the optimizer chose the plan, and the report then writes
`[PREDICTION: selected plan, coverage NOT guaranteed]`.

**Result.** The text separates `[EXACT]` and `[PREDICTION: coverage 90 %]`.
`n_calibration` (1,284) is visible. The `NOT EVALUABLE` section is always
there: summer comfort, systems, materials.

**What to remember.** "No overlap" can be re-checked by counting areas.
"sDA ≥ 51.4" is a 90 % coverage **against the frozen oracle**
(split-flux), not a regulatory sDA. If `performance is None`, the report
writes `NOT EVALUABLE` in the prediction section rather than inventing a
number.

**See also:** [The two guarantees](../concepts/two-guarantees.md),
[Dual diagnostics](05-dual-diagnostics.md),
[Conformal prediction](../concepts/conformal-prediction.md).
