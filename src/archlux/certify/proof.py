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
:math:`w_p h_p \\ge a_{\\min}(\\mathrm{type}(p))` for every room. A fused room (L, T, U,
Z), decomposed into sub-rectangles :math:`R_k`, is checked as a whole:
:math:`\\lambda(\\bigcup_k R_k) \\ge a_{\\min}`, the union being a single polygon.

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

from fractions import Fraction

from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union

from archlux.geom.rectilineaire import PieceRectilineaire
from archlux.tolerances import AREA_PROOF_M2, GAP_M2, OVERLAP_M2, SNAP_M, WALL_M
from archlux.types import Contexte, Mur, Piece, Plan, PreuveGeometrique

__all__ = ["GAP_TOLERANCE_M2", "max_displacement", "rational_tiling", "verify_exactly"]

GAP_TOLERANCE_M2 = GAP_M2
"""Area tolerance of the uncovered-gap and overhang detection, in square metres."""

_WALL_TOLERANCE_M = WALL_M
_AREA_TOLERANCE_M2 = AREA_PROOF_M2
_OVERLAP_TOLERANCE_M2 = OVERLAP_M2


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

    The tolerance is ``OVERLAP_M2 = 1e-9 m²``: two rooms touching along an edge
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
            if area > _OVERLAP_TOLERANCE_M2:
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


def _share_an_edge(a: Piece, b: Piece) -> bool:
    """Edges within ``SNAP_M`` of each other, sharing more than ``SNAP_M`` of length."""

    def touch(a0: float, a1: float, b0: float, b1: float) -> bool:
        return abs(a1 - b0) <= SNAP_M or abs(b1 - a0) <= SNAP_M

    def overlap(a0: float, a1: float, b0: float, b1: float) -> bool:
        return min(a1, b1) - max(a0, b0) > SNAP_M

    ax, ay, bx, by = (a.x, a.x + a.w), (a.y, a.y + a.h), (b.x, b.x + b.w), (b.y, b.y + b.h)
    return (touch(*ax, *bx) and overlap(*ay, *by)) or (touch(*ay, *by) and overlap(*ax, *bx))


def _edge_connected(members: list[Piece]) -> bool:
    """Whether the sub-rectangles form one piece through shared edges (not corners)."""
    reached = {0}
    frontier = [0]
    while frontier:
        current = members[frontier.pop()]
        for k, other in enumerate(members):
            if k not in reached and _share_an_edge(current, other):
                reached.add(k)
                frontier.append(k)
    return len(reached) == len(members)


def _fused_area(room_id: str, members: list[Piece], ctx: Contexte) -> tuple[str, ...]:
    """Area of the recomposed polygon of a fused room against its minimum.

    The minimum applies to the room, not to each sub-rectangle. Sub-rectangles that do
    not form a single polygon (detached, or touching at a corner only) are not one
    room, and have no area to compare.
    """
    minimum = max(ctx.referentiel.a_min(member.type) for member in members)
    if not _edge_connected(members):
        return (f"area {room_id}: sub-rectangles do not form one polygon",)
    area = float(unary_union([_rectangle(member) for member in members]).area)
    if minimum > 0.0 and area + _AREA_TOLERANCE_M2 < minimum:
        return (f"area {room_id}: {_format_m2(area)} < {_format_m2(minimum)}",)
    return ()


def _areas(
    rooms: tuple[Piece, ...], ctx: Contexte, fusions: tuple[PieceRectilineaire, ...] = ()
) -> tuple[bool, tuple[str, ...]]:
    """Area ``w h`` against ``a_min`` of the room type; fused rooms as a whole."""
    by_id = {room.id: room for room in rooms}
    fused: set[str] = set()
    violations: list[str] = []
    for piece in fusions:
        members = [by_id[r.id] for r in piece.rectangles if r.id in by_id]
        fused.update(member.id for member in members)
        if members:
            violations.extend(_fused_area(piece.id, members, ctx))
    for room in rooms:
        if room.id in fused:
            continue
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


def _rectangular_outline(
    outline: tuple[tuple[float, float], ...],
) -> tuple[Fraction, Fraction, Fraction, Fraction] | None:
    """Exact bounds of an axis-aligned rectangular outline, ``None`` for any other shape.

    Every vertex lies on the bounding box and the polygon fills it: collinear vertices
    along an edge are accepted, an L-shaped outline is not.
    """
    polygon = _outline_polygon(outline)
    if polygon is None:
        return None
    x0, y0, x1, y1 = polygon.bounds
    on_box = all(x in (x0, x1) or y in (y0, y1) for x, y in outline)
    if not on_box or abs(polygon.area - (x1 - x0) * (y1 - y0)) > 1e-12 * polygon.area:
        return None
    return Fraction(x0), Fraction(y0), Fraction(x1), Fraction(y1)


def _identify(values: list[Fraction], tolerance: Fraction) -> dict[Fraction, Fraction]:
    """Map each value to the first value of its group; a group spans at most ``tolerance``.

    Two edges closer than the tolerance become the same line. Groups are anchored on
    their first value, so they never chain: every member is within the tolerance of the
    anchor.
    """
    mapping: dict[Fraction, Fraction] = {}
    anchor: Fraction | None = None
    for value in sorted(set(values)):
        if anchor is None or value - anchor > tolerance:
            anchor = value
        mapping[value] = anchor
    return mapping


def rational_tiling(plan: Plan, ctx: Contexte) -> tuple[str, ...] | None:
    """Prove, in exact rational arithmetic, that the rooms tile a rectangular outline.

    Edges closer than ``SNAP_M`` (1e-7 m) are identified: that is the only tolerance,
    on lengths, and it does not depend on the size of the rooms. Every coordinate is
    then an exact ``Fraction`` (a binary float is an exact rational), and the check is:

    1. every room lies inside the outline;
    2. the interiors of any two rooms are disjoint;
    3. the sum of the room areas equals the area of the outline.

    **Theorem.** 1 and 2 give ``λ(∪ R_i) = Σ λ(R_i) ≤ λ(C)``; with 3, the part of ``C``
    left uncovered has area ``λ(C) − Σ λ(R_i) = 0``: the rooms tile ``C`` up to a null
    set (no gap, no overlap).

    The identification moves edges by less than ``SNAP_M``, which can hide up to
    ``SNAP_M`` times a perimeter of area: 9e-6 m² along a 100 m edge. The theorem is
    about the identified rectangles, so the raw plan is then bounded as well, still in
    exact arithmetic (:func:`_raw_residuals`): every raw pairwise overlap is at most
    ``OVERLAP_M2``, and the raw overhang and an upper bound of the raw uncovered area
    are at most ``GAP_M2``, the tolerances of the GEOS path and of the test checker.

    Parameters
    ----------
    plan : Plan
        Plan to check.
    ctx : Contexte
        Provides the outline.

    Returns
    -------
    tuple of str or None
        Violation messages (empty: exact tiling), or ``None`` when the outline is not an
        axis-aligned rectangle, in which case :func:`verify_exactly` falls back on the
        GEOS area checks and their tolerances.
    """
    bounds = _rectangular_outline(ctx.contour)
    if bounds is None:
        return None
    ox0, oy0, ox1, oy1 = bounds
    raw = [
        (
            room.id,
            Fraction(room.x),
            Fraction(room.x) + Fraction(room.w),
            Fraction(room.y),
            Fraction(room.y) + Fraction(room.h),
        )
        for room in plan.pieces
    ]
    tolerance = Fraction(SNAP_M)
    same_x = _identify([ox0, ox1, *(v for r in raw for v in (r[1], r[2]))], tolerance)
    same_y = _identify([oy0, oy1, *(v for r in raw for v in (r[3], r[4]))], tolerance)
    ox0, ox1, oy0, oy1 = same_x[ox0], same_x[ox1], same_y[oy0], same_y[oy1]
    boxes = [(rid, same_x[a], same_x[b], same_y[c], same_y[d]) for rid, a, b, c, d in raw]

    violations: list[str] = []
    for rid, x0, x1, y0, y1 in boxes:
        if x1 <= x0 or y1 <= y0:
            violations.append(f"gap: room {rid} is thinner than the identification tolerance")
        elif x0 < ox0 or x1 > ox1 or y0 < oy0 or y1 > oy1:
            violations.append(f"gap: room {rid} lies partly outside the outline")
    for i, (a, ax0, ax1, ay0, ay1) in enumerate(boxes):
        for b, bx0, bx1, by0, by1 in boxes[i + 1 :]:
            dx, dy = min(ax1, bx1) - max(ax0, bx0), min(ay1, by1) - max(ay0, by0)
            if dx > 0 and dy > 0:
                pair = "|".join(sorted((a, b)))
                violations.append(f"overlap {pair}: {float(dx * dy):.6g} m² (exact)")
    if not violations:
        covered = sum(((x1 - x0) * (y1 - y0) for _, x0, x1, y0, y1 in boxes), Fraction(0))
        outline_area = (ox1 - ox0) * (oy1 - oy0)
        if covered != outline_area:
            missing = float(outline_area - covered)
            violations.append(f"gap: uncovered area {missing:.6g} m² (exact)")
    if not violations:
        violations.extend(_raw_residuals(raw, bounds))
    return tuple(violations)


_Box = tuple[str, Fraction, Fraction, Fraction, Fraction]


def _intersection(
    a: tuple[Fraction, Fraction, Fraction, Fraction],
    b: tuple[Fraction, Fraction, Fraction, Fraction],
) -> tuple[Fraction, Fraction, Fraction, Fraction] | None:
    """Exact intersection of two boxes ``(x0, x1, y0, y1)``, ``None`` if its area is null."""
    x0, x1 = max(a[0], b[0]), min(a[1], b[1])
    y0, y1 = max(a[2], b[2]), min(a[3], b[3])
    if x1 <= x0 or y1 <= y0:
        return None
    return x0, x1, y0, y1


def _area(box_: tuple[Fraction, Fraction, Fraction, Fraction] | None) -> Fraction:
    if box_ is None:
        return Fraction(0)
    return (box_[1] - box_[0]) * (box_[3] - box_[2])


def _raw_residuals(
    raw: list[_Box], bounds: tuple[Fraction, Fraction, Fraction, Fraction]
) -> list[str]:
    """Bound, on the raw coordinates, what the identification may have erased.

    With ``C`` the outline and ``R_i`` the raw rooms, Bonferroni's inequality
    ``λ(∪ R_i ∩ C) ≥ Σ λ(R_i ∩ C) − Σ_{i<j} λ(R_i ∩ R_j ∩ C)`` bounds the uncovered area
    from above by ``λ(C) − Σ λ(R_i ∩ C) + Σ_{i<j} λ(R_i ∩ R_j ∩ C)``; the overhang, by
    ``Σ (λ(R_i) − λ(R_i ∩ C))``, the area of the rooms outside the outline.
    """
    ox0, oy0, ox1, oy1 = bounds
    outline = (ox0, ox1, oy0, oy1)
    violations: list[str] = []
    inside = [(rid, _intersection((x0, x1, y0, y1), outline)) for rid, x0, x1, y0, y1 in raw]
    overlaps = Fraction(0)
    for i, (a, ax0, ax1, ay0, ay1) in enumerate(raw):
        for b, bx0, bx1, by0, by1 in raw[i + 1 :]:
            common = _area(_intersection((ax0, ax1, ay0, ay1), (bx0, bx1, by0, by1)))
            if common > _OVERLAP_TOLERANCE_M2:
                pair = "|".join(sorted((a, b)))
                violations.append(f"overlap {pair}: {float(common):.6g} m² (exact, raw)")
            overlaps += common
    overhang = sum(
        (
            _area((x0, x1, y0, y1)) - _area(part)
            for (_, x0, x1, y0, y1), (_, part) in zip(raw, inside, strict=True)
        ),
        Fraction(0),
    )
    if overhang > GAP_TOLERANCE_M2:
        violations.append(
            f"gap: overhang outside the outline {float(overhang):.6g} m² (exact, raw)"
        )
    uncovered = _area(outline) - sum((_area(part) for _, part in inside), Fraction(0)) + overlaps
    if uncovered > GAP_TOLERANCE_M2:
        violations.append(f"gap: uncovered area at most {float(uncovered):.6g} m² (exact, raw)")
    return violations


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
    plan: Plan,
    ctx: Contexte,
    *,
    reference: Plan | None = None,
    budget: float | None = None,
    fusions: tuple[PieceRectilineaire, ...] = (),
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
    fusions : tuple of PieceRectilineaire, optional
        Rooms decomposed into sub-rectangles (L, T, U, Z), as passed to
        :func:`archlux.api.legalize`. The minimum area of such a room applies to the
        union of its sub-rectangles found in ``plan`` (by id), which must form a single
        polygon; no sub-rectangle is checked on its own.

    Returns
    -------
    PreuveGeometrique
        The predicates and their violation messages.

    Guarantees
    ----------
    - Geometric, rectangular outline: tiling proved in **exact rational arithmetic**
      (:func:`rational_tiling`), the only tolerance being the identification of edges
      closer than ``SNAP_M`` (1e-7 m). Other outlines: GEOS areas, tolerances
      ``_AREA_TOLERANCE_M2`` and ``GAP_TOLERANCE_M2``. ``valide`` is the conjunction.
    - Performance: **none**.

    Notes
    -----
    Formulas: ``docs/formules/preuve-exacte.md``.
    """
    rational = rational_tiling(plan, ctx)
    if rational is None:  # not a rectangular outline: GEOS areas and their tolerances
        overlap, v_overlap = _overlaps(plan.pieces)
        gaps, v_gaps = _gaps(plan.pieces, ctx.contour)
    else:
        v_overlap = tuple(v for v in rational if v.startswith("overlap"))
        v_gaps = tuple(v for v in rational if v.startswith("gap"))
        overlap, gaps = bool(v_overlap), bool(v_gaps)
        if overlap:
            # With overlapping rooms the sum of areas no longer measures coverage, so the
            # rational check cannot see a gap: take the gap diagnosis from GEOS. The plan
            # is invalid either way; this keeps the report complete.
            geos_flag, geos_gaps = _gaps(plan.pieces, ctx.contour)
            gaps = gaps or geos_flag
            v_gaps = v_gaps + tuple(v for v in geos_gaps if v not in v_gaps)
    areas_ok, v_areas = _areas(plan.pieces, ctx, fusions)
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
