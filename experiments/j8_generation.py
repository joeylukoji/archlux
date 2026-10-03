"""Milestone 8: legalize **actually generated** plans, not corrupted ones.

What this milestone adds to milestone 7
---------------------------------------
`j7_msd_repair.py` measures the repair of MSD plans **corrupted by hand**. The fault
is known there, which is ideal to attribute a failure, but the amplitudes are
calibrated on no real generator (`data.corruption` says so). Here the inputs come out
of a published model and are never damaged by us: this is the **external validity**
check of the milestone 7 table.

The generator
-------------
HouseDiffusion (Shabani, Hosseini, Furukawa, CVPR 2023), official weights
`model250000.pt`, trained on RPLAN. The model returns vector coordinates, so no image
vectorization stands between it and us.

**It is sampled over 1000 steps, without respacing.** This is not a matter of
comfort: `gaussian_diffusion.py:270` only enables the **discrete** denoising branch
(the very contribution of the paper, the one that snaps corners to the grid) for
``t < 32``. Subsampling the trajectory short-circuits it and creates a misalignment
that does not belong to the model. Median distance from a corner to its axis-aligned
rectangle, by number of steps:

===== ==========
steps  distance
===== ==========
20     0.750 m
80     0.188 m
200    0.000 m
1000   0.000 m
===== ==========

At 1000 steps the generated rooms are **exactly** axis-aligned: no bounding-box
approximation enters the measurement below.

License boundary
----------------
HouseDiffusion is under **GPL v3, commercial use forbidden**. archlux is under
Apache-2.0 and does not import it: sampling lives in a separate script
(`vendor/j8_generer.py`, outside the repository) and the boundary between the two is
the JSONL file read here.

Usage: j8_generation.py [plans.jsonl] [n_max] [label]
"""

from __future__ import annotations

import csv as csvmod
import json
import sys
import time
from dataclasses import replace
from pathlib import Path

import numpy as np
from shapely.geometry import box
from shapely.ops import unary_union

import archlux as ax
from archlux.certify.proof import verify_exactly
from archlux.errors import GapNeedsTiling, GridNotRecoverable
from archlux.export.wilson import wilson_interval
from archlux.geom.diagnostic import Diagnostic, diagnose
from archlux.types import (
    Context,
    Orientation,
    Plan,
    Regulation,
    Room,
    Structure,
)

DEFAULT = Path("D:/archlux-donnees/j8_plans.jsonl")

# Median area of an MSD apartment, measured on 1200 apartments: 79.0 m2.
# RPLAN coordinates have no unit; the scale is set so that the median generated area
# equals the MSD one, so that the displacements of milestones 7 and 8 are comparable.
# No validity rate depends on it: overlap and gap are scale invariant.
TARGET_AREA_M2 = 79.0
MIN_SIDE_M = 0.05  # below this threshold a room is degenerate, not narrow

# Swept budgets. The default of `api.legalize` is 4, tuned on corrupted plans. A
# generator output belongs to another regime: the whole curve is measured rather than
# reporting the single convenient point.
BUDGETS = (0, 4, 8, 16)

# Minimum width of a room, in metres. This parameter is NOT a compliance detail here:
# without a strictly positive floor, the cheapest way to close a gap is to shrink a
# room to zero, and the plan comes out "valid" with an annihilated room. Measured at
# `min_width = 0`: 61 % of the plans reported as repaired contained at least one room
# with a side of exactly zero.
#
# Milestone 7 set 0.0 for a good reason: a 1.80 m threshold broke 52 MSD plans out of
# 60 that were **already valid**. That caution does not apply here: 0 / 740 generated
# plans are valid to begin with, so the threshold cannot break anything.
DEFAULT_WIDTH = 0.50
WIDTHS = (0.0, 0.25, 1.00, 1.80)

# Below this side, it is no longer a room but a residue that the drawing does not even
# show. Used to tell "valid" from "valid AND program preserved".
INTACT_SIDE_M = 0.50

FIELDS = (
    "plan_id",
    "program",
    "graph",
    "n_rooms",
    "mode",
    "budget",
    "min_width",
    "valid_before",
    "valid_after",
    "n_rooms_after",
    "min_side_after",
    "intact",
    "cells",
    "overlaps_before",
    "gap_share_before",
    "hole_share_before",
    "fragments_before",
    "size_m",
    "max_displacement_m",
    "relative_displacement",
    "time_ms",
    "status",
)


def _boxes(plan_json: dict, scale: float) -> list[tuple[str, tuple[float, ...]]]:
    """(type, (x, y, w, h)) in metres, one entry per generated room."""
    out = []
    for room in plan_json["pieces"]:  # key of the vendor JSONL format
        corners = np.asarray(room["coins"], dtype=float) * scale
        x0, y0 = float(corners[:, 0].min()), float(corners[:, 1].min())
        x1, y1 = float(corners[:, 0].max()), float(corners[:, 1].max())
        out.append((str(room["type"]), (x0, y0, x1 - x0, y1 - y0)))
    return out


def _scale(rows: list[dict]) -> float:
    """Unit -> metre factor matching the median generated area to the MSD one."""
    areas = []
    for plan_json in rows:
        shapes = [box(x, y, x + w, y + h) for _, (x, y, w, h) in _boxes(plan_json, 1.0)]
        union = unary_union(shapes)
        if not union.is_empty:
            areas.append(union.area)
    return float(np.sqrt(TARGET_AREA_M2 / np.median(areas)))


def _build(plan_json: dict, scale: float) -> tuple[Plan, Context, Diagnostic] | str:
    """archlux plan + input diagnostic, or the rejection reason in plain words."""
    boxes = _boxes(plan_json, scale)
    if any(w < MIN_SIDE_M or h < MIN_SIDE_M for _, (_, _, w, h) in boxes):
        return "degenerate room"

    rooms = tuple(
        Room(id=f"p{rank:03d}", type=room_type, x=x, y=y, w=w, h=h)
        for rank, (room_type, (x, y, w, h)) in enumerate(boxes)
    )
    shapes = [box(p.x, p.y, p.x + p.w, p.y + p.h) for p in rooms]
    union = unary_union(shapes)
    if union.is_empty:
        return "empty union"

    # The target outline is the **bounding box** of the union. HouseDiffusion receives
    # no envelope as a condition: it invents its own footprint. Imposing the tiling of
    # this box therefore also squares the footprint; this is deliberate, and the
    # reported displacement gives its cost.
    x0, y0, x1, y1 = union.bounds
    outline = ((x0, y0), (x1, y0), (x1, y1), (x0, y1))

    plan = Plan(rooms=rooms, walls=(), openings=(), outline=outline)
    context = Context(
        structure=Structure(load_bearing_walls=(), columns=()),
        orientation=Orientation(deg=0.0),
        outline=outline,
        # The regulation is replaced run by run: see DEFAULT_WIDTH.
        regulation=Regulation(min_areas=(), min_width=DEFAULT_WIDTH),
        program=tuple(sorted(set(plan_json["programme"]))),
    )
    return plan, context, diagnose(plan)


def _summarize(raw: Path, scale: float, rejections: dict[str, int]) -> str:
    """Summary tables, Wilson intervals included."""
    with raw.open(encoding="utf-8") as stream:
        records = list(csvmod.DictReader(stream))
    plans = {r["plan_id"] for r in records}
    before = sum(r["valid_before"] == "True" for r in records if r["mode"] == "base")
    # The main tables cover the nominal width; the width sweep has its own table below.
    nominal = f"{DEFAULT_WIDTH:.2f}"
    at_nominal = [r for r in records if r["min_width"] == nominal]
    diag = [r for r in at_nominal if r["mode"] == "base"]
    cells = np.asarray([float(r["cells"]) for r in diag])
    overlaps = np.asarray([float(r["overlaps_before"]) for r in diag])
    gap = np.asarray([float(r["gap_share_before"]) for r in diag])
    hole = np.asarray([float(r["hole_share_before"]) for r in diag])
    fragments = np.asarray([float(r["fragments_before"]) for r in diag])

    rows = [
        "| mode | budget | n | repaired | 95 % CI | median t | median displacement |",
        "|---|--:|--:|--:|:--:|--:|--:|",
    ]
    for mode, budget in [("base", "")] + [("pavage", str(b)) for b in BUDGETS]:
        batch = [r for r in at_nominal if r["mode"] == mode and r["budget"] == budget]
        if not batch:
            continue
        ok = sum(r["valid_after"] == "True" for r in batch)
        low, high = wilson_interval(ok, len(batch))
        elapsed = np.median([float(r["time_ms"]) for r in batch])
        moved = [float(r["max_displacement_m"]) for r in batch if r["max_displacement_m"]]
        rel = [float(r["relative_displacement"]) for r in batch if r["relative_displacement"]]
        median_moved = (
            f"{np.median(moved):.2f} m ({np.median(rel):.0%} of the side)" if moved else "—"
        )
        name = "`legalize` alone" if mode == "base" else "`tiling=True`"
        rows.append(
            f"| {name} | {budget or '—'} | {len(batch)} | "
            f"**{100 * ok / len(batch):.1f} %** | [{100 * low:.1f}, {100 * high:.1f}] | "
            f"{elapsed:.1f} ms | {median_moved} |"
        )

    # Breakdown by number of rooms. It explains the rate, not connectivity: at a fixed
    # budget the bounded repair fixes a bounded number of cells, and the grid swells as
    # (2n-1)^2 when no edges coincide.
    last = str(BUDGETS[-1])
    final_batch = [r for r in at_nominal if r["mode"] == "pavage" and r["budget"] == last]

    # Sweep of the minimum width. This is the decisive table: without a strictly
    # positive floor, closing a gap by shrinking a room to zero is the cheapest
    # solution, and the plan comes out "valid" minus one room.
    widths = [
        "| `min_width` | n | valid | **of which no room crushed** | "
        "smallest side | median displacement |",
        "|--:|--:|--:|--:|--:|--:|",
    ]
    for width in sorted({*WIDTHS, DEFAULT_WIDTH}):
        key = f"{width:.2f}"
        batch = [
            r
            for r in records
            if r["mode"] == "pavage" and r["budget"] == last and r["min_width"] == key
        ]
        if not batch:
            continue
        ok = sum(r["valid_after"] == "True" for r in batch)
        sound = sum(r["intact"] == "True" for r in batch)
        b1, h1 = wilson_interval(ok, len(batch))
        b2, h2 = wilson_interval(sound, len(batch))
        sides = [float(r["min_side_after"]) for r in batch if r["min_side_after"]]
        rel = [float(r["relative_displacement"]) for r in batch if r["relative_displacement"]]
        mark = " *(nominal)*" if width == DEFAULT_WIDTH else ""
        widths.append(
            f"| {width:.2f} m{mark} | {len(batch)} | "
            f"{100 * ok / len(batch):.1f} % [{100 * b1:.1f}, {100 * h1:.1f}] | "
            f"**{100 * sound / len(batch):.1f} %** [{100 * b2:.1f}, {100 * h2:.1f}] | "
            f"{(f'{np.median(sides):.3f} m' if sides else '—')} | "
            f"{(f'{np.median(rel):.0%}' if rel else '—')} |"
        )
    by_n: dict[int, list[dict[str, str]]] = {}
    for r in final_batch:
        by_n.setdefault(int(r["n_rooms"]), []).append(r)
    by_size = [
        f"| rooms | n | repaired (budget {last}) | median cells |",
        "|--:|--:|--:|--:|",
    ]
    for k in sorted(by_n):
        records_k = by_n[k]
        ok = sum(x["valid_after"] == "True" for x in records_k)
        cel = np.median([float(x["cells"]) for x in records_k])
        by_size.append(
            f"| {k} | {len(records_k)} | {100 * ok / len(records_k):.1f} % | {cel:.0f} |"
        )

    # Breakdown by topology of the access graph. HouseDiffusion's `door_mask` derives
    # from it: it is an input of the model, not staging. If the rate were sensitive to
    # it, no global figure would be interpretable.
    by_topology: dict[str, list[dict[str, str]]] = {}
    for r in final_batch:
        by_topology.setdefault(r["graph"], []).append(r)
    topology = [
        f"| topology | n | repaired (budget {last}) | median gap | "
        "median overlap | median fragments |",
        "|---|--:|--:|--:|--:|--:|",
    ]
    for key in sorted(by_topology):
        records_t = by_topology[key]
        ok = sum(x["valid_after"] == "True" for x in records_t)
        topology.append(
            f"| `{key}` | {len(records_t)} | {100 * ok / len(records_t):.1f} % | "
            f"{np.median([float(x['gap_share_before']) for x in records_t]):.1%} | "
            f"{np.median([float(x['overlaps_before']) for x in records_t]):.2f} | "
            f"{np.median([float(x['fragments_before']) for x in records_t]):.0f} |"
        )

    reasons: dict[str, int] = {}
    for r in records:
        if r["status"] != "ok":
            key = f"{r['mode']}{r['budget']}:{r['status']}"
            reasons[key] = reasons.get(key, 0) + 1

    return (
        "# Milestone 8: legalizing **actually generated** plans\n\n"
        f"HouseDiffusion (CVPR 2023), official weights `model250000.pt`, RPLAN, "
        f"**1000 steps** without respacing. {len(plans)} plans, "
        f"{len(plans) and int(np.sum([float(r['n_rooms']) for r in diag]))} rooms. "
        f"Scale {scale:.3f} m/unit, matched to the MSD median area (79.0 m²).\n\n"
        f"**{before} plan(s) out of {len(plans)} are valid before correction.**\n\n"
        "## State of the generator outputs\n\n"
        "| | median | mean | p95 |\n|---|--:|--:|--:|\n"
        f"| rooms overlapped per room | {np.median(overlaps):.2f} | "
        f"{overlaps.mean():.2f} | {np.quantile(overlaps, 0.95):.2f} |\n"
        f"| gap share of the envelope | {np.median(gap):.1%} | "
        f"{gap.mean():.1%} | {np.quantile(gap, 0.95):.1%} |\n"
        f"| of which **interior** holes | {np.median(hole):.1%} | "
        f"{hole.mean():.1%} | {np.quantile(hole, 0.95):.1%} |\n"
        f"| disjoint fragments of the union | {np.median(fragments):.0f} | "
        f"{fragments.mean():.2f} | {np.quantile(fragments, 0.95):.0f} |\n"
        f"| cells of the implicit grid | {np.median(cells):.0f} | "
        f"{cells.mean():.0f} | {np.quantile(cells, 0.95):.0f} |\n\n"
        "## Repair\n\n"
        f"Regulation `min_width = {DEFAULT_WIDTH:.2f} m`.\n\n" + "\n".join(rows) + "\n\n"
        "## What a floor on the width costs, and what it buys\n\n" + "\n".join(widths) + "\n\n"
        "## Repair by program size\n\n" + "\n".join(by_size) + "\n\n"
        "## Repair by access-graph topology\n\n" + "\n".join(topology) + "\n\n"
        f"## Failures\n\n{reasons}\n\n"
        f"## Rejections at construction\n\n{rejections or 'none'}\n"
    )


def main() -> None:
    # The command line is read HERE and not at module level: `j8_visuals` imports
    # `_build` and `_scale`, and parsing at import time would make the import fail on
    # its own arguments.
    plans = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT
    n_max = int(sys.argv[2]) if len(sys.argv) > 2 else 10**9
    # Output label: two graph conditionings are measured, and their results must not
    # overwrite each other.
    label = sys.argv[3] if len(sys.argv) > 3 else plans.stem
    rows = [
        json.loads(line)
        for line in plans.read_text(encoding="utf-8").splitlines()[:n_max]
        if line.strip()
    ]
    if not rows:
        raise SystemExit(f"no plan in {plans}")
    scale = _scale(rows)
    print(f"{len(rows)} generated plans, scale {scale:.4f} m/unit")

    Path("results").mkdir(exist_ok=True)
    output = Path(f"results/j8_{label}_raw.csv")
    rejections: dict[str, int] = {}
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csvmod.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        for plan_json in rows:
            built = _build(plan_json, scale)
            if isinstance(built, str):
                rejections[built] = rejections.get(built, 0) + 1
                continue
            plan, context, diagnostic = built
            before = verify_exactly(plan, context).valid
            # Two sweeps, not their product: the budgets at nominal width, then the
            # widths at the best budget. The second exists because `min_width = 0`
            # lets the LP annihilate a room to close a gap: what this threshold costs
            # and buys must be shown.
            runs = [("base", 0, DEFAULT_WIDTH)]
            runs += [("pavage", b, DEFAULT_WIDTH) for b in BUDGETS]
            runs += [("pavage", BUDGETS[-1], width) for width in WIDTHS if width != DEFAULT_WIDTH]
            for mode, budget, width in runs:
                start = time.perf_counter()
                # CSV values (`mode`, `status`) stay as published: the raw rows are data.
                status, valid, moved, n_after = "ok", False, "", ""
                min_side, intact = "", ""
                run_context = replace(
                    context,
                    regulation=Regulation(min_areas=(), min_width=width),
                )
                try:
                    fixed = ax.legalize(
                        plan,
                        run_context,
                        tiling=(mode == "pavage"),
                        repair_budget=budget,
                    )
                    valid = fixed.certificate.geometry.valid
                    moved = f"{fixed.certificate.geometry.max_displacement:.6f}"
                    n_after = str(len(fixed.rooms))
                    smallest = min(min(p.w, p.h) for p in fixed.rooms)
                    min_side = f"{smallest:.4f}"
                    # "Intact" = valid AND no room shrunk to a residue. Counting rooms
                    # is not enough: a room crushed to 0 m stays in the count.
                    intact = str(bool(valid and smallest >= INTACT_SIDE_M))
                except ax.Infeasible:
                    status = "infaisable"  # lang-ok: published CSV value
                except GridNotRecoverable:
                    status = "trame"  # lang-ok: published CSV value
                except (ax.InvariantViolation, GapNeedsTiling):
                    # `legalize` alone now refuses a gap up front (GapNeedsTiling) where
                    # it used to return an invalid plan: same published value.
                    status = "invariant_viole"  # lang-ok: published CSV value
                writer.writerow(
                    {
                        "plan_id": plan_json["id"],
                        "program": "+".join(plan_json["programme"]),
                        # Missing from the first JSONL files: the field did not exist yet.
                        "graph": plan_json.get("graphe", "etoile"),
                        "n_rooms": len(plan.rooms),
                        "mode": mode,
                        "budget": budget if mode == "pavage" else "",
                        "min_width": f"{width:.2f}",
                        "valid_before": before,
                        "valid_after": valid,
                        "n_rooms_after": n_after,
                        "min_side_after": min_side,
                        "intact": intact,
                        "cells": diagnostic.cells,
                        "overlaps_before": f"{diagnostic.overlaps:.3f}",
                        "gap_share_before": f"{diagnostic.gap_share:.4f}",
                        "hole_share_before": f"{diagnostic.hole_share:.4f}",
                        "fragments_before": diagnostic.fragments,
                        "size_m": f"{diagnostic.size:.3f}",
                        "max_displacement_m": moved,
                        "relative_displacement": (
                            f"{float(moved) / diagnostic.size:.4f}" if moved else ""
                        ),
                        "time_ms": f"{(time.perf_counter() - start) * 1000:.3f}",
                        "status": status,
                    }
                )
    print("raw rows written:", output)
    summary = Path(f"results/j8_{label}.md")
    summary.write_text(_summarize(output, scale, rejections), encoding="utf-8")
    print("summary written:", summary)
    if rejections:
        print("rejections:", rejections)


if __name__ == "__main__":
    main()
