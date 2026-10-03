# Repair a generated plan

Example geometry: the **12 m × 9 m** envelope of the published test corpus
(`CONTEXTE_DEFAUT`), not a room invented for the documentation.

**Problem.** A generator produced two rooms that overlap by one metre, while
covering the envelope. The plan cannot be built.

**Solution.**

```python
import archlux as ax

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
    orientation=ax.Orientation(deg=0.0),
    outline=outline,
    regulation=ax.Regulation(min_areas=(), min_width=1.0),
)
q = ax.legalize(plan, ctx)
print(q.certificate.geometry.valid)
print(round(q.certificate.geometry.max_displacement, 2))
```

**Result.**

```
True
1.0
```

The living room goes from 7 m to 6 m wide; the bedroom does not move. No overlap,
no gap. The proof is **exact**: `certify.proof` recounts the areas, independently of
the solver.

**What to remember.** `legalize` minimizes the L1 displacement over the polytope of
valid plans with the same relative order. The layout (who is left of whom) is
kept; only the dimensions move.

Formula: [L1 epigraph](../formulas/l1-epigraph.md),
[pipeline](../formulas/pipeline.md).

**See also:** [Detect infeasibility](03-detect-infeasibility.md),
[The polytope](../concepts/polytope.md)
