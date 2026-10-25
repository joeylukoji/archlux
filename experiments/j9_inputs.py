"""Milestone 9 inputs: rebuild the six B9 plans from the published SVG sheets.

Why this file exists
--------------------
`j9_orientation.py` reads the generated plans from `j8_plans_divers.jsonl`, a file that
lives outside the repository (`D:/archlux-donnees/`) and is not in this container. The
published sheets are the only trace left of the six plans of B9:

- `results/visuals/divers/repaired/hdXXXX.svg` draws the **proposed** (generated) plan
  and its repair side by side, at one scale (`archlux.export.svg.compare`);
- `results/orientation/hdXXXX.svg` draws the **old** B9 variants, one per azimuth, at
  one scale (`archlux.export.svg.sheet`);
- `results/j8_divers_raw.csv` gives `size_m`, the square root of the outline area, to
  three decimals: it fixes the pixel-to-metre scale.

The renderer writes coordinates to 0.01 px, about 0.3 mm at these scales, and `size_m`
fixes the scale to about 1e-4 relative. The rebuilt plans are therefore the published
ones **up to about one millimetre**, not bit-exact copies; the outline is put at the
origin (the generator's absolute offset is lost, and no score depends on it).
Coordinates within `SNAP_MM` of each other are merged before checking the plan, so
that rounding does not open sub-millimetre gaps.

Output: `results/j9_inputs.json`, with each plan's provenance (source files and
their SHA-256): the six B9 plans (proposed, published repair, old variants) and, for
the timing runs, the proposed plan of every published repaired sheet.

Usage: j9_inputs.py
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from archlux.io.json_io import to_dict
from archlux.types import Plan, Room

PLANS = ("hd0012", "hd0013", "hd0016", "hd0018", "hd0022", "hd0026")
REPAIRED = Path("results/visuals/divers/repaired")
ORIENTATION = Path("results/orientation")
SIZES = Path("results/j8_divers_raw.csv")
OUT = Path("results/j9_inputs.json")
PANEL_WIDTH, MARGIN, SPACING = 380.0, 28.0, 12.0  # archlux.export.svg constants
SNAP_MM = 3.0
_NS = "{http://www.w3.org/2000/svg}"
_TITLE = re.compile(r"^(\d+)°")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sizes() -> dict[str, float]:
    with SIZES.open(encoding="utf-8", newline="") as handle:
        return {row["plan_id"]: float(row["size_m"]) for row in csv.DictReader(handle)}


def _panels(path: Path) -> list[dict[str, object]]:
    """Split a sheet into panels: title, outline polygon and room rectangles, in px."""
    root = ET.parse(path).getroot()
    panels: list[dict[str, object]] = []
    pending: list[float] | None = None
    for element in root:
        tag = element.tag.removeprefix(_NS)
        if tag == "rect" and element.get("fill") == "#ffffff":
            panels.append(
                {
                    "origin": (float(element.get("x", 0)) - 1, float(element.get("y", 0)) - 1),
                    "rooms": [],
                    "title": "",
                    "outline": None,
                }
            )
        elif not panels:
            continue
        elif tag == "text" and element.get("font-weight") == "600":
            panels[-1]["title"] = element.text or ""
        elif tag == "polygon":
            points = [
                tuple(map(float, p.split(","))) for p in (element.get("points") or "").split()
            ]
            panels[-1]["outline"] = points
        elif tag == "rect" and element.get("fill-opacity") is not None:
            pending = [float(element.get(k, 0)) for k in ("x", "y", "width", "height")]
        elif tag == "text" and pending is not None:
            rooms = panels[-1]["rooms"]
            assert isinstance(rooms, list)
            rooms.append((element.text or "room", *pending))
            pending = None
    return panels


def _snap(values: list[float], tolerance: float) -> dict[float, float]:
    """Merge values closer than ``tolerance`` (chained), keeping the fixed ones."""
    ordered = sorted(set(values))
    groups: list[list[float]] = []
    for v in ordered:
        if groups and v - groups[-1][-1] <= tolerance:
            groups[-1].append(v)
        else:
            groups.append([v])
    mapping: dict[float, float] = {}
    for group in groups:
        centre = sum(group) / len(group)
        for v in group:
            mapping[v] = centre
    return mapping


def rebuild(panel: dict[str, object], size_m: float, ids: list[str] | None = None) -> Plan:
    """Metric plan of one panel, outline at the origin, edges snapped to ``SNAP_MM``."""
    outline_px = panel["outline"]
    assert isinstance(outline_px, list)
    xs = [p[0] for p in outline_px]
    ys = [p[1] for p in outline_px]
    w_px, h_px = max(xs) - min(xs), max(ys) - min(ys)
    scale = math.sqrt(w_px * h_px) / size_m
    width, height = w_px / scale, h_px / scale
    left, top = min(xs), min(ys)
    raw = []
    rooms_px = panel["rooms"]
    assert isinstance(rooms_px, list)
    for label, x, y, w, h in rooms_px:
        x0 = (x - left) / scale
        y0 = height - (y - top + h) / scale
        raw.append((label, x0, y0, x0 + w / scale, y0 + h / scale))
    tol = SNAP_MM / 1000
    snap_x = _snap([0.0, width, *(v for r in raw for v in (r[1], r[3]))], tol)
    snap_y = _snap([0.0, height, *(v for r in raw for v in (r[2], r[4]))], tol)
    fix_x = {snap_x[0.0]: 0.0, snap_x[width]: width}
    fix_y = {snap_y[0.0]: 0.0, snap_y[height]: height}

    def sx(v: float) -> float:
        return round(fix_x.get(snap_x[v], snap_x[v]), 6)

    def sy(v: float) -> float:
        return round(fix_y.get(snap_y[v], snap_y[v]), 6)

    rooms = tuple(
        Room(
            id=ids[k] if ids else f"p{k:03d}",
            type=label,
            x=sx(x0),
            y=sy(y0),
            w=round(sx(x1) - sx(x0), 6),
            h=round(sy(y1) - sy(y0), 6),
        )
        for k, (label, x0, y0, x1, y1) in enumerate(raw)
    )
    w6, h6 = round(width, 6), round(height, 6)
    outline = ((0.0, 0.0), (w6, 0.0), (w6, h6), (0.0, h6))
    return Plan(rooms=rooms, walls=(), openings=(), outline=outline)


def main() -> None:
    sizes = _sizes()
    out: dict[str, object] = {
        "note": (
            "Rebuilt from published SVG sheets to about 1 mm; outline at the origin. "
            "Not the original generator output (j8_plans_divers.jsonl is not available)."
        ),
        "snap_mm": SNAP_MM,
        "plans": {},
    }
    plans = out["plans"]
    assert isinstance(plans, dict)
    for name in PLANS:
        repaired = REPAIRED / f"{name}.svg"
        variants = ORIENTATION / f"{name}.svg"
        before, after = _panels(repaired)[:2]
        proposed = rebuild(before, sizes[name])
        legalized = rebuild(after, sizes[name])
        old = {}
        for panel in _panels(variants):
            match = _TITLE.match(str(panel["title"]))
            if match and "no variant" not in str(panel["title"]):
                old[match.group(1)] = to_dict(rebuild(panel, sizes[name]))
        plans[name] = {
            "size_m": sizes[name],
            "proposed": to_dict(proposed),
            "legalized_published": to_dict(legalized),
            "old_variants": old,
            "sources": {str(p): _sha(p) for p in (repaired, variants, SIZES)},
        }
    # Timing set: every published repaired sheet of the `divers` conditioning. The
    # article timed "20 plans x 8 azimuths" without naming them; these are not
    # necessarily the same 20.
    timing: dict[str, object] = {}
    for sheet_path in sorted(REPAIRED.glob("hd*.svg")):
        before = _panels(sheet_path)[0]
        timing[sheet_path.stem] = {
            "size_m": sizes[sheet_path.stem],
            "proposed": to_dict(rebuild(before, sizes[sheet_path.stem])),
            "sources": {str(sheet_path): _sha(sheet_path), str(SIZES): _sha(SIZES)},
        }
    out["timing_plans"] = timing
    OUT.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{len(PLANS)} plans -> {OUT}")


if __name__ == "__main__":
    main()
