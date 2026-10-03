"""Grid inference: recover the combinatorial structure of a proposed plan.

Split from :mod:`archlux.geom.tiling` (PLAN.md phase 4, block 3): :class:`Grid` and
:func:`deduce_grid`, which groups edges into grid lines, consolidates and repairs them
(:mod:`archlux.geom.grid_repair`) and **proves** the cells partition the outline. The
public names stay importable from :mod:`archlux.geom.tiling`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
from shapely import contains_xy
from shapely.geometry import Polygon

from archlux._deprecation import renamed_parameters
from archlux.errors import GridNotRecoverable, InvariantViolation, UnsupportedInput
from archlux.geom.grid_repair import _consolidate, _coverage, _repair_partition

if TYPE_CHECKING:
    from collections.abc import Sequence

    from archlux.types import Context, Plan

__all__ = ["Grid", "deduce_grid"]


@dataclass(frozen=True, slots=True)
class Grid:
    """Combinatorial structure of a rectangular dissection.

    Attributes
    ----------
    x_lines, y_lines : tuple of float
        **Reference** positions of the grid lines, increasing. They are not
        imposed: only the incidences are. They serve as a fallback feasible
        point and for diagnostics.
    incidences : tuple of (str, int, int, int, int)
        Per room: ``(id, left, right, bottom, top)``, indices into
        ``x_lines`` / ``y_lines``. ``left < right`` and ``bottom < top``.
    anchored_x, anchored_y : frozenset of int
        Indices of the lines that carry an outline vertex: fixed on the outline.
    """

    x_lines: tuple[float, ...]
    y_lines: tuple[float, ...]
    incidences: tuple[tuple[str, int, int, int, int], ...]
    anchored_x: frozenset[int] = frozenset()
    anchored_y: frozenset[int] = frozenset()

    @property
    def n_cells(self) -> int:
        """Number of cells of the array, ``(p - 1) × (q - 1)``."""
        return (len(self.x_lines) - 1) * (len(self.y_lines) - 1)


def _cluster(values: Sequence[float], tolerance: float) -> tuple[list[float], dict[float, int]]:
    """Group close coordinates into increasing grid lines.

    Increasing sweep: values are aggregated as long as the gap to the **previous** one
    stays under ``tolerance``. The grouping is therefore transitive along a chain, which
    is intended: a string of edges offset step by step describes a single
    alignment intent.
    """
    sorted_lines = sorted(set(values))
    if not sorted_lines:
        return [], {}
    groups: list[list[float]] = [[sorted_lines[0]]]
    for value in sorted_lines[1:]:
        if value - groups[-1][-1] <= tolerance:
            groups[-1].append(value)
        else:
            groups.append([value])
    lines = [sum(g) / len(g) for g in groups]
    rank: dict[float, int] = {}
    for index, group in enumerate(groups):
        for value in group:
            rank[value] = index
    return lines, rank


@renamed_parameters({"support_min": "min_support", "budget_reparation": "repair_budget"})
def deduce_grid(
    plan: Plan,
    ctx: Context,
    *,
    tolerance: float = 0.01,
    min_support: int = 2,
    repair_budget: int = 4,
) -> Grid:
    """Recover the grid of the proposed plan and **prove** that it tiles the outline.

    Parameters
    ----------
    plan : Plan
        Proposed plan, possibly invalid. Its edges fix the incidences.
    ctx : Context
        The outline serves as the outer edge: the first and last line of
        each axis must coincide with it, otherwise the union does not cover the envelope.
    tolerance : float, optional
        **Numerical** grouping only: two edges closer than this
        threshold are the same line. Default 1 cm. This is not the recovery
        lever; see ``min_support``.
    min_support : int, optional
        An interior line carried by fewer than ``min_support`` edges is an
        **orphan**: it is absorbed into its nearest neighbor, unless
        this crushes a room. This is how the intended structure is recovered,
        without guessing a metric tolerance. Default 2: an interior wall separates
        two rooms, so it carries at least two edges. ``min_support=1`` disables
        consolidation.
    repair_budget : int, optional
        Maximum number of one-step adjustments of the partition repair. Default 4.
        ``0`` disables the repair.

    Returns
    -------
    Grid
        Verified structure: the covered cells form a partition.

    Raises
    ------
    GridNotRecoverable
        The cells do not form a partition: an empty cell (structural gap) or a cell
        covered twice (structural overlap). The fault is then not a coordinate
        offset but the order itself, and no partition move will repair it.
    UnsupportedInput
        An input the grid cannot describe: no room, an empty or invalid outline, fewer
        than two grid lines on an axis, a room flat after grouping (thinner than
        ``tolerance``), or two outline edges closer than ``tolerance`` (one grid line
        cannot lie exactly on both). ``GridNotRecoverable`` is a subclass.
    InvariantViolation
        Only on an internal defect: a room left degenerate by consolidation or repair,
        which both refuse such moves by construction.

    Notes
    -----
    Complexity: ``O(n log n)`` for the grouping, ``O(Σ cells)`` for the
    partition check, that is ``O(n·p·q)`` at worst.
    """
    if not plan.rooms:
        raise UnsupportedInput("tiling grid: the plan has no room")
    if not ctx.outline:
        raise UnsupportedInput("tiling grid: the outline is empty, the grid has no anchor")

    lines_x, rank_x, lines_y, rank_y = _deduce_lines(plan, ctx, tolerance)
    borders_x, borders_y = _room_bounds(plan, rank_x, rank_y, tolerance)

    # Lines that carry an outline vertex are frozen: the envelope is an
    # input, it does not move. They therefore escape consolidation.
    anchored_xs = {rank_x[point[0]] for point in ctx.outline}
    anchored_ys = {rank_y[point[1]] for point in ctx.outline}

    if min_support > 1:
        lines_x, borders_x, anchored_xs = _consolidate(lines_x, borders_x, anchored_xs, min_support)
        lines_y, borders_y, anchored_ys = _consolidate(lines_y, borders_y, anchored_ys, min_support)

    incidences = [
        (room.id, left, right, low, high)
        for room, (left, right), (low, high) in zip(plan.rooms, borders_x, borders_y, strict=True)
    ]
    incidences = _verify_partition(ctx, lines_x, lines_y, incidences, repair_budget)

    # Last safety net: repair and consolidation only handle indices, and a
    # room with reversed edges would silently pass into the LP.
    for name, left, right, low, high in incidences:
        if left >= right or low >= high:
            raise InvariantViolation((f"room {name} degenerate in the grid",))

    return Grid(
        x_lines=tuple(lines_x),
        y_lines=tuple(lines_y),
        incidences=tuple(incidences),
        anchored_x=frozenset(anchored_xs),
        anchored_y=frozenset(anchored_ys),
    )


def _deduce_lines(
    plan: Plan, ctx: Context, tolerance: float
) -> tuple[list[float], dict[float, int], list[float], dict[float, int]]:
    """Group room and outline edges into grid lines, anchored to the outline.

    Extracted from :func:`deduce_grid` (PLAN.md phase 4, block 3): the grouping and
    outline-anchoring pass, on its own so the caller's own complexity does not include
    it.

    Raises
    ------
    UnsupportedInput
        Two outline edges fall in the same grid line through room edges within the
        grouping tolerance, or fewer than two grid lines result on an axis.
    """
    xs = [p.x for p in plan.rooms] + [p.x + p.w for p in plan.rooms]
    ys = [p.y for p in plan.rooms] + [p.y + p.h for p in plan.rooms]
    xs_outline = [point[0] for point in ctx.outline]
    ys_outline = [point[1] for point in ctx.outline]
    # All the outline coordinates enter the grid, not only the
    # extremes: on a rectilinear outline, each cell must be entirely
    # inside or entirely outside, otherwise the mask below is meaningless.
    lines_x, rank_x = _cluster([*xs, *xs_outline], tolerance)
    lines_y, rank_y = _cluster([*ys, *ys_outline], tolerance)
    _anchor_outline_vertices("x", lines_x, rank_x, xs_outline, tolerance)
    _anchor_outline_vertices("y", lines_y, rank_y, ys_outline, tolerance)
    if len(lines_x) < 2 or len(lines_y) < 2:
        raise UnsupportedInput("tiling grid: fewer than two grid lines on an axis")
    return lines_x, rank_x, lines_y, rank_y


def _anchor_outline_vertices(
    axis: str, lines: list[float], rank: dict[float, int], values: list[float], tolerance: float
) -> None:
    """Pin the grid lines that carry an outline vertex to that exact coordinate.

    Extracted from :func:`_deduce_lines` (PLAN.md phase 4, block 3). A line that
    carries an outline vertex *is* the outline: the group mean would drift with the
    room edges grouped with it, and the anchoring equalities would then pin the rooms
    off the outline, leaving an uncovered strip. Mutates ``lines`` in place.

    Raises
    ------
    UnsupportedInput
        Two outline edges fall in the same grid line through room edges within the
        grouping tolerance.
    """
    spans: dict[int, float] = {}
    for value in values:
        row = rank[value]
        if spans.setdefault(row, value) != value:
            raise UnsupportedInput(
                f"tiling grid: outline edges {spans[row]} and {value} in {axis} "
                f"fall in one grid line, joined through room edges within the grouping "
                f"tolerance {tolerance} m"
            )
        lines[row] = value


def _room_bounds(
    plan: Plan, rank_x: dict[float, int], rank_y: dict[float, int], tolerance: float
) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    """Room bounds as grid-line indices, checked non-degenerate.

    Extracted from :func:`deduce_grid` (PLAN.md phase 4, block 3).

    Raises
    ------
    UnsupportedInput
        A room is flat in one axis after grouping (thinner than ``tolerance``, or of
        negative size).
    """
    borders_x = [(rank_x[p.x], rank_x[p.x + p.w]) for p in plan.rooms]
    borders_y = [(rank_y[p.y], rank_y[p.y + p.h]) for p in plan.rooms]
    for axis, borders in (("x", borders_x), ("y", borders_y)):
        for (start, end), room in zip(borders, plan.rooms, strict=True):
            if start >= end:
                raise UnsupportedInput(
                    f"tiling grid: room {room.id} is flat in {axis} (thinner than the "
                    f"grouping tolerance {tolerance} m, or of negative size)"
                )
    return borders_x, borders_y


def _verify_partition(
    ctx: Context,
    lines_x: list[float],
    lines_y: list[float],
    incidences: list[tuple[str, int, int, int, int]],
    repair_budget: int,
) -> list[tuple[str, int, int, int, int]]:
    """Check the cells inside the outline form a partition; repair or refuse.

    Extracted from :func:`deduce_grid` (PLAN.md phase 4, block 3): each cell **inside
    the outline** covered exactly once, none outside. The real outline is rectilinear,
    not rectangular: requiring the bounding box to be tiled would be wrong.

    Raises
    ------
    UnsupportedInput
        The outline is not a valid polygon.
    GridNotRecoverable
        The cells do not form a partition and no bounded repair recovers one.
    """
    envelope = Polygon(ctx.outline)
    if not envelope.is_valid:
        raise UnsupportedInput("tiling grid: the outline is not a valid polygon")
    centers_x = 0.5 * (np.asarray(lines_x[:-1]) + np.asarray(lines_x[1:]))
    centers_y = 0.5 * (np.asarray(lines_y[:-1]) + np.asarray(lines_y[1:]))
    mesh_x, mesh_y = np.meshgrid(centers_x, centers_y, indexing="ij")
    inside = np.asarray(contains_xy(envelope, mesh_x, mesh_y))
    shape = (len(lines_x) - 1, len(lines_y) - 1)
    grid = _coverage(incidences, shape)
    excess_cells = int(np.sum(grid[inside] > 1) + np.sum(grid[~inside] > 0))
    lacking = int(np.sum(grid[inside] < 1))
    if not (excess_cells or lacking):
        return incidences
    # Local defect of a few cells: try a bounded index adjustment
    # before refusing. Beyond the budget, it is no longer a wrong dimension.
    repaired = _repair_partition(incidences, inside, repair_budget) if repair_budget > 0 else None
    if repaired is None:
        raise GridNotRecoverable(excess=excess_cells, missing=lacking)
    return repaired
