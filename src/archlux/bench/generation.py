"""Milestone 8: legalize **actually generated** plans, not corrupted ones.

The evaluation and summary of ``experiments/j8_generation.py``, moved into the library
(PLAN.md phase 4, block 16; ``ARCHITECTURE.md`` §11: a script longer than 50 lines
signals a missing library function). The code is unchanged: the published outputs are
byte-identical, timings aside.

What this milestone adds to milestone 7
---------------------------------------
``j7_msd_repair.py`` measures the repair of MSD plans **corrupted by hand**. The fault is
known there, which is ideal to attribute a failure, but the amplitudes are calibrated on
no real generator (``data.corruption`` says so). Here the inputs come out of a published
model and are never damaged by us: this is the **external validity** check of the
milestone 7 table.

The generator
-------------
HouseDiffusion (Shabani, Hosseini, Furukawa, CVPR 2023), official weights
``model250000.pt``, trained on RPLAN. The model returns vector coordinates, so no image
vectorization stands between it and us.

**It is sampled over 1000 steps, without respacing.** ``gaussian_diffusion.py:270`` only
enables the **discrete** denoising branch (the one that snaps corners to the grid) for
``t < 32``; subsampling the trajectory short-circuits it. Median distance from a corner
to its axis-aligned rectangle, by number of steps: 0.750 m at 20, 0.188 m at 80, 0.000 m
at 200 and at 1000. At 1000 steps the generated rooms are **exactly** axis-aligned.

License boundary
----------------
HouseDiffusion is under **GPL v3, commercial use forbidden**. archlux is under
Apache-2.0 and does not import it: sampling lives in a separate script
(``vendor/j8_generer.py``, outside the repository); the boundary is the JSONL file.

Layering
--------
``bench`` may not import ``api``: :func:`evaluate_generated` receives ``legalize`` as a
parameter (the script passes :func:`archlux.legalize`).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import replace
from typing import Any

import numpy as np

from archlux.certify.proof import verify_exactly
from archlux.data.generated import DEFAULT_MIN_WIDTH, generated_plan
from archlux.errors import GapNeedsTiling, GridNotRecoverable, Infeasible, InvariantViolation
from archlux.export.wilson import wilson_interval
from archlux.types import Context, Plan, Regulation

__all__ = [
    "BUDGETS",
    "FIELDS",
    "INTACT_SIDE_M",
    "WIDTHS",
    "evaluate_generated",
    "summarize_generation",
]

BUDGETS = (0, 4, 8, 16)
"""Swept repair budgets.

The default of ``api.legalize`` is 4, tuned on corrupted plans. A generator output
belongs to another regime: the whole curve is measured rather than reporting the single
convenient point."""

WIDTHS = (0.0, 0.25, 1.00, 1.80)
"""Minimum widths swept at the largest budget, besides the nominal one
(:data:`archlux.data.generated.DEFAULT_MIN_WIDTH`)."""

INTACT_SIDE_M = 0.50
"""Below this side, it is no longer a room but a residue that the drawing does not even
show. Used to tell "valid" from "valid AND program preserved"."""

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
"""Columns of the raw CSV, in order."""


def evaluate_generated(
    plan_json: dict[str, Any], scale: float, *, legalize: Callable[..., Any]
) -> list[dict[str, object]] | str:
    """Raw rows of one generated plan, one per run, or the reason it is rejected.

    Two sweeps, not their product: the budgets at nominal width, then the widths at the
    best budget. The second exists because ``min_width = 0`` lets the LP annihilate a
    room to close a gap: what this threshold costs and buys must be shown.

    Parameters
    ----------
    plan_json : dict
        One JSONL record of the generator.
    scale : float
        Unit-to-metre factor, see :func:`archlux.data.generated.generated_scale`.
    legalize : callable
        :func:`archlux.legalize` (``bench`` may not import ``api``).

    Returns
    -------
    list of dict or str
        One row per run, keyed by :data:`FIELDS`; or the rejection reason of
        :func:`archlux.data.generated.generated_plan`.
    """
    built = generated_plan(plan_json, scale)
    if isinstance(built, str):
        return built
    plan, context, diagnostic = built
    fixed = {
        "plan_id": plan_json["id"],
        "program": "+".join(plan_json["programme"]),  # lang-ok: vendor key
        # Missing from the first JSONL files: the field did not exist yet.
        "graph": plan_json.get("graphe", "etoile"),  # lang-ok: vendor key
        "n_rooms": len(plan.rooms),
        "valid_before": verify_exactly(plan, context).valid,
        "cells": diagnostic.cells,
        "overlaps_before": f"{diagnostic.overlaps:.3f}",
        "gap_share_before": f"{diagnostic.gap_share:.4f}",
        "hole_share_before": f"{diagnostic.hole_share:.4f}",
        "fragments_before": diagnostic.fragments,
        "size_m": f"{diagnostic.size:.3f}",
    }
    rows: list[dict[str, object]] = []
    for mode, budget, width in _runs():
        start = time.perf_counter()
        run_context = replace(context, regulation=Regulation(min_areas=(), min_width=width))
        outcome = _outcome(plan, run_context, mode, budget, legalize)
        moved = str(outcome["max_displacement_m"])
        rows.append(
            {
                **fixed,
                **outcome,
                "mode": mode,
                "budget": budget if mode == "pavage" else "",
                "min_width": f"{width:.2f}",
                "relative_displacement": (f"{float(moved) / diagnostic.size:.4f}" if moved else ""),
                "time_ms": f"{(time.perf_counter() - start) * 1000:.3f}",
            }
        )
    return rows


def _runs() -> list[tuple[str, int, float]]:
    """The runs of one plan: budgets at the nominal width, then widths at the largest.

    Returns
    -------
    list of (str, int, float)
        ``(mode, budget, min_width)`` of each run, in order.
    """
    runs = [("base", 0, DEFAULT_MIN_WIDTH)]
    runs += [("pavage", b, DEFAULT_MIN_WIDTH) for b in BUDGETS]
    runs += [("pavage", BUDGETS[-1], width) for width in WIDTHS if width != DEFAULT_MIN_WIDTH]
    return runs


def _outcome(
    plan: Plan, run_context: Context, mode: str, budget: int, legalize: Callable[..., Any]
) -> dict[str, object]:
    """Result columns of one run: validity, displacement, smallest side, status.

    Parameters
    ----------
    plan : Plan
        Generated plan.
    run_context : Context
        Its context, with the run's minimum width.
    mode : str
        ``"base"`` (``legalize`` alone) or ``"pavage"`` (``tiling=True``).
    budget : int
        Repair budget of the run.
    legalize : callable
        :func:`archlux.legalize`.

    Returns
    -------
    dict
        The columns ``status``, ``valid_after``, ``max_displacement_m``,
        ``n_rooms_after``, ``min_side_after`` and ``intact``.
    """
    # CSV values (`mode`, `status`) stay as published: the raw rows are data.
    out: dict[str, object] = {
        "status": "ok",
        "valid_after": False,
        "max_displacement_m": "",
        "n_rooms_after": "",
        "min_side_after": "",
        "intact": "",
    }
    try:
        fixed = legalize(plan, run_context, tiling=(mode == "pavage"), repair_budget=budget)
        valid = fixed.certificate.geometry.valid
        smallest = min(min(p.w, p.h) for p in fixed.rooms)
        out["valid_after"] = valid
        out["max_displacement_m"] = f"{fixed.certificate.geometry.max_displacement:.6f}"
        out["n_rooms_after"] = str(len(fixed.rooms))
        out["min_side_after"] = f"{smallest:.4f}"
        # "Intact" = valid AND no room shrunk to a residue. Counting rooms is not enough:
        # a room crushed to 0 m stays in the count.
        out["intact"] = str(bool(valid and smallest >= INTACT_SIDE_M))
    except Infeasible:
        out["status"] = "infaisable"  # lang-ok: published CSV value
    except GridNotRecoverable:
        out["status"] = "trame"  # lang-ok: published CSV value
    except (InvariantViolation, GapNeedsTiling):
        # `legalize` alone refuses a gap up front (GapNeedsTiling) where it used to return
        # an invalid plan: same published value.
        out["status"] = "invariant_viole"  # lang-ok: published CSV value
    return out


def _repair_table(at_nominal: list[dict[str, str]]) -> list[str]:
    """Repair rate per mode and budget, at the nominal width.

    Parameters
    ----------
    at_nominal : list of dict
        Raw rows at the nominal width.

    Returns
    -------
    list of str
        The Markdown table lines.
    """
    rows = [
        "| mode | budget | n | repaired | 95 % CI | median t | median displacement |",
        "|---|--:|--:|--:|:--:|--:|--:|",
    ]
    for mode, budget in [("base", "")] + [("pavage", str(b)) for b in BUDGETS]:
        batch = [r for r in at_nominal if r["mode"] == mode and r["budget"] == budget]
        if batch:
            rows.append(_repair_row(mode, budget, batch))
    return rows


def _filled(batch: list[dict[str, str]], column: str) -> list[float]:
    """The non-empty values of ``column``, as floats.

    Parameters
    ----------
    batch : list of dict
        Raw rows.
    column : str
        Column name.

    Returns
    -------
    list of float
        The values that are not empty.
    """
    return [float(r[column]) for r in batch if r[column]]


def _repair_row(mode: str, budget: str, batch: list[dict[str, str]]) -> str:
    """One line of the repair table.

    Parameters
    ----------
    mode : str
        ``"base"`` or ``"pavage"``.
    budget : str
        Repair budget, as written in the CSV.
    batch : list of dict
        Raw rows of that mode and budget, at the nominal width.

    Returns
    -------
    str
        The Markdown table line.
    """
    ok = sum(r["valid_after"] == "True" for r in batch)
    low, high = wilson_interval(ok, len(batch))
    elapsed = np.median([float(r["time_ms"]) for r in batch])
    moved = _filled(batch, "max_displacement_m")
    rel = _filled(batch, "relative_displacement")
    median_moved = f"{np.median(moved):.2f} m ({np.median(rel):.0%} of the side)" if moved else "—"
    name = "`legalize` alone" if mode == "base" else "`tiling=True`"
    return (
        f"| {name} | {budget or '—'} | {len(batch)} | "
        f"**{100 * ok / len(batch):.1f} %** | [{100 * low:.1f}, {100 * high:.1f}] | "
        f"{elapsed:.1f} ms | {median_moved} |"
    )


def _width_table(records: list[dict[str, str]], last: str) -> list[str]:
    """Sweep of the minimum width at the largest budget.

    The decisive table: without a strictly positive floor, closing a gap by shrinking a
    room to zero is the cheapest solution, and the plan comes out "valid" minus one room.

    Parameters
    ----------
    records : list of dict
        All raw rows.
    last : str
        The largest budget, as written in the CSV.

    Returns
    -------
    list of str
        The Markdown table lines.
    """
    widths = [
        "| `min_width` | n | valid | **of which no room crushed** | "
        "smallest side | median displacement |",
        "|--:|--:|--:|--:|--:|--:|",
    ]
    for width in sorted({*WIDTHS, DEFAULT_MIN_WIDTH}):
        key = f"{width:.2f}"
        batch = [
            r
            for r in records
            if r["mode"] == "pavage" and r["budget"] == last and r["min_width"] == key
        ]
        if batch:
            widths.append(_width_row(width, batch))
    return widths


def _width_row(width: float, batch: list[dict[str, str]]) -> str:
    """One line of the minimum-width table.

    Parameters
    ----------
    width : float
        Minimum width of the runs, in metres.
    batch : list of dict
        Raw rows at that width and the largest budget.

    Returns
    -------
    str
        The Markdown table line.
    """
    ok = sum(r["valid_after"] == "True" for r in batch)
    sound = sum(r["intact"] == "True" for r in batch)
    b1, h1 = wilson_interval(ok, len(batch))
    b2, h2 = wilson_interval(sound, len(batch))
    sides = _filled(batch, "min_side_after")
    rel = _filled(batch, "relative_displacement")
    mark = " *(nominal)*" if width == DEFAULT_MIN_WIDTH else ""
    return (
        f"| {width:.2f} m{mark} | {len(batch)} | "
        f"{100 * ok / len(batch):.1f} % [{100 * b1:.1f}, {100 * h1:.1f}] | "
        f"**{100 * sound / len(batch):.1f} %** [{100 * b2:.1f}, {100 * h2:.1f}] | "
        f"{(f'{np.median(sides):.3f} m' if sides else '—')} | "
        f"{(f'{np.median(rel):.0%}' if rel else '—')} |"
    )


def _size_table(final_batch: list[dict[str, str]], last: str) -> list[str]:
    """Repair rate by number of rooms, at the largest budget.

    It explains the rate, not connectivity: at a fixed budget the bounded repair fixes a
    bounded number of cells, and the grid swells as (2n-1)^2 when no edges coincide.

    Parameters
    ----------
    final_batch : list of dict
        Raw rows at the largest budget and nominal width.
    last : str
        The largest budget, as written in the CSV.

    Returns
    -------
    list of str
        The Markdown table lines.
    """
    by_n: dict[int, list[dict[str, str]]] = {}
    for r in final_batch:
        by_n.setdefault(int(r["n_rooms"]), []).append(r)
    by_size = [f"| rooms | n | repaired (budget {last}) | median cells |", "|--:|--:|--:|--:|"]
    for k in sorted(by_n):
        records_k = by_n[k]
        ok = sum(x["valid_after"] == "True" for x in records_k)
        cel = np.median([float(x["cells"]) for x in records_k])
        by_size.append(
            f"| {k} | {len(records_k)} | {100 * ok / len(records_k):.1f} % | {cel:.0f} |"
        )
    return by_size


def _topology_table(final_batch: list[dict[str, str]], last: str) -> list[str]:
    """Repair rate by topology of the access graph, at the largest budget.

    HouseDiffusion's ``door_mask`` derives from it: it is an input of the model, not
    staging. If the rate were sensitive to it, no global figure would be interpretable.

    Parameters
    ----------
    final_batch : list of dict
        Raw rows at the largest budget and nominal width.
    last : str
        The largest budget, as written in the CSV.

    Returns
    -------
    list of str
        The Markdown table lines.
    """
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
    return topology


def summarize_generation(
    records: list[dict[str, str]], scale: float, rejections: dict[str, int]
) -> str:
    """Summary of a milestone 8 run, Wilson intervals included.

    Parameters
    ----------
    records : list of dict
        The raw rows, as read back from the CSV (all values are strings).
    scale : float
        Unit-to-metre factor used to build the plans.
    rejections : dict of str to int
        Count of records rejected at construction, by reason.

    Returns
    -------
    str
        The Markdown summary.
    """
    # The main tables cover the nominal width; the width sweep has its own table below.
    nominal = f"{DEFAULT_MIN_WIDTH:.2f}"
    at_nominal = [r for r in records if r["min_width"] == nominal]
    diag = [r for r in at_nominal if r["mode"] == "base"]
    last = str(BUDGETS[-1])
    final_batch = [r for r in at_nominal if r["mode"] == "pavage" and r["budget"] == last]
    return (
        _header(records, diag, scale)
        + "## State of the generator outputs\n\n"
        + _outputs_table(diag)
        + "## Repair\n\n"
        f"Regulation `min_width = {DEFAULT_MIN_WIDTH:.2f} m`.\n\n"
        + "\n".join(_repair_table(at_nominal))
        + "\n\n"
        "## What a floor on the width costs, and what it buys\n\n"
        + "\n".join(_width_table(records, last))
        + "\n\n"
        "## Repair by program size\n\n" + "\n".join(_size_table(final_batch, last)) + "\n\n"
        "## Repair by access-graph topology\n\n"
        + "\n".join(_topology_table(final_batch, last))
        + "\n\n"
        f"## Failures\n\n{_failure_reasons(records)}\n\n"
        f"## Rejections at construction\n\n{rejections or 'none'}\n"
    )


def _outputs_table(diag: list[dict[str, str]]) -> str:
    """Table of the generator outputs' defects, before any repair.

    Parameters
    ----------
    diag : list of dict
        One raw row per plan (mode ``"base"``, nominal width).

    Returns
    -------
    str
        The Markdown table, followed by a blank line.
    """
    columns = ("cells", "overlaps_before", "gap_share_before", "hole_share_before")
    cells, overlaps, gap, hole = (np.asarray(_filled(diag, c)) for c in columns)
    fragments = np.asarray(_filled(diag, "fragments_before"))
    return (
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
    )


def _failure_reasons(records: list[dict[str, str]]) -> dict[str, int]:
    """Count of failed runs, by mode, budget and status.

    Parameters
    ----------
    records : list of dict
        Raw rows.

    Returns
    -------
    dict of str to int
        ``"{mode}{budget}:{status}"`` to count, in order of first appearance.
    """
    reasons: dict[str, int] = {}
    for r in records:
        if r["status"] != "ok":
            key = f"{r['mode']}{r['budget']}:{r['status']}"
            reasons[key] = reasons.get(key, 0) + 1
    return reasons


def _header(records: list[dict[str, str]], diag: list[dict[str, str]], scale: float) -> str:
    """Title and opening paragraph of the summary.

    Parameters
    ----------
    records : list of dict
        Raw rows.
    diag : list of dict
        One raw row per plan (mode ``"base"``, nominal width).
    scale : float
        Unit-to-metre factor used to build the plans.

    Returns
    -------
    str
        The Markdown title and paragraphs, followed by a blank line.
    """
    plans = {r["plan_id"] for r in records}
    before = sum(r["valid_before"] == "True" for r in records if r["mode"] == "base")
    return (
        "# Milestone 8: legalizing **actually generated** plans\n\n"
        f"HouseDiffusion (CVPR 2023), official weights `model250000.pt`, RPLAN, "
        f"**1000 steps** without respacing. {len(plans)} plans, "
        f"{len(plans) and int(np.sum([float(r['n_rooms']) for r in diag]))} rooms. "
        f"Scale {scale:.3f} m/unit, matched to the MSD median area (79.0 m²).\n\n"
        f"**{before} plan(s) out of {len(plans)} are valid before correction.**\n\n"
    )
