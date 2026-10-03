# Compare two methods honestly

**Problem.** The classic legalizer ignores north. Two identical apartments,
one facing north, the other south, receive the same L1 repair. We want a
repair that *prefers* daylight, without training a network yet.

**Solution.** Same function, one parameter: `objective=AnalyticSurrogate()`.
The surrogate is a closed-form model (useful depth \(2{,}5\times\) head height,
orientation harmonics). Frank-Wolfe reuses the LP oracle of milestone 2.

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
ctx_n = ax.Context(
    structure=ax.Structure(()),
    orientation=ax.Orientation(0.0),
    outline=outline,
    regulation=ax.Regulation((), 1.0),
)
ctx_s = ax.Context(
    structure=ax.Structure(()),
    orientation=ax.Orientation(180.0),
    outline=outline,
    regulation=ax.Regulation((), 1.0),
)
q_l1 = ax.legalize(plan, ctx_n)
q_n = ax.legalize(plan, ctx_n, objective=AnalyticSurrogate())
q_s = ax.legalize(plan, ctx_s, objective=AnalyticSurrogate())
print(q_l1.certificate.geometry.valid)
print(q_n.rooms == q_s.rooms)
```

**Result.**

```
True
False
```

The geometric proof stays **exact** in all three cases. The two performance
plans differ: north is no longer a dummy coordinate. The surrogate's score is
**not** a measured sDA; no conformal coverage is claimed (milestone 5).

**What to remember.** `objective=None` reproduces milestone 2. A surrogate
does not change the domain: it changes the vector \(c\) of the oracle. Compare L1
and performance legalization on the *same* order, never by mixing the guarantees.

Formulas: [analytic surrogate](../formulas/analytic-surrogate.md),
[Frank-Wolfe](../formulas/frank-wolfe.md),
[shared oracle](../concepts/shared-oracle.md).

**See also:** [Repair a plan](01-repair-a-plan.md),
[Performance legalization](../tutorials/performance-legalization.md)
