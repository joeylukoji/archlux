"""Naive local repair: the baseline that a global optimisation must beat.

Each room is moved on its own, in identifier order, to the first position of a fixed
grid where it lies inside the bounding box of the outline and overlaps none of the rooms
already placed. Sizes are never changed and no room looks at the others' needs. The
comparison with :func:`archlux.legalize` measures what the global linear programme brings
over a local, greedy correction; the result is checked by the same exact validator.
"""

from __future__ import annotations

import math
from dataclasses import replace

from archlux.tolerances import CONTACT_M as _TOLERANCE_M
from archlux.types import Plan, Room

__all__ = ["naive_repair"]


def _overlaps(room: Room, others: list[Room]) -> bool:
    """Whether ``room`` has a positive-area intersection with one of ``others``.

    Parameters
    ----------
    room : Room
        Room to test.
    others : list of Room
        Rooms already placed.

    Returns
    -------
    bool
        ``True`` if an intersection wider and taller than the tolerance exists.
    """
    for other in others:
        dx = min(room.x + room.w, other.x + other.w) - max(room.x, other.x)
        dy = min(room.y + room.h, other.y + other.h) - max(room.y, other.y)
        if dx > _TOLERANCE_M and dy > _TOLERANCE_M:
            return True
    return False


def _box(plan: Plan) -> tuple[float, float, float, float]:
    """Bounding box of the outline, or of the rooms when the plan has no outline.

    Parameters
    ----------
    plan : Plan
        Plan to bound.

    Returns
    -------
    tuple of float
        ``(x_low, y_low, x_high, y_high)`` in metres.
    """
    if plan.outline:
        xs = [p[0] for p in plan.outline]
        ys = [p[1] for p in plan.outline]
    else:
        xs = [v for r in plan.rooms for v in (r.x, r.x + r.w)]
        ys = [v for r in plan.rooms for v in (r.y, r.y + r.h)]
    return min(xs), min(ys), max(xs), max(ys)


def _candidates(current: float, low: float, high: float, size: float, step: float) -> list[float]:
    """Grid positions of one coordinate, nearest to ``current`` first.

    Parameters
    ----------
    current : float
        Current coordinate of the room.
    low, high : float
        Extent of the box along this axis.
    size : float
        Extent of the room along this axis.
    step : float
        Grid step.

    Returns
    -------
    list of float
        Every grid position ``low + k * step`` that keeps the room inside the box, sorted
        by distance to ``current``.
    """
    count = math.floor((high - size - low) / step + _TOLERANCE_M)
    grid = [low + k * step for k in range(count + 1)]
    return sorted(grid, key=lambda v: (abs(v - current), v))


def _inside(room: Room, box: tuple[float, float, float, float]) -> bool:
    """Whether ``room`` lies inside ``box``, up to the tolerance.

    Parameters
    ----------
    room : Room
        Room to test.
    box : tuple of float
        ``(x_low, y_low, x_high, y_high)``.

    Returns
    -------
    bool
        ``True`` if the room is inside the box.
    """
    x_low, y_low, x_high, y_high = box
    return (
        room.x >= x_low - _TOLERANCE_M
        and room.y >= y_low - _TOLERANCE_M
        and room.x + room.w <= x_high + _TOLERANCE_M
        and room.y + room.h <= y_high + _TOLERANCE_M
    )


def _first_free(
    room: Room, placed: list[Room], box: tuple[float, float, float, float], step: float
) -> Room:
    """The nearest free grid position of ``room`` (Chebyshev), or ``room`` if none is free.

    Parameters
    ----------
    room : Room
        Room to place.
    placed : list of Room
        Rooms already placed, which it must not overlap.
    box : tuple of float
        ``(x_low, y_low, x_high, y_high)`` it must stay in.
    step : float
        Grid step.

    Returns
    -------
    Room
        ``room`` itself when it is already free, else its nearest free copy.
    """
    if _inside(room, box) and not _overlaps(room, placed):
        return room
    x_low, y_low, x_high, y_high = box
    best, best_cost = room, float("inf")
    for x in _candidates(room.x, x_low, x_high, room.w, step):
        if abs(x - room.x) >= best_cost:
            break
        for y in _candidates(room.y, y_low, y_high, room.h, step):
            cost = max(abs(x - room.x), abs(y - room.y))
            if cost >= best_cost:
                break
            candidate = replace(room, x=round(x, 9), y=round(y, 9))
            if not _overlaps(candidate, placed):
                best, best_cost = candidate, cost
                break
    return best


def naive_repair(plan: Plan, *, step: float = 0.05) -> Plan:
    """Move each room independently to its nearest free position on a grid.

    Parameters
    ----------
    plan : Plan
        Plan to repair.
    step : float, optional
        Grid step in metres (default 0.05).

    Returns
    -------
    Plan
        The plan with every room that could be placed moved; a room with no free grid
        position stays where it was. Sizes, walls and openings are unchanged, and no
        certificate is attached: check the result with
        :func:`archlux.certify.verify_exactly`.

    Examples
    --------
    >>> from archlux.types import Plan, Room
    >>> a = Room(id="a", type="bedroom", x=0.0, y=0.0, w=2.0, h=2.0)
    >>> b = Room(id="b", type="bedroom", x=1.0, y=0.0, w=2.0, h=2.0)
    >>> out = naive_repair(Plan(rooms=(a, b), outline=((0, 0), (4, 0), (4, 2), (0, 2))))
    >>> [(r.id, r.x) for r in out.rooms]
    [('a', 0.0), ('b', 2.0)]
    """
    x_low, y_low, x_high, y_high = _box(plan)
    placed: list[Room] = []
    for room in sorted(plan.rooms, key=lambda r: r.id):
        moved = _first_free(room, placed, (x_low, y_low, x_high, y_high), step)
        placed.append(moved)
    order = {room.id: k for k, room in enumerate(plan.rooms)}
    rooms = tuple(sorted(placed, key=lambda r: order[r.id]))
    return replace(plan, rooms=rooms, certificate=None)
