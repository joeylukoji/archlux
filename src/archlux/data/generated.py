"""Load generated plans: axis-aligned boxes of a generator's JSONL into a :class:`Plan`.

The milestone 8-9 scripts (``experiments/j8_generation.py``, ``j8_visuals.py``,
``j9_orientation.py``) read HouseDiffusion outputs. The loader lived in one of them and
the other two imported its private functions, which ``ARCHITECTURE.md`` §11 forbids; it
is the library function those scripts were missing (PLAN.md phase 4, block 16).

The JSONL format is the vendor script's (``vendor/j8_generer.py``, outside the
repository): each line holds ``pieces`` (rooms with a ``type`` and their ``coins``,
corner coordinates in RPLAN units) and ``programme`` (the room types). Those key names
are part of the file format and stay as written.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from shapely.geometry import box
from shapely.ops import unary_union

from archlux.geom.diagnostic import Diagnostic, diagnose
from archlux.types import Context, Orientation, Plan, Regulation, Room, Structure

__all__ = [
    "DEFAULT_MIN_WIDTH",
    "MIN_SIDE_M",
    "TARGET_AREA_M2",
    "generated_boxes",
    "generated_plan",
    "generated_scale",
]

TARGET_AREA_M2 = 79.0
"""Median area of an MSD apartment, measured on 1200 apartments, in square metres.

RPLAN coordinates have no unit; the scale is set so that the median generated area
equals the MSD one, so that the displacements of milestones 7 and 8 are comparable. No
validity rate depends on it: overlap and gap are scale invariant."""

MIN_SIDE_M = 0.05
"""Below this side a generated room is degenerate, not narrow, in metres."""

DEFAULT_MIN_WIDTH = 0.50
"""Regulatory minimum width attached to a generated plan, in metres.

Not a compliance detail: without a strictly positive floor, the cheapest way to close a
gap is to shrink a room to zero, and the plan comes out "valid" with an annihilated
room (measured at 0: 61 % of the plans reported as repaired had a room with a side of
exactly zero). Milestone 7 used 0.0 because 1.80 m broke already valid MSD plans; none
of the 740 generated plans is valid to begin with, so the floor cannot break any."""


def generated_boxes(
    plan_json: dict[str, Any], scale: float
) -> list[tuple[str, tuple[float, float, float, float]]]:
    """Room type and axis-aligned box of every generated room.

    Parameters
    ----------
    plan_json : dict
        One JSONL record of the generator.
    scale : float
        Unit-to-metre factor.

    Returns
    -------
    list of (str, tuple of float)
        ``(type, (x, y, w, h))`` in metres, one entry per generated room.
    """
    out = []
    for room in plan_json["pieces"]:  # lang-ok: key of the vendor JSONL format
        corners = np.asarray(room["coins"], dtype=float) * scale  # lang-ok: vendor key
        x0, y0 = float(corners[:, 0].min()), float(corners[:, 1].min())
        x1, y1 = float(corners[:, 0].max()), float(corners[:, 1].max())
        out.append((str(room["type"]), (x0, y0, x1 - x0, y1 - y0)))
    return out


def generated_scale(rows: list[dict[str, Any]], *, target_area_m2: float = TARGET_AREA_M2) -> float:
    """Unit-to-metre factor matching the median generated area to ``target_area_m2``.

    Parameters
    ----------
    rows : list of dict
        JSONL records of the generator.
    target_area_m2 : float, optional
        Median area to match, in square metres.

    Returns
    -------
    float
        The factor applied to the generator's coordinates.
    """
    areas = []
    for plan_json in rows:
        shapes = [box(x, y, x + w, y + h) for _, (x, y, w, h) in generated_boxes(plan_json, 1.0)]
        union = unary_union(shapes)
        if not union.is_empty:
            areas.append(union.area)
    return float(np.sqrt(target_area_m2 / np.median(areas)))


def generated_plan(
    plan_json: dict[str, Any],
    scale: float,
    *,
    min_side: float = MIN_SIDE_M,
    min_width: float = DEFAULT_MIN_WIDTH,
) -> tuple[Plan, Context, Diagnostic] | str:
    """Plan, context and input diagnostic of one generated record, or why it is rejected.

    The target outline is the **bounding box** of the union of the rooms. The generator
    receives no envelope as a condition: it invents its own footprint. Imposing the
    tiling of this box therefore also squares the footprint; this is deliberate, and the
    reported displacement gives its cost.

    Parameters
    ----------
    plan_json : dict
        One JSONL record of the generator.
    scale : float
        Unit-to-metre factor, see :func:`generated_scale`.
    min_side : float, optional
        Side, in metres, below which a room is degenerate and the record rejected.
    min_width : float, optional
        Regulatory minimum width of the context, in metres.

    Returns
    -------
    tuple of (Plan, Context, Diagnostic) or str
        The plan, its context and its diagnostic; or the rejection reason in plain
        words (``"degenerate room"``, ``"empty union"``).
    """
    boxes = generated_boxes(plan_json, scale)
    if any(w < min_side or h < min_side for _, (_, _, w, h) in boxes):
        return "degenerate room"
    rooms = tuple(
        Room(id=f"p{rank:03d}", type=room_type, x=x, y=y, w=w, h=h)
        for rank, (room_type, (x, y, w, h)) in enumerate(boxes)
    )
    union = unary_union([box(p.x, p.y, p.x + p.w, p.y + p.h) for p in rooms])
    if union.is_empty:
        return "empty union"
    x0, y0, x1, y1 = union.bounds
    outline = ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
    plan = Plan(rooms=rooms, walls=(), openings=(), outline=outline)
    context = Context(
        structure=Structure(load_bearing_walls=(), columns=()),
        orientation=Orientation(deg=0.0),
        outline=outline,
        regulation=Regulation(min_areas=(), min_width=min_width),
        program=tuple(sorted(set(plan_json["programme"]))),  # lang-ok: vendor key
    )
    return plan, context, diagnose(plan)
