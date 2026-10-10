"""Legalize the three example plans and print what changed (PLAN.md 5.3).

Run from the repository root: ``python examples/legalize_examples.py``.
"""

from pathlib import Path

import archlux as ax

here = Path(__file__).parent
areas = (("living_room", 14.0), ("bedroom", 9.0), ("kitchen", 4.0), ("bathroom", 3.0))
regulation = ax.Regulation(min_areas=areas, min_width=0.90)
for name in ("t2", "t3_load_bearing", "generated"):
    plan = ax.Plan.from_json(here / f"{name}.json")
    walls = tuple(w for w in plan.walls if w.load_bearing)
    ctx = ax.Context(ax.Structure(walls), ax.Orientation(0.0), regulation, outline=plan.outline)
    fixed = ax.legalize(plan, ctx, tiling=True)
    assert fixed.certificate is not None  # legalize always certifies what it returns
    proof = fixed.certificate.geometry
    print(f"{name}: valid={proof.valid}, max displacement {proof.max_displacement:.2f} m")
