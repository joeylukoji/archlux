"""Repair of a recovered grid: orphan-line consolidation and bounded partition repair.

Split from :mod:`archlux.geom.tiling` (PLAN.md phase 4, block 3). Both passes move
**indices only**, never a coordinate; :func:`archlux.geom.grid.deduce_grid` calls them.
See :mod:`archlux.geom.tiling` for the rationale (support of a line, repair budget).
"""

from __future__ import annotations

import numpy as np

__all__: list[str] = []


def _consolidate(
    lines: list[float],
    borders: list[tuple[int, int]],
    protected: set[int],
    min_support: int,
) -> tuple[list[float], list[tuple[int, int]], set[int]]:
    """Absorb the **orphan** lines into their nearest neighbor.

    In a sound plan, an interior grid line is carried by several
    edges: a wall separates two rooms, so at least one edge on each side.
    Moving a room makes one edge leave its line and creates a new one,
    carried by it alone. The **support** (the number of edges carried) thus
    distinguishes the intended structure from the accident, without any metric
    tolerance having to be guessed.

    Absorption continues while an interior line of support ``< min_support`` remains,
    merging it with the nearest line, unless this **crushes a
    room**, that is, brings both of its edges onto the same line. This refusal is what
    keeps a narrow room from being absorbed by a tolerance that is too wide.

    Parameters
    ----------
    lignes : list of float
        Line positions, increasing.
    bords : list of (int, int)
        One ``(low_line, high_line)`` pair per room, on this axis.
    protegees : set of int
        Lines that are never absorbed: the outline edges.
    min_support : int
        Below this number of carried edges, an interior line is an orphan.

    Returns
    -------
    tuple
        ``(lignes, bords, protegees)`` reindexed, with no absorbable orphan line left.
    """
    while True:
        support: dict[int, int] = dict.fromkeys(range(len(lines)), 0)
        for low_line, high_line in borders:
            support[low_line] += 1
            support[high_line] += 1
        candidates = sorted(
            (k for k, n in support.items() if n < min_support and k not in protected),
            key=lambda k: (support[k], k),
        )
        merge: tuple[int, int] | None = None
        for orphan in candidates:
            neighbours = sorted(
                (j for j in range(len(lines)) if j != orphan),
                key=lambda j: abs(lines[j] - lines[orphan]),
            )
            for target in neighbours:
                replaced = {orphan: target}
                # The nearest neighbor may lie on the other side of the moved
                # edge: testing equality is not enough, strict order is needed,
                # otherwise the room comes out with its edges reversed.
                collapses = any(
                    replaced.get(low_line, low_line) >= replaced.get(high_line, high_line)
                    for low_line, high_line in borders
                )
                if not collapses:
                    merge = (orphan, target)
                    break
            if merge is not None:
                break
        if merge is None:
            return lines, borders, protected
        orphan, target = merge
        borders = [
            (
                target if low_line == orphan else low_line,
                target if high_line == orphan else high_line,
            )
            for low_line, high_line in borders
        ]
        # Reindex, removing the absorbed line, protected ones included.
        kept = [k for k in range(len(lines)) if k != orphan]
        new = {old: rank for rank, old in enumerate(kept)}
        lines = [lines[k] for k in kept]
        borders = [(new[low_line], new[high_line]) for low_line, high_line in borders]
        protected = {new[k] for k in protected if k in new}


def _coverage(
    incidences: list[tuple[str, int, int, int, int]], shape: tuple[int, int]
) -> np.ndarray:
    """Number of rooms covering each cell."""
    grid = np.zeros(shape, dtype=int)
    for _, left, right, low, high in incidences:
        grid[left:right, low:high] += 1
    return grid


def _touch_ups(
    incidence: tuple[str, int, int, int, int], shape: tuple[int, int]
) -> list[tuple[tuple[str, int, int, int, int], tuple[slice, slice], bool]]:
    """Growths and shrinks of one step, with the cells concerned.

    The boolean says whether it is an extension (true) or a reduction (false).
    Moving a single index by one step leaves the room rectangular by construction.
    """
    name, left, right, low, high = incidence
    width, height = shape
    proposals: list[tuple[tuple[str, int, int, int, int], tuple[slice, slice], bool]] = []
    if left > 0:
        proposals.append(
            (
                (name, left - 1, right, low, high),
                (slice(left - 1, left), slice(low, high)),
                True,
            )
        )
    if right < width:
        proposals.append(
            (
                (name, left, right + 1, low, high),
                (slice(right, right + 1), slice(low, high)),
                True,
            )
        )
    if low > 0:
        proposals.append(
            (
                (name, left, right, low - 1, high),
                (slice(left, right), slice(low - 1, low)),
                True,
            )
        )
    if high < height:
        proposals.append(
            (
                (name, left, right, low, high + 1),
                (slice(left, right), slice(high, high + 1)),
                True,
            )
        )
    if right - left > 1:
        proposals.append(
            (
                (name, left + 1, right, low, high),
                (slice(left, left + 1), slice(low, high)),
                False,
            )
        )
        proposals.append(
            (
                (name, left, right - 1, low, high),
                (slice(right - 1, right), slice(low, high)),
                False,
            )
        )
    if high - low > 1:
        proposals.append(
            (
                (name, left, right, low + 1, high),
                (slice(left, right), slice(low, low + 1)),
                False,
            )
        )
        proposals.append(
            (
                (name, left, right, low, high - 1),
                (slice(left, right), slice(high - 1, high)),
                False,
            )
        )
    return proposals


def _repair_partition(
    incidences: list[tuple[str, int, int, int, int]],
    inside: np.ndarray,
    budget: int,
) -> list[tuple[str, int, int, int, int]] | None:
    """Fix a partition that is off by a few cells, in indices only.

    After consolidation, **local** defects remain: a cell that is not
    covered, or covered twice. Measured on MSD, this is the dominant case:
    127 gaps and 115 overlaps of exactly one cell out of 1,200 corruptions.

    They are absorbed by growing or shrinking a room **by one step**, which
    leaves it rectangular by construction: only the indices move, never
    a coordinate. An extension is kept only if **all** the cells
    it gains are missing; a reduction, only if all those it
    frees are in excess. No structure is thus invented: a room gets back
    what a fault had taken from it, or loses what it had taken.

    Parameters
    ----------
    incidences : list of (str, int, int, int, int)
        Current incidences, possibly faulty.
    dedans : numpy.ndarray of bool
        Mask of the cells inside the outline.
    budget : int
        Maximum number of adjustments. Bounding it distinguishes a **repair** from a
        reconstruction: beyond it, the fault is no longer a wrong dimension but an
        order inconsistency, and one must refuse rather than guess.

    Returns
    -------
    list or None
        Repaired incidences, or ``None`` if the budget is exhausted before a partition.
    """
    shape = (int(inside.shape[0]), int(inside.shape[1]))
    incidences = list(incidences)
    for _ in range(budget):
        grid = _coverage(incidences, shape)
        missing = inside & (grid < 1)
        surplus = (inside & (grid > 1)) | (~inside & (grid > 0))
        if not missing.any() and not surplus.any():
            return incidences
        best: tuple[int, tuple[str, int, int, int, int], int] | None = None
        for rank, incidence in enumerate(incidences):
            for propose, cellules, extension in _touch_ups(incidence, shape):
                targeted = missing if extension else surplus
                zone = targeted[cellules]
                if zone.size and bool(zone.all()):
                    gain = int(zone.size)
                    if best is None or gain > best[2]:
                        best = (rank, propose, gain)
        if best is None:
            return None
        rank, propose, _ = best
        incidences[rank] = propose
    grid = _coverage(incidences, shape)
    rest = bool((inside & (grid != 1)).any() or (~inside & (grid > 0)).any())
    return None if rest else incidences
