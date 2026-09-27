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

Reference: wall-coordinate formulation of rectangular dissections,
Otten (1982) and Lengauer (1990) ch. 10; see ``docs/formules/sources.md``.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

import numpy as np
from scipy import sparse
from shapely import contains_xy
from shapely.geometry import Polygon

from archlux._deprecation import Alias, lazy_aliases, renamed_parameters
from archlux.errors import GridNotRecoverable, InvariantViolation, UnsupportedInput

if TYPE_CHECKING:
    from collections.abc import Sequence

    from archlux.geom.polytope import Polytope
    from archlux.types import Context, Plan

__all__ = ["Grid", "deduce_grid", "extend_tiling", "snap_to_grid", "tiling_constraints"]

_EPS = 1e-9


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


def _consolider(
    lignes: list[float],
    bords: list[tuple[int, int]],
    protegees: set[int],
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
        support: dict[int, int] = dict.fromkeys(range(len(lignes)), 0)
        for basse, haute in bords:
            support[basse] += 1
            support[haute] += 1
        candidates = sorted(
            (k for k, n in support.items() if n < min_support and k not in protegees),
            key=lambda k: (support[k], k),
        )
        fusion: tuple[int, int] | None = None
        for orpheline in candidates:
            voisines = sorted(
                (j for j in range(len(lignes)) if j != orpheline),
                key=lambda j: abs(lignes[j] - lignes[orpheline]),
            )
            for cible in voisines:
                remplace = {orpheline: cible}
                # The nearest neighbor may lie on the other side of the moved
                # edge: testing equality is not enough, strict order is needed,
                # otherwise the room comes out with its edges reversed.
                ecrase = any(
                    remplace.get(basse, basse) >= remplace.get(haute, haute)
                    for basse, haute in bords
                )
                if not ecrase:
                    fusion = (orpheline, cible)
                    break
            if fusion is not None:
                break
        if fusion is None:
            return lignes, bords, protegees
        orpheline, cible = fusion
        bords = [
            (cible if basse == orpheline else basse, cible if haute == orpheline else haute)
            for basse, haute in bords
        ]
        # Reindex, removing the absorbed line, protected ones included.
        garde = [k for k in range(len(lignes)) if k != orpheline]
        nouveau = {ancien: rang for rang, ancien in enumerate(garde)}
        lignes = [lignes[k] for k in garde]
        bords = [(nouveau[basse], nouveau[haute]) for basse, haute in bords]
        protegees = {nouveau[k] for k in protegees if k in nouveau}


def _couverture(
    incidences: list[tuple[str, int, int, int, int]], forme: tuple[int, int]
) -> np.ndarray:
    """Number of rooms covering each cell."""
    grille = np.zeros(forme, dtype=int)
    for _, gauche, droite, bas, haut in incidences:
        grille[gauche:droite, bas:haut] += 1
    return grille


def _retouches(
    incidence: tuple[str, int, int, int, int], forme: tuple[int, int]
) -> list[tuple[tuple[str, int, int, int, int], tuple[slice, slice], bool]]:
    """Growths and shrinks of one step, with the cells concerned.

    The boolean says whether it is an extension (true) or a reduction (false).
    Moving a single index by one step leaves the room rectangular by construction.
    """
    nom, gauche, droite, bas, haut = incidence
    largeur, hauteur = forme
    propositions: list[tuple[tuple[str, int, int, int, int], tuple[slice, slice], bool]] = []
    if gauche > 0:
        propositions.append(
            (
                (nom, gauche - 1, droite, bas, haut),
                (slice(gauche - 1, gauche), slice(bas, haut)),
                True,
            )
        )
    if droite < largeur:
        propositions.append(
            (
                (nom, gauche, droite + 1, bas, haut),
                (slice(droite, droite + 1), slice(bas, haut)),
                True,
            )
        )
    if bas > 0:
        propositions.append(
            (
                (nom, gauche, droite, bas - 1, haut),
                (slice(gauche, droite), slice(bas - 1, bas)),
                True,
            )
        )
    if haut < hauteur:
        propositions.append(
            (
                (nom, gauche, droite, bas, haut + 1),
                (slice(gauche, droite), slice(haut, haut + 1)),
                True,
            )
        )
    if droite - gauche > 1:
        propositions.append(
            (
                (nom, gauche + 1, droite, bas, haut),
                (slice(gauche, gauche + 1), slice(bas, haut)),
                False,
            )
        )
        propositions.append(
            (
                (nom, gauche, droite - 1, bas, haut),
                (slice(droite - 1, droite), slice(bas, haut)),
                False,
            )
        )
    if haut - bas > 1:
        propositions.append(
            (
                (nom, gauche, droite, bas + 1, haut),
                (slice(gauche, droite), slice(bas, bas + 1)),
                False,
            )
        )
        propositions.append(
            (
                (nom, gauche, droite, bas, haut - 1),
                (slice(gauche, droite), slice(haut - 1, haut)),
                False,
            )
        )
    return propositions


def _reparer_partition(
    incidences: list[tuple[str, int, int, int, int]],
    dedans: np.ndarray,
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
    forme = (int(dedans.shape[0]), int(dedans.shape[1]))
    incidences = list(incidences)
    for _ in range(budget):
        grille = _couverture(incidences, forme)
        manquantes = dedans & (grille < 1)
        excedents = (dedans & (grille > 1)) | (~dedans & (grille > 0))
        if not manquantes.any() and not excedents.any():
            return incidences
        meilleure: tuple[int, tuple[str, int, int, int, int], int] | None = None
        for rang, incidence in enumerate(incidences):
            for propose, cellules, extension in _retouches(incidence, forme):
                vise = manquantes if extension else excedents
                zone = vise[cellules]
                if zone.size and bool(zone.all()):
                    gain = int(zone.size)
                    if meilleure is None or gain > meilleure[2]:
                        meilleure = (rang, propose, gain)
        if meilleure is None:
            return None
        rang, propose, _ = meilleure
        incidences[rang] = propose
    grille = _couverture(incidences, forme)
    reste = bool((dedans & (grille != 1)).any() or (~dedans & (grille > 0)).any())
    return None if reste else incidences


@renamed_parameters({"support_min": "min_support"})
def deduce_grid(
    plan: Plan,
    ctx: Context,
    *,
    tolerance: float = 0.01,
    min_support: int = 2,
    budget_reparation: int = 4,
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
    budget_reparation : int, optional
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

    xs = [p.x for p in plan.rooms] + [p.x + p.w for p in plan.rooms]
    ys = [p.y for p in plan.rooms] + [p.y + p.h for p in plan.rooms]
    xs_contour = [point[0] for point in ctx.outline]
    ys_contour = [point[1] for point in ctx.outline]
    # All the outline coordinates enter the grid, not only the
    # extremes: on a rectilinear outline, each cell must be entirely
    # inside or entirely outside, otherwise the mask below is meaningless.
    lignes_x, rang_x = _regrouper([*xs, *xs_contour], tolerance)
    lignes_y, rang_y = _regrouper([*ys, *ys_contour], tolerance)
    # A line that carries an outline vertex *is* the outline: the group mean would
    # drift with the room edges grouped with it, and the anchoring equalities would
    # then pin the rooms off the outline, leaving an uncovered strip.
    for axe, lignes, rang, valeurs in (
        ("x", lignes_x, rang_x, xs_contour),
        ("y", lignes_y, rang_y, ys_contour),
    ):
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
    if len(lignes_x) < 2 or len(lignes_y) < 2:
        raise UnsupportedInput("tiling grid: fewer than two grid lines on an axis")

    bords_x = [(rang_x[p.x], rang_x[p.x + p.w]) for p in plan.rooms]
    bords_y = [(rang_y[p.y], rang_y[p.y + p.h]) for p in plan.rooms]
    for axe, bords in (("x", bords_x), ("y", bords_y)):
        for (debut, fin), piece in zip(bords, plan.rooms, strict=True):
            if debut >= fin:
                raise UnsupportedInput(
                    f"tiling grid: room {piece.id} is flat in {axe} (thinner than the "
                    f"grouping tolerance {tolerance} m, or of negative size)"
                )

    # Lines that carry an outline vertex are frozen: the envelope is an
    # input, it does not move. They therefore escape consolidation.
    ancrees_x = {rang_x[v] for v in xs_contour}
    ancrees_y = {rang_y[v] for v in ys_contour}

    if min_support > 1:
        lignes_x, bords_x, ancrees_x = _consolider(lignes_x, bords_x, ancrees_x, min_support)
        lignes_y, bords_y, ancrees_y = _consolider(lignes_y, bords_y, ancrees_y, min_support)

    incidences = [
        (piece.id, gauche, droite, bas, haut)
        for piece, (gauche, droite), (bas, haut) in zip(plan.rooms, bords_x, bords_y, strict=True)
    ]

    # Partition: each cell **inside the outline** covered exactly once, and no
    # outside cell covered. The real outline is rectilinear, not
    # rectangular: requiring the bounding box to be tiled would be wrong.
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
    if trop or manque:
        # Local defect of a few cells: try a bounded index adjustment
        # before refusing. Beyond the budget, it is no longer a wrong dimension.
        repare = (
            _reparer_partition(incidences, dedans, budget_reparation)
            if budget_reparation > 0
            else None
        )
        if repare is None:
            raise GridNotRecoverable(excess=trop, missing=manque)
        incidences = repare

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
    lignes = {
        nom: (gauche, droite, bas, haut) for nom, gauche, droite, bas, haut in grid.incidences
    }
    rooms = []
    for piece in plan.rooms:
        gauche, droite, bas, haut = lignes[piece.id]
        x, y = grid.x_lines[gauche], grid.y_lines[bas]
        rooms.append(replace(piece, x=x, y=y, w=grid.x_lines[droite] - x, h=grid.y_lines[haut] - y))
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
        :func:`~archlux.geom.rectilineaire.contraintes_fusion`.

    Raises
    ------
    InvariantViolation
        An expected variable is missing from ``index``.
    """
    egalites: list[tuple[str, dict[str, float], float]] = []
    # An edge is described by the terms that express it: left edge = x,
    # right edge = x + w. Same in y.
    bords_x: dict[int, list[tuple[str, dict[str, float]]]] = {}
    bords_y: dict[int, list[tuple[str, dict[str, float]]]] = {}
    for piece_id, gauche, droite, bas, haut in grid.incidences:
        for nom in (f"{piece_id}.x", f"{piece_id}.w", f"{piece_id}.y", f"{piece_id}.h"):
            if nom not in index:
                raise InvariantViolation((f"variable missing from the index: {nom}",))
        bords_x.setdefault(gauche, []).append((piece_id, {f"{piece_id}.x": 1.0}))
        bords_x.setdefault(droite, []).append(
            (piece_id, {f"{piece_id}.x": 1.0, f"{piece_id}.w": 1.0})
        )
        bords_y.setdefault(bas, []).append((piece_id, {f"{piece_id}.y": 1.0}))
        bords_y.setdefault(haut, []).append(
            (piece_id, {f"{piece_id}.y": 1.0, f"{piece_id}.h": 1.0})
        )

    for axe, bords, lignes, ancrees in (
        ("x", bords_x, grid.x_lines, grid.anchored_x),
        ("y", bords_y, grid.y_lines, grid.anchored_y),
    ):
        for ligne, membres in sorted(bords.items()):
            if ligne in ancrees:
                # Anchoring: each edge of the line is fixed on the outline.
                cible = lignes[ligne]
                for piece_id, termes in membres:
                    egalites.append((f"contour {axe}={cible:.4f} {piece_id}", dict(termes), cible))
                continue
            reference_id, reference = membres[0]
            for piece_id, termes in membres[1:]:
                combines = dict(reference)
                for nom, coef in termes.items():
                    combines[nom] = combines.get(nom, 0.0) - coef
                combines = {n: c for n, c in combines.items() if abs(c) > _EPS}
                if not combines:
                    continue
                egalites.append(
                    (
                        f"trame {axe}#{ligne} {reference_id}|{piece_id}",
                        combines,
                        0.0,
                    )
                )
    return tuple(egalites)


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
    egalites = tiling_constraints(grid, poly.index)
    if not egalites:
        return poly
    n_var = len(poly.index)
    lignes: list[int] = []
    colonnes: list[int] = []
    valeurs: list[float] = []
    seconds: list[float] = []
    labels: list[str] = []
    for rang, (libelle, termes, borne) in enumerate(egalites):
        for nom, coef in termes.items():
            lignes.append(rang)
            colonnes.append(poly.index[nom])
            valeurs.append(coef)
        seconds.append(borne)
        labels.append(f"tiling {libelle}")
    a_extra = sparse.coo_matrix((valeurs, (lignes, colonnes)), shape=(len(egalites), n_var)).tocsr()
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
        "Trame": Alias(Grid, "archlux.geom.pavage.Grid"),
        "deduire_trame": Alias(deduce_grid, "archlux.geom.pavage.deduce_grid"),
        "contraintes_pavage": Alias(tiling_constraints, "archlux.geom.pavage.tiling_constraints"),
        "etendre_pavage": Alias(extend_tiling, "archlux.geom.pavage.extend_tiling"),
    },
)
