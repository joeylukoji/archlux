"""Grid inference: recover the combinatorial structure of a proposed plan.

Split from :mod:`archlux.geom.pavage` (PLAN.md phase 4, block 3): :class:`Grid` and
:func:`deduce_grid`, which groups edges into grid lines, consolidates and repairs them
(:mod:`archlux.geom.grid_repair`) and **proves** the cells partition the outline. The
public names stay importable from :mod:`archlux.geom.pavage`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
from shapely import contains_xy
from shapely.geometry import Polygon

from archlux._deprecation import renamed_parameters
from archlux.errors import GridNotRecoverable, InvariantViolation, UnsupportedInput
from archlux.geom.grid_repair import _consolider, _couverture, _reparer_partition

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


def _regrouper(valeurs: Sequence[float], tolerance: float) -> tuple[list[float], dict[float, int]]:
    """Group close coordinates into increasing grid lines.

    Increasing sweep: values are aggregated as long as the gap to the **previous** one
    stays under ``tolerance``. The grouping is therefore transitive along a chain, which
    is intended: a string of edges offset step by step describes a single
    alignment intent.
    """
    triees = sorted(set(valeurs))
    if not triees:
        return [], {}
    groupes: list[list[float]] = [[triees[0]]]
    for value in triees[1:]:
        if value - groupes[-1][-1] <= tolerance:
            groupes[-1].append(value)
        else:
            groupes.append([value])
    lignes = [sum(g) / len(g) for g in groupes]
    rang: dict[float, int] = {}
    for indice, groupe in enumerate(groupes):
        for value in groupe:
            rang[value] = indice
    return lignes, rang


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

    lignes_x, rang_x, lignes_y, rang_y = _deduce_lines(plan, ctx, tolerance)
    bords_x, bords_y = _room_bounds(plan, rang_x, rang_y, tolerance)

    # Lines that carry an outline vertex are frozen: the envelope is an
    # input, it does not move. They therefore escape consolidation.
    ancrees_x = {rang_x[point[0]] for point in ctx.outline}
    ancrees_y = {rang_y[point[1]] for point in ctx.outline}

    if min_support > 1:
        lignes_x, bords_x, ancrees_x = _consolider(lignes_x, bords_x, ancrees_x, min_support)
        lignes_y, bords_y, ancrees_y = _consolider(lignes_y, bords_y, ancrees_y, min_support)

    incidences = [
        (piece.id, gauche, droite, bas, haut)
        for piece, (gauche, droite), (bas, haut) in zip(plan.rooms, bords_x, bords_y, strict=True)
    ]
    incidences = _verify_partition(ctx, lignes_x, lignes_y, incidences, repair_budget)

    # Last safety net: repair and consolidation only handle indices, and a
    # room with reversed edges would silently pass into the LP.
    for nom, gauche, droite, bas, haut in incidences:
        if gauche >= droite or bas >= haut:
            raise InvariantViolation((f"room {nom} degenerate in the grid",))

    return Grid(
        x_lines=tuple(lignes_x),
        y_lines=tuple(lignes_y),
        incidences=tuple(incidences),
        anchored_x=frozenset(ancrees_x),
        anchored_y=frozenset(ancrees_y),
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
    xs_contour = [point[0] for point in ctx.outline]
    ys_contour = [point[1] for point in ctx.outline]
    # All the outline coordinates enter the grid, not only the
    # extremes: on a rectilinear outline, each cell must be entirely
    # inside or entirely outside, otherwise the mask below is meaningless.
    lignes_x, rang_x = _regrouper([*xs, *xs_contour], tolerance)
    lignes_y, rang_y = _regrouper([*ys, *ys_contour], tolerance)
    _anchor_outline_vertices("x", lignes_x, rang_x, xs_contour, tolerance)
    _anchor_outline_vertices("y", lignes_y, rang_y, ys_contour, tolerance)
    if len(lignes_x) < 2 or len(lignes_y) < 2:
        raise UnsupportedInput("tiling grid: fewer than two grid lines on an axis")
    return lignes_x, rang_x, lignes_y, rang_y


def _anchor_outline_vertices(
    axe: str, lignes: list[float], rang: dict[float, int], valeurs: list[float], tolerance: float
) -> None:
    """Pin the grid lines that carry an outline vertex to that exact coordinate.

    Extracted from :func:`_deduce_lines` (PLAN.md phase 4, block 3). A line that
    carries an outline vertex *is* the outline: the group mean would drift with the
    room edges grouped with it, and the anchoring equalities would then pin the rooms
    off the outline, leaving an uncovered strip. Mutates ``lignes`` in place.

    Raises
    ------
    UnsupportedInput
        Two outline edges fall in the same grid line through room edges within the
        grouping tolerance.
    """
    portees: dict[int, float] = {}
    for value in valeurs:
        ligne = rang[value]
        if portees.setdefault(ligne, value) != value:
            raise UnsupportedInput(
                f"tiling grid: outline edges {portees[ligne]} and {value} in {axe} "
                f"fall in one grid line, joined through room edges within the grouping "
                f"tolerance {tolerance} m"
            )
        lignes[ligne] = value


def _room_bounds(
    plan: Plan, rang_x: dict[float, int], rang_y: dict[float, int], tolerance: float
) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    """Room bounds as grid-line indices, checked non-degenerate.

    Extracted from :func:`deduce_grid` (PLAN.md phase 4, block 3).

    Raises
    ------
    UnsupportedInput
        A room is flat in one axis after grouping (thinner than ``tolerance``, or of
        negative size).
    """
    bords_x = [(rang_x[p.x], rang_x[p.x + p.w]) for p in plan.rooms]
    bords_y = [(rang_y[p.y], rang_y[p.y + p.h]) for p in plan.rooms]
    for axe, bords in (("x", bords_x), ("y", bords_y)):
        for (debut, fin), piece in zip(bords, plan.rooms, strict=True):
            if debut >= fin:
                raise UnsupportedInput(
                    f"tiling grid: room {piece.id} is flat in {axe} (thinner than the "
                    f"grouping tolerance {tolerance} m, or of negative size)"
                )
    return bords_x, bords_y


def _verify_partition(
    ctx: Context,
    lignes_x: list[float],
    lignes_y: list[float],
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
    enveloppe = Polygon(ctx.outline)
    if not enveloppe.is_valid:
        raise UnsupportedInput("tiling grid: the outline is not a valid polygon")
    centres_x = 0.5 * (np.asarray(lignes_x[:-1]) + np.asarray(lignes_x[1:]))
    centres_y = 0.5 * (np.asarray(lignes_y[:-1]) + np.asarray(lignes_y[1:]))
    maille_x, maille_y = np.meshgrid(centres_x, centres_y, indexing="ij")
    dedans = np.asarray(contains_xy(enveloppe, maille_x, maille_y))
    forme = (len(lignes_x) - 1, len(lignes_y) - 1)
    grille = _couverture(incidences, forme)
    trop = int(np.sum(grille[dedans] > 1) + np.sum(grille[~dedans] > 0))
    manque = int(np.sum(grille[dedans] < 1))
    if not (trop or manque):
        return incidences
    # Local defect of a few cells: try a bounded index adjustment
    # before refusing. Beyond the budget, it is no longer a wrong dimension.
    repare = _reparer_partition(incidences, dedans, repair_budget) if repair_budget > 0 else None
    if repare is None:
        raise GridNotRecoverable(excess=trop, missing=manque)
    return repare
