"""Quantify **how** a plan is invalid, not merely whether it is.

Why this module exists
----------------------
:func:`~archlux.certify.proof.verify_exactly` returns a verdict and names the
violations. That is what certification needs; it is not what **characterising a
corpus of inputs** needs. "Invalid" does not tell a plan whose partition wall
slipped by two centimetres from a plan whose rooms float as an archipelago — yet
these two regimes call for different corrections, and the second is not repairable
at the same cost.

The five measures returned here are the ones that decide whether
:func:`~archlux.api.legalize` stands a chance:

- ``overlaps`` — how many rooms each room overlaps, on average. This is the
  quantity the MSD authors report for their own baseline (4.11 ± 2.25), hence
  the only one directly comparable to the literature.
- ``gap_share`` — share of the bounding box that the union does not cover.
- ``hole_share`` — share taken up by holes **interior** to the union. Separating
  the two is essential: an edge gap may merely be a non-rectangular footprint,
  whereas an interior hole is an unambiguous defect.
- ``fragments`` — number of connected components. Beyond 1, the "apartment" is an
  archipelago, and no grid will fix it on a reasonable budget. Two rooms that
  touch **only at a corner** count as two fragments: a shared corner is neither a
  party wall nor a passage, and for tiling it remains a gap.
- ``cells`` — size of the implicit grid, ``(|X| - 1) × (|Y| - 1)`` over the lines
  carried by the edges. In a real plan rooms share their walls and this number
  stays small; if it explodes, the combinatorial structure of the tiling **does
  not exist** — see :mod:`archlux.geom.tiling`.

None of these quantities is a guarantee: this module describes, it proves nothing.
The proof stays in ``certify``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from shapely.geometry import MultiPolygon, Polygon, box
from shapely.ops import unary_union

from archlux._deprecation import Alias, lazy_aliases
from archlux.errors import InvalidInput

if TYPE_CHECKING:
    from archlux.types import Plan

__all__ = ["Diagnostic", "diagnose"]

_MIN_AREA = 1e-6


@dataclass(frozen=True, slots=True)
class Diagnostic:
    """Numeric portrait of a proposed plan. None of these values is a proof.

    Attributes
    ----------
    overlaps : float
        Mean number of rooms overlapped by a room. ``0.0`` if no pair overlaps.
    gap_share : float
        Share of the bounding box that is not covered, in ``[0, 1]``.
    hole_share : float
        Share taken up by holes **interior** to the union, in ``[0, 1]``.
        Always ``<= gap_share``.
    fragments : int
        Connected components of the union. ``1`` for a single-piece plan.
    cells : int
        Cardinality of the implicit grid carried by the room edges.
    size : float
        Characteristic side, ``sqrt(bounding-box area)``, in metres. A displacement
        in metres cannot be read without it.
    """

    overlaps: float
    gap_share: float
    hole_share: float
    fragments: int
    cells: int
    size: float


def diagnose(plan: Plan) -> Diagnostic:
    """Measure the five pathologies of a proposed plan.

    Parameters
    ----------
    plan : Plan
        Plan to describe. It may be invalid — that is the use case.

    Returns
    -------
    Diagnostic
        The numeric portrait. See :class:`Diagnostic` for each field.

    Raises
    ------
    ValueError
        The plan carries no room: there is nothing to describe, and returning
        zeros would suggest a sound plan.

    Notes
    -----
    The outline of ``ctx`` is **not** consulted: the measures bear on the bounding
    box of the union, so that they stay comparable between plans whose outlines are
    fixed differently.

    Complexity
    ----------
    O(n²) in the number of rooms, for the overlap count. n is around ten in
    practice.

    Examples
    --------
    Two adjoining rooms exactly tiling their bounding box:

    >>> from archlux.types import Plan, Room
    >>> plan = Plan(
    ...     rooms=(
    ...         Room(id="a", type="salon", x=0.0, y=0.0, w=3.0, h=2.0),
    ...         Room(id="b", type="kitchen", x=3.0, y=0.0, w=2.0, h=2.0),
    ...     ),
    ...     walls=(), openings=(), outline=(),
    ... )
    >>> diag = diagnose(plan)
    >>> diag.overlaps, diag.gap_share, diag.fragments, diag.cells
    (0.0, 0.0, 1, 2)

    Moving the second room away opens a gap and cuts the plan in two:

    >>> troue = Plan(
    ...     rooms=(plan.rooms[0], Room(
    ...         id="b", type="kitchen", x=4.0, y=0.0, w=2.0, h=2.0)),
    ...     walls=(), openings=(), outline=(),
    ... )
    >>> diag = diagnose(troue)
    >>> round(diag.gap_share, 3), diag.fragments
    (0.167, 2)
    """
    if not plan.rooms:
        raise InvalidInput("rooms", "the plan has no room: nothing to diagnose")

    shapes = [box(p.x, p.y, p.x + p.w, p.y + p.h) for p in plan.rooms]
    n = len(shapes)
    overlap_area = (
        sum(
            1
            for i in range(n)
            for j in range(n)
            if i != j and shapes[i].intersection(shapes[j]).area > _MIN_AREA
        )
        / n
    )

    union = unary_union(shapes)
    x0, y0, x1, y1 = union.bounds
    box_area = (x1 - x0) * (y1 - y0)
    parts = list(union.geoms) if isinstance(union, MultiPolygon) else [union]
    hole_area = sum(Polygon(ring).area for shape in parts for ring in shape.interiors)

    lines_x = {p.x for p in plan.rooms} | {p.x + p.w for p in plan.rooms}
    lines_y = {p.y for p in plan.rooms} | {p.y + p.h for p in plan.rooms}

    return Diagnostic(
        overlaps=float(overlap_area),
        gap_share=float(1.0 - union.area / box_area) if box_area > 0 else 0.0,
        hole_share=float(hole_area / box_area) if box_area > 0 else 0.0,
        fragments=len(parts),
        cells=(len(lines_x) - 1) * (len(lines_y) - 1),
        size=math.sqrt(box_area),
    )


__getattr__ = lazy_aliases(
    __name__,
    {
        "diagnostiquer": Alias(diagnose, "archlux.geom.diagnostic.diagnose"),
    },
)
