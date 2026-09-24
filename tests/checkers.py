"""Independent checker of the exact guarantees, shared by tests and benchmarks.

It recomputes every guarantee from room coordinates only and never calls ``certify``:
re-checking the proof with itself is precisely the blind spot that let a tautological
load-bearing check through (AUDIT.md §3 n°1).

Scope: rectangular rooms inside the axis-aligned rectangle spanned by the outline, and
axis-aligned load-bearing walls. Anything else is refused loudly, never misread.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from archlux.geom.rectilineaire import FUSION_DROIT, PieceRectilineaire
from archlux.types import Contexte, Piece, Plan

TOLERANCE = 1e-6
"""Metres or square metres: well above float noise, well below any meaningful defect."""

Kind = Literal["overlap", "coverage", "area", "wall", "budget"]
KINDS: tuple[Kind, ...] = ("overlap", "coverage", "area", "wall", "budget")


@dataclass(frozen=True, slots=True)
class Violation:
    """One broken guarantee: its kind and a human-readable detail."""

    kind: Kind
    detail: str


def outline_area(ctx: Contexte) -> float:
    """Area of the axis-aligned rectangle spanned by the outline."""
    xs = [x for x, _ in ctx.contour]
    ys = [y for _, y in ctx.contour]
    return (max(xs) - min(xs)) * (max(ys) - min(ys))


def _fusion_holds(a: Piece, b: Piece, kind: str) -> bool:
    """``b`` continues ``a`` across the recorded edge, sharing a positive length of it."""
    if kind == FUSION_DROIT:
        edge, span = abs(a.x + a.w - b.x), min(a.y + a.h, b.y + b.h) - max(a.y, b.y)
    else:
        edge, span = abs(a.y + a.h - b.y), min(a.x + a.w, b.x + b.w) - max(a.x, b.x)
    return edge <= TOLERANCE and span > TOLERANCE


def _fused_area_violations(
    rooms: tuple[Piece, ...], ctx: Contexte, fusions: tuple[PieceRectilineaire, ...]
) -> tuple[set[str], list[Violation]]:
    """Fused rooms measured as a whole: every recorded edge holds, the sum meets the minimum.

    Returns the ids of the sub-rectangles found, which escape the per-room check.
    """
    by_id = {room.id: room for room in rooms}
    members: set[str] = set()
    found: list[Violation] = []
    for piece in fusions:
        parts = [by_id[r.id] for r in piece.rectangles if r.id in by_id]
        if not parts:
            continue
        members.update(part.id for part in parts)
        for i, j, kind in piece.fusions:
            a, b = by_id.get(piece.rectangles[i].id), by_id.get(piece.rectangles[j].id)
            if a is not None and b is not None and not _fusion_holds(a, b, kind):
                found.append(Violation("area", f"{piece.id}: {a.id} and {b.id} are apart"))
        minimum = max(ctx.referentiel.a_min(part.type) for part in parts)
        area = sum(part.w * part.h for part in parts)
        if area < minimum - TOLERANCE:
            found.append(Violation("area", f"{piece.id}: area {area:.6f} < {minimum:.6f}"))
    return members, found


def violations(
    plan: Plan, ctx: Contexte, *, fusions: tuple[PieceRectilineaire, ...] = ()
) -> list[Violation]:
    """Tiling, minimum areas and load-bearing walls, checked from coordinates only.

    Pairwise disjoint rooms whose areas add up to the outline area tile it exactly. A
    fused room (``fusions``) is measured as a whole: its sub-rectangles must keep every
    recorded shared edge, and their areas add up to the room's.
    """
    found: list[Violation] = []
    rooms = plan.pieces

    for i, a in enumerate(rooms):
        for b in rooms[i + 1 :]:
            dx = min(a.x + a.w, b.x + b.w) - max(a.x, b.x)
            dy = min(a.y + a.h, b.y + b.h) - max(a.y, b.y)
            if dx > TOLERANCE and dy > TOLERANCE:
                found.append(Violation("overlap", f"{a.id} overlaps {b.id}"))

    total, target = sum(room.w * room.h for room in rooms), outline_area(ctx)
    if abs(total - target) > TOLERANCE:
        found.append(
            Violation("coverage", f"rooms cover {total:.6f} m² of a {target:.6f} m² outline")
        )

    fused, fused_found = _fused_area_violations(rooms, ctx, fusions)
    found.extend(fused_found)
    for room in rooms:
        if room.id in fused:
            continue
        minimum = ctx.referentiel.a_min(room.type)
        if room.w * room.h < minimum - TOLERANCE:
            found.append(
                Violation("area", f"{room.id}: area {room.w * room.h:.6f} < {minimum:.6f}")
            )

    for wall in ctx.structure.murs_porteurs:
        (xa, ya), (xb, yb) = wall.a, wall.b
        vertical, horizontal = abs(xa - xb) < TOLERANCE, abs(ya - yb) < TOLERANCE
        if not (vertical or horizontal):
            raise ValueError(f"checker only handles axis-aligned walls: {wall}")
        for room in rooms:
            x0, x1, y0, y1 = room.x, room.x + room.w, room.y, room.y + room.h
            if vertical:
                crosses = x0 + TOLERANCE < xa < x1 - TOLERANCE
                overlap = min(y1, max(ya, yb)) - max(y0, min(ya, yb))
            else:
                crosses = y0 + TOLERANCE < ya < y1 - TOLERANCE
                overlap = min(x1, max(xa, xb)) - max(x0, min(xa, xb))
            if crosses and overlap > TOLERANCE:
                found.append(Violation("wall", f"{room.id} crosses load-bearing wall {wall.id}"))
    return found


def budget_violations(plan: Plan, proposed: Plan, budget: float) -> list[Violation]:
    """Rooms moved farther than ``budget`` (L-infinity over x, y, w, h) from ``proposed``."""
    before = {room.id: room for room in proposed.pieces}
    found: list[Violation] = []
    for room in plan.pieces:
        origin = before.get(room.id)
        if origin is None:
            continue
        moved = max(
            abs(room.x - origin.x),
            abs(room.y - origin.y),
            abs(room.w - origin.w),
            abs(room.h - origin.h),
        )
        if moved > budget + TOLERANCE:
            found.append(Violation("budget", f"{room.id} moved {moved:.6f} m > {budget} m"))
    return found
