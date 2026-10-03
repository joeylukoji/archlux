r"""Exact tiling constraints: making a "gap" unrepresentable.

The problem
-----------
The order polytope is a **relaxation**: ``x_a + w_a <= x_b`` forbids
overlap, never a hole. If the input carries a gap, the holed plan is already
the closest point to itself: the L1 optimum leaves it as is, and
``certify.proof`` rejects it. Measured on MSD without this module: ``legalize`` repairs
68 % of the overlaps and 10 % of the gaps.

The result that unlocks it
--------------------------
In a rectangular dissection, every room edge is carried by a **grid
line**. Write room :math:`i` as
:math:`[v_{l(i)}, v_{r(i)}] \times [h_{b(i)}, h_{t(i)}]`, with integer indices. The
room then covers exactly the cells :math:`l(i) \le a < r(i)`,
:math:`b(i) \le \beta < t(i)`.

**The tiling condition bears only on the indices, never on the
coordinates.** The union tiles the outline if and only if these cells form
a partition of the array: a combinatorial fact, checked once.

It therefore suffices to impose *"these edges share a line"*, which is a set of
affine equalities in the existing variables. Every feasible point is then
an exact tiling: **a gap ceases to be representable**.

Two properties follow, and they are what distinguishes this approach from
contact freezing (:func:`~archlux.geom.polytope.freeze_contacts`):

1. **The system stays feasible.** The grid-line positions of the reference plan
   are always a feasible point. Freezing *approximately* saturated contacts
   offers no such guarantee: 8 % of LPs measured infeasible.
2. **The guarantee is structural, not numerical.** It depends on no
   tolerance at run time: the partition check has already happened.

Recovering the structure
------------------------
The counterpart is that the grid must be **recoverable** from the proposed plan,
which is precisely the faulty one. The lever is not a metric tolerance: guessing it
fails, too wide it crushes narrow rooms, too narrow it recovers
nothing (measured: 3.8 % repaired).

The right criterion is the **support** of a line, that is, the number of edges
it carries. In a sound plan, an interior line carries at least two: a
wall separates two rooms. Moving a room makes one edge leave its line and
creates a new one, carried by it alone. Absorbing the **orphan** lines into
their nearest neighbor, while refusing any merge that would crush a room,
thus recovers the intended structure with no threshold in meters. A 2 m gap is
recovered as well as a 5 cm gap, and a 40 cm partition survives.

A **bounded repair** of the partition is added: growing or shrinking a
room by one step as long as the cells concerned are all missing, or all
in excess. The budget (default 4) distinguishes repair from reconstruction.

Measured on MSD, 4,796 corrupted plans: repair goes from 35.9 % to 93.9 %, and
on gaps alone from 10.0 % to 98.0 %.

Grid recovery lives in :mod:`archlux.geom.grid` and its repair in
:mod:`archlux.geom.grid_repair`; both public names are re-exported here.

Reference: wall-coordinate formulation of rectangular dissections,
Otten (1982) and Lengauer (1990) ch. 10; see ``docs/formules/sources.md``.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

import numpy as np
from scipy import sparse

from archlux._deprecation import Alias, lazy_aliases, renamed_parameters
from archlux.errors import InvariantViolation
from archlux.geom.grid import Grid, deduce_grid

if TYPE_CHECKING:
    from archlux.geom.polytope import Polytope
    from archlux.types import Plan

__all__ = ["Grid", "deduce_grid", "extend_tiling", "snap_to_grid", "tiling_constraints"]

_EPS = 1e-9


@renamed_parameters({"trame": "grid"})
def snap_to_grid(plan: Plan, grid: Grid) -> Plan:
    """Place every room of ``plan`` on the reference lines of its recovered grid.

    The result is an exact tiling of the outline (the partition of ``grid`` is
    verified), so every pair of rooms is separated on the axis the grid says. Reading
    the relative order from it rather than from the faulty plan keeps the order
    consistent with the tiling equalities: a room moved onto its neighbour overlaps it
    on both axes, and the centres alone may then pick the wrong axis.

    Parameters
    ----------
    plan : Plan
        The proposed plan ``grid`` was recovered from.
    grid : Grid
        Grid returned by :func:`deduce_grid` for ``plan``.

    Returns
    -------
    Plan
        New plan, rooms in the same order, only their coordinates changed.
    """
    lines = {name: (left, right, low, high) for name, left, right, low, high in grid.incidences}
    rooms = []
    for room in plan.rooms:
        left, right, low, high = lines[room.id]
        x, y = grid.x_lines[left], grid.y_lines[low]
        rooms.append(replace(room, x=x, y=y, w=grid.x_lines[right] - x, h=grid.y_lines[high] - y))
    return replace(plan, rooms=tuple(rooms))


@renamed_parameters({"trame": "grid"})
def tiling_constraints(
    grid: Grid, index: dict[str, int]
) -> tuple[tuple[str, dict[str, float], float], ...]:
    """Translate the grid into affine equalities ``Σ a_k v_k = b``.

    Two families, and nothing else:

    - **line sharing**: two edges on the same line are equal. The first edge
      met serves as reference, the following ones attach to it: ``m`` edges
      on a line give ``m - 1`` equalities, never ``m(m-1)/2``.
    - **anchoring**: the edges carried by the first and last line of an axis
      are fixed on the outline. Without them the whole grid could slide, or
      shrink inside the envelope.

    Returns
    -------
    tuple
        Triplets ``(label, terms, right_hand_side)``, same conventions as
        :func:`~archlux.geom.rectilinear.merge_constraints`.

    Raises
    ------
    InvariantViolation
        An expected variable is missing from ``index``.
    """
    equalities: list[tuple[str, dict[str, float], float]] = []
    # An edge is described by the terms that express it: left edge = x,
    # right edge = x + w. Same in y.
    borders_x: dict[int, list[tuple[str, dict[str, float]]]] = {}
    borders_y: dict[int, list[tuple[str, dict[str, float]]]] = {}
    for room_id, left, right, low, high in grid.incidences:
        for name in (f"{room_id}.x", f"{room_id}.w", f"{room_id}.y", f"{room_id}.h"):
            if name not in index:
                raise InvariantViolation((f"variable missing from the index: {name}",))
        borders_x.setdefault(left, []).append((room_id, {f"{room_id}.x": 1.0}))
        borders_x.setdefault(right, []).append(
            (room_id, {f"{room_id}.x": 1.0, f"{room_id}.w": 1.0})
        )
        borders_y.setdefault(low, []).append((room_id, {f"{room_id}.y": 1.0}))
        borders_y.setdefault(high, []).append((room_id, {f"{room_id}.y": 1.0, f"{room_id}.h": 1.0}))

    for axis, borders, lines, anchored in (
        ("x", borders_x, grid.x_lines, grid.anchored_x),
        ("y", borders_y, grid.y_lines, grid.anchored_y),
    ):
        for row, members in sorted(borders.items()):
            if row in anchored:
                # Anchoring: each edge of the line is fixed on the outline.
                target = lines[row]
                for room_id, terms in members:
                    equalities.append(
                        (f"contour {axis}={target:.4f} {room_id}", dict(terms), target)
                    )
                continue
            reference_id, reference = members[0]
            for room_id, terms in members[1:]:
                combines = dict(reference)
                for name, coef in terms.items():
                    combines[name] = combines.get(name, 0.0) - coef
                combines = {n: c for n, c in combines.items() if abs(c) > _EPS}
                if not combines:
                    continue
                equalities.append(
                    (
                        f"trame {axis}#{row} {reference_id}|{room_id}",
                        combines,
                        0.0,
                    )
                )
    return tuple(equalities)


@renamed_parameters({"trame": "grid"})
def extend_tiling(poly: Polytope, grid: Grid) -> Polytope:
    """Add the tiling equalities to the polytope (``A_eq``, ``b_eq``).

    Parameters
    ----------
    poly : Polytope
        System already assembled for the rooms of ``grid``.
    grid : Grid
        Structure verified by :func:`deduce_grid`.

    Returns
    -------
    Polytope
        New instance. ``origins`` is unchanged: these are equalities, not
        dualized inequalities, so they do **not** appear in the
        dual diagnostic of the certificate.
    """
    equalities = tiling_constraints(grid, poly.index)
    if not equalities:
        return poly
    n_var = len(poly.index)
    lines: list[int] = []
    columns: list[int] = []
    values: list[float] = []
    seconds: list[float] = []
    labels: list[str] = []
    for rank, (label, terms, bound) in enumerate(equalities):
        for name, coef in terms.items():
            lines.append(rank)
            columns.append(poly.index[name])
            values.append(coef)
        seconds.append(bound)
        labels.append(f"tiling {label}")
    a_extra = sparse.coo_matrix((values, (lines, columns)), shape=(len(equalities), n_var)).tocsr()
    if poly.A_eq.shape[0]:
        a_eq = sparse.vstack([poly.A_eq, a_extra], format="csr")
        b_eq = np.concatenate([poly.b_eq, np.asarray(seconds, dtype=float)])
    else:
        a_eq = a_extra
        b_eq = np.asarray(seconds, dtype=float)
    return replace(poly, A_eq=a_eq, b_eq=b_eq, origins_eq=poly.eq_labels() + tuple(labels))


__getattr__ = lazy_aliases(
    __name__,
    {
        "Trame": Alias(Grid, "archlux.geom.tiling.Grid"),
        "deduire_trame": Alias(deduce_grid, "archlux.geom.tiling.deduce_grid"),
        "contraintes_pavage": Alias(tiling_constraints, "archlux.geom.tiling.tiling_constraints"),
        "etendre_pavage": Alias(extend_tiling, "archlux.geom.tiling.extend_tiling"),
    },
)
