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

from archlux.types import Contexte, Plan

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


def violations(plan: Plan, ctx: Contexte) -> list[Violation]:
    """Tiling, minimum areas and load-bearing walls, checked from coordinates only.

    Pairwise disjoint rooms whose areas add up to the outline area tile it exactly.
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

    for room in rooms:
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
