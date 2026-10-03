# Detect infeasibility

**Problem.** Two rooms each require a minimum width of 8 m in a 12 m envelope.
No valid plan exists: saying so is better than returning a wrong plan.

**Solution.**

```python
import archlux as ax

outline = ((0.0, 0.0), (12.0, 0.0), (12.0, 9.0), (0.0, 9.0))
plan = ax.Plan(
    rooms=(
        ax.Room(id="a", type="living_room", x=0.0, y=0.0, w=8.0, h=8.0),
        ax.Room(id="b", type="living_room", x=8.0, y=0.0, w=8.0, h=8.0),
    ),
    walls=(),
    openings=(),
    outline=outline,
)
ctx = ax.Context(
    structure=ax.Structure(load_bearing_walls=()),
    orientation=ax.Orientation(deg=0.0),
    outline=outline,
    regulation=ax.Regulation(min_areas=(), min_width=8.0),
)
try:
    ax.legalize(plan, ctx)
except ax.Infeasible as err:
    print(sorted(err.origins))
```

**Result.**

```
['contour droit b', 'separation horizontale a|b']
```

The Farkas certificate names the conflicting subsystem: the two horizontal
separations and the right edges. It is not an error message, it is a **proof** of
non-existence (Farkas' lemma). The labels are the solver's own row labels, still in
French in this version.

**What to remember.** `Infeasible` is not a solver failure. It is the program
that does not hold. The `origins` are domain labels, never row indices.

Formula: [Farkas and duals](../formulas/farkas.md).

**See also:** [Repair a plan](01-repair-a-plan.md),
[The polytope](../concepts/polytope.md)
