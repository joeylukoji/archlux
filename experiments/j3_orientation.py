"""One 2x2 plan, eight orientations, milestone 3 review (PLAN.md phase 2).

Analytic surrogate, with and without minimum areas (12 m² per room type). Raw rows and
one SVG sheet per variant, deterministic, byte-stable. The dependence of the move on the
azimuth is a circular-linear fit, not a Rayleigh test: 8 equally spaced angles are
uniform by design.
"""

import csv
import math
import sys
from pathlib import Path

import archlux as ax
from archlux.export.svg import sheet
from archlux.light.analytique import AnalyticSurrogate
from archlux.orient.circulaire import circular_linear_regression as fit

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "results")
C = ((0.0, 0.0), (12.0, 0.0), (12.0, 9.0), (0.0, 9.0))
ROOMS = (("sw", "living_room", 0, 0), ("se", "bedroom", 6, 0), ("nw", "living_room", 0, 4.5))
ROOMS += (("ne", "bedroom", 6, 4.5),)
PLAN = ax.Plan(
    tuple(ax.Room(id=i, type=t, x=x, y=y, w=6, h=4.5) for i, t, x, y in ROOMS), (), (), C
)
FIELDS = ("minimum_area_m2", "deg", "moved_from_l1_m", "h_sw", "h_nw", "smallest_room_m2")
with (OUT / "j3_orientation.csv").open("w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, FIELDS, lineterminator="\n")
    writer.writeheader()
    for minimum in (0.0, 12.0):
        ref = ax.Regulation(tuple((t, minimum) for t in ("bedroom", "living_room") if minimum), 1.0)
        panels, moves = [], []
        for deg in range(0, 360, 45):
            ctx = ax.Context(
                structure=ax.Structure(()),
                orientation=ax.Orientation(float(deg)),
                outline=C,
                regulation=ref,
            )
            l1 = {r.id: r for r in ax.legalize(PLAN, ctx).rooms}
            out = ax.legalize(PLAN, ctx, objective=AnalyticSurrogate())
            moved = sum(abs(r.w - l1[r.id].w) + abs(r.h - l1[r.id].h) for r in out.rooms)
            moves.append(moved)
            rooms = {r.id: r for r in out.rooms}
            smallest = min(r.w * r.h for r in out.rooms)
            row = (minimum, deg, f"{moved:.6f}", f"{rooms['sw'].h:.6f}", f"{rooms['nw'].h:.6f}")
            writer.writerow(dict(zip(FIELDS, (*row, f"{smallest:.6f}"), strict=True)))
            panels.append((out, f"{deg} deg"))
        name = f"j3_orientation_min{minimum:g}.svg"
        (OUT / name).write_text(sheet(tuple(panels), colonnes=8), encoding="utf-8")
        r = fit(list(range(0, 360, 45)), moves)  # moves ~ a cos + b sin + c, descriptive only
        r2 = 1 - sum(r.residus**2) / sum((m - sum(moves) / 8) ** 2 for m in moves)
        amp, peak = math.hypot(r.a, r.b), math.degrees(math.atan2(r.b, r.a)) % 360
        print(f"minimum {minimum:g}: amplitude {amp:.2f} m at {peak:.0f} deg, R2 {r2:.2f}")
