# Getting started

Install the core (without PyTorch):

```bash
pip install archlux
```

## One plan, one context, one repair

The envelope and the rooms below are those of the published test corpus
(`CONTEXTE_DEFAUT`: 12 m × 9 m) — not a geometry invented for the docs.

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
assert q.certificate is not None
assert q.certificate.geometry.valid
assert q.certificate.performance is None  # classic legalization: no bound
print(q.certificate.report())
```

`legalize` returns a plan **proved** valid (tiling, areas, load-bearing walls).
The `[PREDICTION]` section of the report stays `NOT EVALUABLE` as long as no
conformal calibration has been attached.

## Load from a file

A generator writes its plans as JSON. The file below imitates a typical output:
the living room overlaps the bedroom by 5 cm, and a 3 cm gap separates the
bedroom from the bathroom. It is written here so that the example is self-contained;
in practice, it comes from the generator.

```python
from pathlib import Path

Path("generator_output.json").write_text(
    """{
      "schema": "2",
      "outline": [[0, 0], [12, 0], [12, 9], [0, 9]],
      "rooms": [
        {"id": "living_room", "type": "living_room", "x": 0, "y": 0, "w": 6.05, "h": 9},
        {"id": "bedroom", "type": "bedroom", "x": 6, "y": 0, "w": 6, "h": 5},
        {"id": "bathroom", "type": "bathroom", "x": 6, "y": 5.03, "w": 6, "h": 3.97}
      ],
      "walls": [], "openings": [], "certificate": null
    }""",
    encoding="utf-8",
)

plan = ax.Plan.from_json("generator_output.json")
q = ax.legalize(plan, ctx, tiling=True)
assert q.certificate is not None and q.certificate.geometry.valid
q.to_json("legalized_plan.json")
```

`tiling=True` requires the rooms to cover the outline exactly. It is needed
as soon as the input can contain a gap, which is the case of generator outputs:
without it, the separations are inequalities, the plan with a hole is already its own
closest point, and the exact verification rejects it (`InvariantViolation`).

The JSON schema is versioned, and `certificate` is `null` on a proposed plan; see the
[reference](../reference/schema-json.md).

## Next

| Need | Page |
|---|---|
| See the same example with commentary | [Repair a plan](../gallery/01-repair-a-plan.md) |
| Understand proof ≠ prediction | [The two guarantees](../concepts/two-guarantees.md) |
| Maximize daylight under validity | [Performance legalization](performance-legalization.md) |
| What the system does not check | [Limitations](../limitations.md) |
