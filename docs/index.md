# archlux

**Repair a generated plan towards geometric validity while preserving its daylight
performance. The geometry is guaranteed; the performance is bounded.**

A generator produced this plan: the living room overlaps the bedroom by 5 cm, and a
3 cm gap separates the bedroom from the bathroom. `legalize` repairs it and proves the
result.

```python
from pathlib import Path

import archlux as ax

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
ctx = ax.Context(
    structure=ax.Structure(load_bearing_walls=()),
    orientation=ax.Orientation(deg=0.0),
    outline=plan.outline,
    regulation=ax.Regulation(min_areas=(("bathroom", 5.0),), min_width=1.0),
)
q = ax.legalize(plan, ctx, tiling=True)  # tiling: the rooms cover the whole outline
print(q.certificate.report())
```

The quickest way to start: the [example gallery](gallery/01-repair-a-plan.md).
The most important thing to understand: [the two guarantees](concepts/two-guarantees.md).
To redo the computations: the [formula book](formulas/index.md) (statement, derivation,
source, use cases).
