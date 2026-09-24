r"""Exact verification, **independent of the solver**.

Formula
=======
Boolean predicates, whose conjunction is ``valide``. None of them is probabilistic.

Overlap
-------
For two rectangles :math:`R_i, R_j`, the intersection area :math:`|R_i \\cap R_j|`
(GEOS / Shapely; :math:`O(n^2)` pairs, accepted). Overlap iff
:math:`|R_i \\cap R_j| > 0` beyond the numerical tolerance.

Gaps
----
Let :math:`U = \\bigcup_i R_i` and :math:`C` the outline polygon. An exact tiling
satisfies :math:`U = C` up to a null measure, tested through **both** set differences:

.. math::

    \\lambda(C \\setminus U) > \\tau \\quad\\text{(uncovered gap)}, \\qquad
    \\lambda(U \\setminus C) > \\tau \\quad\\text{(overhang)}, \\qquad
    \\tau = 10^{-6}\\,\\mathrm{m}^2.

Equal areas :math:`|\\lambda(U) - \\lambda(C)| \\le \\tau` are **not enough**: a gap of
:math:`a` m² compensated by an overhang of :math:`a` m² would pass. The set differences
refuse it. Together with :math:`\\lambda(R_i \\cap R_j)=0` for :math:`i \\ne j`, the
conjunction characterizes a tiling of :math:`C`.

Areas
-----
:math:`w_p h_p \\ge a_{\\min}(\\mathrm{type}(p))` for every room.

Structure
---------
No room interior contains a stretch of a load-bearing wall of :math:`\\mathrm{ctx}`
(rooms shrunk by a metric tolerance, so that a room bounded by the wall is accepted;
oblique walls included). A wall the plan declares with the same ``id`` must match the
structure. Columns (``Structure.poteaux``) are fixed data and are not checked.

Displacement
------------
:math:`\\delta_\\infty = \\max_p \\max\\bigl(|\\Delta x|,|\\Delta y|,|\\Delta w|,|\\Delta h|\\bigr)`
in metres, relative to the reference plan; checked against an optional budget.

Derivation, tolerances and use cases: ``docs/formules/preuve-exacte.md``.
"""

from __future__ import annotations

from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union

from archlux.tolerances import SNAP_M, WALL_M
from archlux.types import Contexte, Mur, Piece, Plan, PreuveGeometrique

__all__ = ["GAP_TOLERANCE_M2", "verify_exactly"]

GAP_TOLERANCE_M2 = 1e-6
"""Area tolerance of the uncovered-gap and overhang detection, in square metres."""

_WALL_TOLERANCE_M = WALL_M
_AREA_TOLERANCE_M2 = 1e-9


def _format_m2(value: float) -> str:
    """An area with four decimals: two rounded equal numbers once hid a real deficit."""
    return f"{value:.4f} m²"


def _rectangle(room: Piece) -> Polygon:
    """Closed rectangle of the room: lower-left corner plus (w, h)."""
    return box(room.x, room.y, room.x + room.w, room.y + room.h)


def _outline_polygon(outline: tuple[tuple[float, float], ...]) -> Polygon | None:
    """Polygon of the outline, or ``None`` if it is degenerate."""
    if len(outline) < 3:
        return None
    polygon = Polygon(outline)
    if not polygon.is_valid or polygon.area <= 0.0:
        return None
    return polygon


def _disjoint(a: Piece, b: Piece) -> bool:
    """Exact rejection of two axis-aligned rectangles, without GEOS.

    Rooms are boxes: if their intervals separate on ``x`` or on ``y``, the intersection
    area is **exactly** zero. This purely arithmetic test skips the shapely call for the
    vast majority of pairs, which keeps the certification budget of §9 without changing
    any result.
    """
    return a.x + a.w <= b.x or b.x + b.w <= a.x or a.y + a.h <= b.y or b.y + b.h <= a.y


def _overlaps(rooms: tuple[Piece, ...]) -> tuple[bool, tuple[str, ...]]:
    """Every pair, intersection area.

    The tolerance is ``_AREA_TOLERANCE_M2 = 1e-9 m²``: two rooms touching along an edge
    have a null intersection and are not reported, while a 1 m by 1 nm sliver just is.
    It differs from :data:`GAP_TOLERANCE_M2`, a thousand times looser, because a gap is
    measured over the whole union, not over one pair.
    """
    violations: list[str] = []
    rectangles = [_rectangle(room) for room in rooms]
    for i, a in enumerate(rooms):
        for offset, b in enumerate(rooms[i + 1 :], start=i + 1):
            if _disjoint(a, b):
                continue
            area = rectangles[i].intersection(rectangles[offset]).area
            if area > _AREA_TOLERANCE_M2:
                pair = "|".join(sorted((a.id, b.id)))
                violations.append(f"overlap {pair}: {_format_m2(area)}")
    return (bool(violations), tuple(violations))


def _gaps(
    rooms: tuple[Piece, ...], outline: tuple[tuple[float, float], ...]
) -> tuple[bool, tuple[str, ...]]:
    """Set differences between union and outline: uncovered gap **and** overhang.

    Comparing areas only would accept a gap compensated by a room outside the outline;
    both set differences are therefore tested separately.
    """
    envelope = _outline_polygon(outline)
    if envelope is None:
        return True, ("degenerate outline: no tiling can be defined",)
    if not rooms:
        return True, ("no room",)
    union = unary_union([_rectangle(room) for room in rooms])
    uncovered = float(envelope.difference(union).area)
    overhang = float(union.difference(envelope).area)
    violations: list[str] = []
    if uncovered > GAP_TOLERANCE_M2:
        violations.append(f"gap: uncovered area {_format_m2(uncovered)}")
    if overhang > GAP_TOLERANCE_M2:
        violations.append(f"gap: overhang outside the outline {_format_m2(overhang)}")
    return (bool(violations), tuple(violations))


def _areas(rooms: tuple[Piece, ...], ctx: Contexte) -> tuple[bool, tuple[str, ...]]:
    """Area ``w h`` against ``a_min`` of the room type."""
    violations: list[str] = []
    for room in rooms:
        minimum = ctx.referentiel.a_min(room.type)
        if minimum <= 0.0:
            continue
        if room.aire + _AREA_TOLERANCE_M2 < minimum:
            violations.append(f"area {room.id}: {_format_m2(room.aire)} < {_format_m2(minimum)}")
    return (not violations, tuple(violations))


def _same_wall(a: Mur, b: Mur) -> bool:
    """Same geometry up to tolerance, end points possibly swapped."""

    def close(p: tuple[float, float], q: tuple[float, float]) -> bool:
        return abs(p[0] - q[0]) <= _WALL_TOLERANCE_M and abs(p[1] - q[1]) <= _WALL_TOLERANCE_M

    return (close(a.a, b.a) and close(a.b, b.b)) or (close(a.a, b.b) and close(a.b, b.a))


def _structure(plan: Plan, ctx: Contexte) -> tuple[bool, tuple[str, ...]]:
    """No room crosses a load-bearing wall, and no load-bearing wall was moved.

    A crossing is any stretch of the wall inside a room's interior, the room being shrunk
    by ``_WALL_TOLERANCE_M`` so that a room merely bounded by the wall is accepted. The
    test is geometric (shapely), so it holds for oblique walls too.

    A plan does not have to repeat the structure in ``plan.murs``: load-bearing walls
    belong to the context. If it does declare a wall of the same id, that wall must
    match the structure, otherwise it was moved.
    """
    declared = {wall.id: wall for wall in plan.murs}
    violations: list[str] = []
    tol = _WALL_TOLERANCE_M
    for wall in ctx.structure.murs_porteurs:
        stated = declared.get(wall.id)
        if stated is not None and not _same_wall(wall, stated):
            violations.append(f"structure: load-bearing wall {wall.id} moved")
        line = LineString([wall.a, wall.b])
        for room in plan.pieces:
            if room.w <= 2 * tol or room.h <= 2 * tol:
                continue  # a degenerate room has no interior to cross
            interior = box(room.x + tol, room.y + tol, room.x + room.w - tol, room.y + room.h - tol)
            if line.intersection(interior).length > tol:
                violations.append(f"structure: room {room.id} crosses load-bearing wall {wall.id}")
    return (not violations, tuple(violations))


def max_displacement(plan: Plan, reference: Plan | None) -> float:
    """L-infinity over (x, y, w, h) of the rooms sharing an identifier; 0 without reference."""
    if reference is None:
        return 0.0
    by_id = {room.id: room for room in reference.pieces}
    delta = 0.0
    for room in plan.pieces:
        origin = by_id.get(room.id)
        if origin is None:
            continue
        delta = max(
            delta,
            abs(room.x - origin.x),
            abs(room.y - origin.y),
            abs(room.w - origin.w),
            abs(room.h - origin.h),
        )
    return delta


def verify_exactly(
    plan: Plan, ctx: Contexte, *, reference: Plan | None = None, budget: float | None = None
) -> PreuveGeometrique:
    """Check that a plan is valid, borrowing nothing from the solver.

    Parameters
    ----------
    plan : Plan
        Plan to check.
    ctx : Contexte
        Outline, load-bearing structure and regulation.
    reference : Plan or None, optional
        Proposed plan, for ``deplacement_max``. ``None`` gives ``0.0``.
    budget : float or None, optional
        Maximum displacement allowed from ``reference``, in metres. When given, a
        larger ``deplacement_max`` (beyond ``SNAP_M``) makes the plan invalid. Without
        ``reference`` the displacement is 0 and the budget cannot be violated.

    Returns
    -------
    PreuveGeometrique
        The predicates and their violation messages.

    Guarantees
    ----------
    - Geometric: **exact** up to the stated tolerances, finite inspection; ``valide``
      is the conjunction.
    - Performance: **none**.

    Notes
    -----
    Formulas: ``docs/formules/preuve-exacte.md``.
    """
    overlap, v_overlap = _overlaps(plan.pieces)
    gaps, v_gaps = _gaps(plan.pieces, ctx.contour)
    areas_ok, v_areas = _areas(plan.pieces, ctx)
    structure_ok, v_structure = _structure(plan, ctx)
    moved = max_displacement(plan, reference)
    budget_ok = budget is None or moved <= budget + SNAP_M
    v_budget = () if budget_ok else (f"budget: max displacement {moved:.6f} m > {budget} m",)
    violations = v_overlap + v_gaps + v_areas + v_structure + v_budget
    valid = (not overlap) and (not gaps) and areas_ok and structure_ok and budget_ok
    return PreuveGeometrique(
        valide=valid,
        chevauchement=overlap,
        jours=gaps,
        surfaces_ok=areas_ok,
        structure_preservee=structure_ok,
        deplacement_max=moved,
        violations=violations,
    )
