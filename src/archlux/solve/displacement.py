"""How far a legalized plan moved from the proposed one: walls, areas, openings.

A displacement budget bounds one number, ``max |x - x_proposed|`` over the decision
variables. That number says nothing about which walls moved, how much a room grew or
shrank, or where a window went. This module measures the three separately, room by
room, and summarizes a population of them (mean, median, spread, histogram), so that a
gain of the surrogate is always read next to the change it cost.

What it does **not** measure: whether the architectural intent survived (circulation,
furnishability, views). Meeting a budget is not preserving a design.

Formulas: ``docs/formulas/frank-wolfe.md``, section "Displacement".
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from archlux.errors import InvalidInput
from archlux.tolerances import FW_FEASIBILITY_M

if TYPE_CHECKING:
    from collections.abc import Iterable

    from archlux.types import Opening, Plan, Room, Wall

__all__ = [
    "Displacement",
    "Distribution",
    "RoomShift",
    "count_saturated",
    "measure_displacement",
    "summarize",
]


@dataclass(frozen=True, slots=True)
class RoomShift:
    """How one room changed.

    Attributes
    ----------
    room_id : str
        Identifier of the room.
    wall_shift : float
        Largest shift of its four sides (left ``x``, right ``x + w``, bottom ``y``, top
        ``y + h``), in metres.
    area_change : float
        Signed area change, in m² (after minus before).
    relative_area_change : float
        ``area_change`` over the proposed area (``0`` for a room of zero area).
    """

    room_id: str
    wall_shift: float
    area_change: float
    relative_area_change: float


@dataclass(frozen=True, slots=True)
class Displacement:
    """Room-by-room and opening-by-opening change between two plans.

    Attributes
    ----------
    rooms : tuple of RoomShift
        One entry per room, in the order of the proposed plan.
    openings : tuple of (str, float)
        Shift of the centre of each opening, in metres, derived from its wall in each
        plan (openings are stored relative to their wall, `ARCHITECTURE.md` §6).
    """

    rooms: tuple[RoomShift, ...]
    openings: tuple[tuple[str, float], ...] = ()

    @property
    def max_wall_shift(self) -> float:
        """Largest side shift over all rooms, in metres.

        Returns
        -------
        float
            ``0`` for a plan without rooms.
        """
        return max((room.wall_shift for room in self.rooms), default=0.0)

    @property
    def max_area_change(self) -> float:
        """Largest absolute area change, in m².

        Returns
        -------
        float
            ``max |area_change|``.
        """
        return max((abs(room.area_change) for room in self.rooms), default=0.0)

    @property
    def max_relative_area_change(self) -> float:
        """Largest absolute relative area change (dimensionless).

        Returns
        -------
        float
            ``max |relative_area_change|``.
        """
        return max((abs(room.relative_area_change) for room in self.rooms), default=0.0)

    @property
    def max_opening_shift(self) -> float:
        """Largest opening shift, in metres.

        Returns
        -------
        float
            ``0`` without openings.
        """
        return max((shift for _, shift in self.openings), default=0.0)

    def combined(self, *, wall: float = 1.0, area: float = 1.0, opening: float = 1.0) -> float:
        """One cost from the three terms, with explicit weights.

        ``wall * max_wall_shift + area * max_relative_area_change + opening *
        max_opening_shift``. The weights carry units (per metre, dimensionless, per
        metre): there is no canonical choice, so the caller states it.

        Parameters
        ----------
        wall
            Weight of the largest side shift.
        area
            Weight of the largest relative area change.
        opening
            Weight of the largest opening shift.

        Returns
        -------
        float
            The weighted sum.
        """
        return (
            wall * self.max_wall_shift
            + area * self.max_relative_area_change
            + opening * self.max_opening_shift
        )


def _room_shift(before: Room, after: Room) -> RoomShift:
    """Side shifts and area change of one room.

    Parameters
    ----------
    before
        Proposed room.
    after
        Legalized room.

    Returns
    -------
    RoomShift
        The change of the room.
    """
    sides = (
        abs(after.x - before.x),
        abs((after.x + after.w) - (before.x + before.w)),
        abs(after.y - before.y),
        abs((after.y + after.h) - (before.y + before.h)),
    )
    change = after.area - before.area
    relative = change / before.area if before.area > 0.0 else 0.0
    return RoomShift(
        room_id=before.id,
        wall_shift=max(sides),
        area_change=change,
        relative_area_change=relative,
    )


def _opening_centre(opening: Opening, walls: dict[str, Wall], label: str) -> tuple[float, float]:
    """Absolute centre of an opening on its wall.

    Parameters
    ----------
    opening
        The opening.
    walls
        Walls of its plan, by id.
    label
        ``"proposed"`` or ``"corrected"``, for the error message.

    Returns
    -------
    tuple of float
        The centre, in metres.

    Raises
    ------
    InvalidInput
        The wall of the opening is not in the plan.
    """
    wall = walls.get(opening.wall_id)
    if wall is None:
        raise InvalidInput(f"{label}.openings[{opening.id}]", f"wall {opening.wall_id!r} not found")
    (ax, ay), (bx, by) = opening.absolute_segment(wall)
    return (ax + bx) / 2.0, (ay + by) / 2.0


def _opening_shifts(proposed: Plan, corrected: Plan) -> tuple[tuple[str, float], ...]:
    """Centre shift of every opening present in both plans.

    Parameters
    ----------
    proposed
        Proposed plan.
    corrected
        Legalized plan.

    Returns
    -------
    tuple of (str, float)
        Shift of each opening, in the order of the proposed plan.

    Raises
    ------
    InvalidInput
        An opening of the proposed plan is missing from the corrected one.
    """
    walls_before = {wall.id: wall for wall in proposed.walls}
    walls_after = {wall.id: wall for wall in corrected.walls}
    after = {opening.id: opening for opening in corrected.openings}
    shifts: list[tuple[str, float]] = []
    for opening in proposed.openings:
        if opening.id not in after:
            raise InvalidInput(f"corrected.openings[{opening.id}]", "missing")
        start = _opening_centre(opening, walls_before, "proposed")
        end = _opening_centre(after[opening.id], walls_after, "corrected")
        shifts.append((opening.id, math.dist(start, end)))
    return tuple(shifts)


def measure_displacement(proposed: Plan, corrected: Plan) -> Displacement:
    """Measure how far ``corrected`` moved from ``proposed``, room by room.

    Parameters
    ----------
    proposed : Plan
        The plan given to :func:`archlux.legalize`.
    corrected : Plan
        The plan it returned (same room and opening identifiers).

    Returns
    -------
    Displacement
        Side shifts, area changes and opening shifts.

    Raises
    ------
    InvalidInput
        The two plans do not have the same room identifiers, or an opening (or its wall)
        is missing from one of them.

    Examples
    --------
    >>> from archlux.types import Plan, Room
    >>> before = Plan(rooms=(Room(id="a", type="living_room", x=0, y=0, w=4, h=3),))
    >>> after = Plan(rooms=(Room(id="a", type="living_room", x=0, y=0, w=4.5, h=3),))
    >>> measure_displacement(before, after).max_wall_shift
    0.5
    """
    after = {room.id: room for room in corrected.rooms}
    if set(after) != {room.id for room in proposed.rooms}:
        raise InvalidInput("corrected.rooms", "the two plans do not have the same rooms")
    rooms = tuple(_room_shift(room, after[room.id]) for room in proposed.rooms)
    return Displacement(rooms=rooms, openings=_opening_shifts(proposed, corrected))


@dataclass(frozen=True, slots=True)
class Distribution:
    """Summary of a population of measurements: centre, spread, extremes, histogram.

    A mean alone hides a population piled up at a bound; ``counts`` shows it.

    Attributes
    ----------
    n : int
        Number of values.
    mean, median : float
        Centre.
    p10, p90 : float
        10th and 90th percentiles (linear interpolation): the spread, as an interval.
    minimum, maximum : float
        Extremes.
    edges : tuple of float
        Histogram bin edges, ``len(counts) + 1`` of them.
    counts : tuple of int
        Values per bin; they sum to ``n``.
    """

    n: int
    mean: float
    median: float
    p10: float
    p90: float
    minimum: float
    maximum: float
    edges: tuple[float, ...]
    counts: tuple[int, ...]


def summarize(values: Iterable[float], *, bins: int = 10) -> Distribution:
    """Summarize measurements: mean, median, 10-90 % interval, extremes, histogram.

    Parameters
    ----------
    values : iterable of float
        Measurements (displacements, gains...). Every value must be finite.
    bins : int, optional
        Number of histogram bins.

    Returns
    -------
    Distribution
        The summary.

    Raises
    ------
    InvalidInput
        No value, a non-finite value, or ``bins < 1``.
    """
    array = np.asarray(list(values), dtype=float)
    if array.size == 0:
        raise InvalidInput("values", "nothing to summarize")
    if not np.all(np.isfinite(array)):
        raise InvalidInput("values", "every value must be finite")
    if bins < 1:
        raise InvalidInput("bins", f"must be >= 1, got {bins}")
    counts, edges = np.histogram(array, bins=bins)
    p10, median, p90 = (float(q) for q in np.percentile(array, (10, 50, 90)))
    return Distribution(
        n=int(array.size),
        mean=float(array.mean()),
        median=median,
        p10=p10,
        p90=p90,
        minimum=float(array.min()),
        maximum=float(array.max()),
        edges=tuple(float(edge) for edge in edges),
        counts=tuple(int(count) for count in counts),
    )


def count_saturated(values: Iterable[float], *, budget: float) -> int:
    """Number of displacements that reached the budget (up to ``FW_FEASIBILITY_M``).

    Parameters
    ----------
    values : iterable of float
        L-infinity displacements, in metres.
    budget : float
        The budget they were bounded by.

    Returns
    -------
    int
        How many equal the budget: there, the budget, not the geometry, stopped the run.
    """
    return sum(1 for value in values if value >= budget - FW_FEASIBILITY_M)
