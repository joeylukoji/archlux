"""Constraint graph -> polytope ``A x <= b``, ``A_eq x = b_eq``, bounds.

Four variables per room: ``<room>.x``, ``<room>.y``, ``<room>.w``, ``<room>.h``.

Minimum areas are **not** produced here: ``w · h >= a`` is nonlinear and
is handled by tangent cuts in :mod:`archlux.lmo.coupes`.

Assembly of A x <= b and sources: ``docs/formules/polytope-separe.md``.
L1 epigraph: ``docs/formules/epigraphe-l1.md``.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

import numpy as np
from scipy import sparse

from archlux._deprecation import Alias, lazy_aliases
from archlux.arrays import VecteurF
from archlux.errors import Infeasible, InvariantViolation
from archlux.geom.graphe import build_graph, transitive_reduction

if TYPE_CHECKING:
    from archlux.geom.graphe import RelativeOrder
    from archlux.types import Context, Plan

__all__ = [
    "FIELDS",
    "Polytope",
    "build_polytope",
    "decision_vector",
    "devectorize",
    "extend_l1_slack",
    "freeze_contacts",
    "vectorize",
]

FIELDS = ("x", "y", "w", "h")
"""The four variables of a room, **in this order**.

The order is a contract: ``lmo`` and ``solve`` assume contiguous columns per room,
and an archived dual trace can only be re-read if the columns have not moved.
"""


@dataclass(frozen=True, slots=True)
class Polytope:
    """The feasible domain, in sparse matrix form.

    Attributes
    ----------
    index : dict of str to int
        ``"living_room.x"`` -> ``12``. The only bridge between business names and columns.
        **Invariant:** the values are exactly ``0..len(index)-1``, with no gap.
        ``lmo`` and ``geom`` rely on it to identify "rank in the list of names sorted by
        column" and "column index"; an index with holes would silently produce
        coefficients placed on the wrong variable.
    origins : tuple of str
        Row ``i`` of ``A`` -> readable label, e.g. ``"separation horizontale a|b"``.
        ``len(origins) == A.shape[0]``: this is what makes the duals pairable.
        The rows of ``A_eq`` are labelled separately, by ``origins_eq``.

    Notes
    -----
    **``origins`` is mandatory, from the very first version.** Without this field, a dual
    price is "the number on row 47": unusable. With it, it is "the load-bearing wall
    on axis 3 costs you 4.1 points". This field cannot be retrofitted
    without rebuilding the module (`ARCHITECTURE.md` §10, `MILESTONE-2.md` §3).

    ``index`` is a mutable ``dict`` in a frozen type: this is the signature imposed by
    `MILESTONE-2.md` §3. Treat it as immutable; nothing in the project modifies it
    after construction.
    """

    A: sparse.csr_matrix
    b: VecteurF
    A_eq: sparse.csr_matrix
    b_eq: VecteurF
    bounds: tuple[tuple[float, float], ...]
    index: dict[str, int]
    origins: tuple[str, ...]
    origins_eq: tuple[str, ...] = ()
    """Label of each row of ``A_eq`` (tiling, fusion, frozen contact). Needed to name
    the constraints of an infeasibility certificate; see :meth:`labels_eq`."""

    def eq_labels(self) -> tuple[str, ...]:
        """One label per row of ``A_eq``; rows added without a label get a generic one."""
        n_rows = self.A_eq.shape[0]
        labels = self.origins_eq[:n_rows]
        return labels + tuple(f"equality {k}" for k in range(len(labels), n_rows))

    def contains(self, x: VecteurF, tol: float = 1e-9) -> bool:
        """Tell whether the point ``x`` satisfies every constraint, within ``tol``.

        **Naive and direct** check, independent of any solver: it is what
        catches a solver error, so it must borrow nothing from it.

        Parameters
        ----------
        x : numpy.ndarray
            Vector of dimension ``len(self.index)``.
        tol : float, optional
            Absolute tolerance on each constraint.

        Returns
        -------
        bool
            ``True`` if the point is feasible: inequalities, equalities and bounds.

        Raises
        ------
        InvariantViolation
            The dimension of ``x`` does not match the polytope.

        Complexity
        ----------
        O(nnz(A)).
        """
        if x.shape != (len(self.index),):
            raise InvariantViolation((f"vector of shape {x.shape}, expected ({len(self.index)},)",))
        if self.A.shape[0] and np.any(self.A @ x > self.b + tol):
            return False
        if self.A_eq.shape[0] and np.any(np.abs(self.A_eq @ x - self.b_eq) > tol):
            return False
        bas = np.array([b[0] for b in self.bounds])
        haut = np.array([b[1] for b in self.bounds])
        return bool(np.all(x >= bas - tol) and np.all(x <= haut + tol))


def freeze_contacts(poly: Polytope, x: VecteurF, *, tol: float = 1e-7) -> Polytope:
    """Turn saturated contacts into equalities, including the outline edges.

    The order polytope is a **relaxation**: ``x_a + w_a <= x_b`` allows a gap,
    and the left / bottom edges are only ``bounds``. After an L1 legalization
    of a tiling, the contacts and the attachment to the outline are saturated. Freezing
    them keeps Frank-Wolfe from opening a hole, while letting the internal partitions
    move. Saturated minimum widths are **not** frozen: a narrow
    room must be able to grow.

    Parameters
    ----------
    poly : Polytope
        System of inequalities from :func:`build_polytope`.
    x : numpy.ndarray
        Reference point, typically the L1 output.
    tol : float, optional
        A contact is saturated if ``b - Ax <= tol``; a bound is if its distance
        to ``x`` is ``<= tol``.

    Returns
    -------
    Polytope
        Same ``index``; saturated rows in ``A_eq``; ``x``/``y`` attached to the
        outline frozen in ``bounds``.
    """
    if x.shape != (len(poly.index),):
        raise InvariantViolation((f"vector of shape {x.shape}, expected ({len(poly.index)},)",))
    noms = {colonne: nom for nom, colonne in poly.index.items()}
    bornes: list[tuple[float, float]] = []
    for colonne, (lo, hi) in enumerate(poly.bounds):
        val = float(x[colonne])
        champ = noms[colonne].rsplit(".", 1)[1]
        bas, haut = lo, hi
        if champ in {"x", "y"}:
            if val - lo <= tol or hi - val <= tol:
                bas = haut = val
        elif hi - val <= tol:
            bas = haut = val
        bornes.append((bas, haut))

    if poly.A.shape[0] == 0:
        return replace(poly, bounds=tuple(bornes))
    marge = poly.b - np.ravel(poly.A @ x)
    saturees = marge <= tol
    if not np.any(saturees):
        return replace(poly, bounds=tuple(bornes))
    libres = ~saturees
    n_var = len(poly.index)
    a_libres = poly.A[libres]
    if a_libres.shape[0] == 0:
        a_libres = sparse.csr_matrix((0, n_var))
    a_saturees = poly.A[saturees]
    b_libres = poly.b[libres]
    b_saturees = poly.b[saturees]
    if poly.A_eq.shape[0]:
        a_eq = sparse.vstack([poly.A_eq, a_saturees], format="csr")
        b_eq = np.concatenate([poly.b_eq, b_saturees])
    else:
        a_eq = a_saturees.tocsr()
        b_eq = b_saturees
    origins = tuple(libelle for libelle, garder in zip(poly.origins, libres, strict=True) if garder)
    frozen = tuple(
        f"contact {libelle}" for libelle, fige in zip(poly.origins, saturees, strict=True) if fige
    )
    return replace(
        poly,
        A=a_libres.tocsr(),
        b=np.asarray(b_libres, dtype=float),
        A_eq=a_eq,
        b_eq=np.asarray(b_eq, dtype=float),
        bounds=tuple(bornes),
        origins=origins,
        origins_eq=poly.eq_labels() + frozen,
    )


def _enveloppe(ctx: Context) -> tuple[float, float, float, float]:
    """Bounding box of the outline: ``(xmin, ymin, xmax, ymax)``."""
    if not ctx.outline:
        raise InvariantViolation(("empty outline: no envelope can be defined",))
    xs = [point[0] for point in ctx.outline]
    ys = [point[1] for point in ctx.outline]
    xmin, xmax, ymin, ymax = min(xs), max(xs), min(ys), max(ys)
    if xmax <= xmin or ymax <= ymin:
        raise InvariantViolation((f"degenerate outline: {xmax - xmin} x {ymax - ymin}",))
    return xmin, ymin, xmax, ymax


def _verifier_enveloppe_admissible(
    min_width: float, largeur: float, hauteur: float, rooms: tuple[str, ...]
) -> None:
    """Refuse an envelope too small for the regulatory minimum width.

    Without this check, ``bounds`` carries an **inverted** interval (``lo > hi``): GLOP
    answers ``ABNORMAL``, which :func:`archlux.lmo.solveur._statut` translates to
    ``"limite"``, and ``api.legalize`` raises ``InvariantViolation`` ("internal bug") on
    what is actually an infeasible program. The Farkas certificate is also
    unusable in this case: the infeasibility comes from no row of ``A``, so
    the auxiliary problem has no solution either.

    Raises
    ------
    Infeasible
        ``largeur_min`` exceeds one of the two dimensions of the envelope. Without rooms,
        there is no ``w``/``h`` variable and so nothing to refuse.
    """
    if not rooms:
        return
    conflits = tuple(
        f"minimum width {min_width} m > {libelle} of the envelope ({etendue} m)"
        for libelle, etendue in (("width", largeur), ("height", hauteur))
        if min_width > etendue
    )
    if conflits:
        raise Infeasible(farkas_certificate=None, origins=conflits)


def build_polytope(ordre: RelativeOrder, ctx: Context) -> Polytope:
    """Assemble the linear system describing every valid plan of this order.

    Constraints produced:

    - horizontal separation ``x_a + w_a - x_b <= 0`` per edge of ``g.horizontal``;
    - vertical separation ``y_a + h_a - y_b <= 0``;
    - load-bearing walls: one row per room and wall, keeping the room on its side
      (``ordre.wall_sides``, see :class:`archlux.geom.graphe.WallSide`);
    - outline ``x_i + w_i <= x_max``, ``y_i + h_i <= y_max``;
    - bottom and left edges, and minimum widths ``w_i >= l_min``, **via ``bounds``**.

    The graph is **transitively reduced** before assembly. The removed edges
    remain implied: from ``x_a + w_a <= x_b`` and ``x_b + w_b <= x_c``, with ``w_b >= 0``,
    follows ``x_a + w_a <= x_c``.

    Parameters
    ----------
    ordre : RelativeOrder
        Partial order, typically from :func:`archlux.geom.graphe.deduce_order`.
    ctx : Context
        Outline, load-bearing structure and regulation.

    Returns
    -------
    Polytope
        Complete system, ``index`` and ``origins`` filled in.

    Raises
    ------
    InconsistentOrder, MissingSeparation
        Propagated from :func:`archlux.geom.graphe.build_graph`.
    InvariantViolation
        Empty or degenerate outline.
    Infeasible
        ``regulation.min_width`` exceeds a dimension of the envelope: no room
        fits in it. Detected here rather than by the LP, which could not tell it apart
        from a numerical error (see :func:`_verifier_enveloppe_admissible`).

    Guarantees
    ----------
    - Geometric: **exact**. Every point of the polytope is a plan free of overlap,
      for a fixed relative order. The converse (every valid plan of this order is in the
      polytope) is checked by a property test on exact tilings.
    - No performance guarantee: this module ignores light.

    Complexity
    ----------
    O(n²) constraints at worst, O(n) after transitive reduction in practice.
    Budget: < 5 ms for 15 rooms (`ARCHITECTURE.md` §9).
    """
    xmin, ymin, xmax, ymax = _enveloppe(ctx)
    graphe = transitive_reduction(build_graph(ordre, ordre.rooms))

    index = _decision_index(ordre.rooms)
    n_var = len(index)

    lignes: list[int] = []
    colonnes: list[int] = []
    valeurs: list[float] = []
    second_membre: list[float] = []
    origins: list[str] = []

    def _ajouter(termes: dict[str, float], borne: float, origin: str) -> None:
        """Add a row ``A x <= b`` and its origin label."""
        ligne = len(origins)
        for nom, coefficient in termes.items():
            lignes.append(ligne)
            colonnes.append(index[nom])
            valeurs.append(coefficient)
        second_membre.append(borne)
        origins.append(origin)

    axes = (("horizontal", "horizontale", "x", "w"), ("vertical", "verticale", "y", "h"))
    for axe, libelle, position, taille in axes:
        for a, b in sorted(getattr(graphe, axe).edges):
            _ajouter(
                {f"{a}.{position}": 1.0, f"{a}.{taille}": 1.0, f"{b}.{position}": -1.0},
                0.0,
                f"separation {libelle} {a}|{b}",
            )

    for piece in ordre.rooms:
        _ajouter({f"{piece}.x": 1.0, f"{piece}.w": 1.0}, xmax, f"contour droit {piece}")
        _ajouter({f"{piece}.y": 1.0, f"{piece}.h": 1.0}, ymax, f"contour haut {piece}")

    # Load-bearing walls are fixed obstacles: each room keeps the side it was on.
    wall_rows: dict[str, tuple[dict[str, float], float]] = {
        "left": ({"x": 1.0, "w": 1.0}, 1.0),  # x + w <= bound
        "right": ({"x": -1.0}, -1.0),  # -x <= -bound
        "below": ({"y": 1.0, "h": 1.0}, 1.0),  # y + h <= bound
        "above": ({"y": -1.0}, -1.0),  # -y <= -bound
    }
    for side in ordre.wall_sides:
        terms, sign = wall_rows[side.side]
        _ajouter(
            {f"{side.room}.{field}": coefficient for field, coefficient in terms.items()},
            sign * side.bound,
            f"load-bearing {side.wall}: {side.room} {side.side} of {side.bound:g}",
        )

    matrice = sparse.coo_matrix((valeurs, (lignes, colonnes)), shape=(len(origins), n_var)).tocsr()

    min_width = ctx.regulation.min_width
    _verifier_enveloppe_admissible(min_width, xmax - xmin, ymax - ymin, ordre.rooms)
    bornes_par_champ = {
        "x": (xmin, xmax),
        "y": (ymin, ymax),
        "w": (min_width, xmax - xmin),
        "h": (min_width, ymax - ymin),
    }
    bornes = tuple(bornes_par_champ[champ] for _ in ordre.rooms for champ in FIELDS)

    return Polytope(
        A=matrice,
        b=np.array(second_membre, dtype=float),
        # Empty but well shaped. Load-bearing walls are inequality rows (ordre.wall_sides),
        # not equalities: a room only has to stay on its side of a wall.
        A_eq=sparse.csr_matrix((0, n_var)),
        b_eq=np.zeros(0, dtype=float),
        bounds=bornes,
        index=index,
        origins=tuple(origins),
    )


def _decision_index(room_ids: tuple[str, ...]) -> dict[str, int]:
    """Columns ``<room>.<field>``: rooms in the given order, fields in :data:`FIELDS` order."""
    return {
        f"{room}.{field}": 4 * rank + offset
        for rank, room in enumerate(room_ids)
        for offset, field in enumerate(FIELDS)
    }


def decision_vector(plan: Plan) -> VecteurF:
    """Decision vector of ``plan``, without building a polytope (AUDIT.md M12).

    Rooms sorted by identifier, then ``x, y, w, h``: the column order of
    :func:`build_polytope` (whose relative order lists rooms sorted), hence the
    vector a surrogate receives from ``solve``. Use it to evaluate a surrogate or an
    oracle on a plan.

    Parameters
    ----------
    plan : Plan
        Any plan; its rooms need distinct identifiers.

    Returns
    -------
    numpy.ndarray
        Vector of dimension ``4 * len(plan.rooms)``.

    Examples
    --------
    >>> from archlux.types import Plan, Room
    >>> plan = Plan(
    ...     rooms=(
    ...         Room(id="b", type="x", x=6, y=0, w=6, h=9),
    ...         Room(id="a", type="x", x=0, y=0, w=6, h=9),
    ...     )
    ... )
    >>> decision_vector(plan).tolist()
    [0.0, 0.0, 6.0, 9.0, 6.0, 0.0, 6.0, 9.0]
    """
    return vectorize(plan, _decision_index(tuple(sorted(room.id for room in plan.rooms))))


def vectorize(plan: Plan, index: dict[str, int]) -> VecteurF:
    """Project a plan onto the decision vector ordered by ``index``.

    Parameters
    ----------
    plan : Plan
        Plan to encode.
    index : dict of str to int
        Lookup table from a :class:`Polytope`.

    Returns
    -------
    numpy.ndarray
        Vector of dimension ``len(index)``.

    Raises
    ------
    InvariantViolation
        A room expected by ``index`` is missing from the plan. This is an internal bug:
        the polytope and the plan must come from the same order.

    Complexity
    ----------
    O(n).
    """
    point = np.zeros(len(index), dtype=float)
    par_id = {piece.id: piece for piece in plan.rooms}
    for nom, colonne in index.items():
        piece_id, champ = nom.rsplit(".", 1)
        piece = par_id.get(piece_id)
        if piece is None:
            raise InvariantViolation((f"room {piece_id} missing from the plan to vectorize",))
        point[colonne] = getattr(piece, champ)
    return point


def devectorize(x: VecteurF, template: Plan, index: dict[str, int]) -> Plan:
    """Rebuild a plan from a solution vector.

    ``template`` provides everything the vector does not carry: walls, openings, outline.
    Since openings are relative to their wall, they follow the move without
    adjustment; this is exactly the reason for the invariant of `ARCHITECTURE.md` §6.

    Parameters
    ----------
    x : numpy.ndarray
        LP solution.
    template : Plan
        Original plan, **not mutated**: a new plan is returned.
    index : dict of str to int
        Lookup table of the polytope.

    Returns
    -------
    Plan
        New plan, **without certificate**: ``api.legalize`` attaches it, and
        only after an independent exact verification.

    Raises
    ------
    InvariantViolation
        Unexpected dimension, or a room of the template missing from the polytope. Leaving
        a room not updated would produce a wrong plan that ``certify`` would reject later,
        with a diagnostic unrelated to the cause.

    Complexity
    ----------
    O(n).
    """
    if x.shape != (len(index),):
        raise InvariantViolation((f"vector of shape {x.shape}, expected ({len(index)},)",))
    manquantes = sorted(piece.id for piece in template.rooms if f"{piece.id}.x" not in index)
    if manquantes:
        raise InvariantViolation((f"rooms missing from the polytope: {', '.join(manquantes)}",))
    rooms = tuple(
        replace(
            piece,
            x=float(x[index[f"{piece.id}.x"]]),
            y=float(x[index[f"{piece.id}.y"]]),
            w=float(x[index[f"{piece.id}.w"]]),
            h=float(x[index[f"{piece.id}.h"]]),
        )
        for piece in template.rooms
    )
    return replace(template, rooms=rooms, certificate=None)


def extend_l1_slack(poly: Polytope, x_ref: VecteurF) -> Polytope:
    r"""Epigraph of :math:`\\|x - \\hat{x}\\|_1`: slack variables and two inequalities.

    Formula
    -------
    :math:`\\min_x \\sum_i |x_i - \\hat{x}_i|` is not linear. The epigraph
    (Bertsimas & Tsitsiklis, *Introduction to Linear Optimization*, Athena
    Scientific, 1997, §1.3) introduces :math:`e_i \\ge 0` such that

    .. math::

        e_i \\ge x_i - \\hat{x}_i, \\qquad e_i \\ge \\hat{x}_i - x_i,

    that is, in the :math:`A x \\le b` form of the polytope:

    .. math::

        x_i - e_i \\le \\hat{x}_i, \\qquad -x_i - e_i \\le -\\hat{x}_i.

    The objective becomes :math:`\\min \\sum_i e_i`, linear. Omitting one of the two
    families leaves :math:`e_i` free on one side and produces a huge apparent
    displacement (`MILESTONE-2.md` §10).

    The original columns keep their indices ``0..n-1``; the slacks occupy
    ``n..2n-1`` under the name ``e.<variable>``.

    Parameters
    ----------
    poly : Polytope
        Geometric domain, n variables.
    x_ref : numpy.ndarray
        Vectorized proposed plan, dimension n.

    Returns
    -------
    Polytope
        Domain of dimension ``2n``.

    Raises
    ------
    InvariantViolation
        Incompatible dimension of ``x_ref``.

    Notes
    -----
    Derivation and use cases: ``docs/formules/epigraphe-l1.md``.
    """
    n_var = len(poly.index)
    if x_ref.shape != (n_var,):
        raise InvariantViolation((f"reference of shape {x_ref.shape}, expected ({n_var},)",))
    noms = sorted(poly.index, key=lambda nom: poly.index[nom])
    index = dict(poly.index)
    for rang, nom in enumerate(noms):
        index[f"e.{nom}"] = n_var + rang

    n_lignes = poly.A.shape[0]
    a_pad = (
        sparse.hstack([poly.A, sparse.csr_matrix((n_lignes, n_var))]).tocsr()
        if n_lignes
        else sparse.csr_matrix((0, 2 * n_var))
    )
    a_eq_pad = (
        sparse.hstack([poly.A_eq, sparse.csr_matrix((poly.A_eq.shape[0], n_var))]).tocsr()
        if poly.A_eq.shape[0]
        else sparse.csr_matrix((0, 2 * n_var))
    )

    lignes: list[int] = []
    colonnes: list[int] = []
    valeurs: list[float] = []
    second: list[float] = []
    origines_extra: list[str] = []
    for rang, nom in enumerate(noms):
        ligne = 2 * rang
        lignes.extend((ligne, ligne))
        colonnes.extend((rang, n_var + rang))
        valeurs.extend((1.0, -1.0))
        second.append(float(x_ref[rang]))
        origines_extra.append(f"ecart plus {nom}")
        ligne = 2 * rang + 1
        lignes.extend((ligne, ligne))
        colonnes.extend((rang, n_var + rang))
        valeurs.extend((-1.0, -1.0))
        second.append(float(-x_ref[rang]))
        origines_extra.append(f"ecart moins {nom}")

    extra = sparse.coo_matrix((valeurs, (lignes, colonnes)), shape=(2 * n_var, 2 * n_var)).tocsr()
    matrice = sparse.vstack([a_pad, extra]).tocsr() if n_lignes else extra
    inf = float("inf")
    return Polytope(
        A=matrice,
        b=np.concatenate([poly.b, np.asarray(second, dtype=float)]),
        A_eq=a_eq_pad,
        b_eq=poly.b_eq,
        bounds=tuple(poly.bounds) + tuple((0.0, inf) for _ in range(n_var)),
        index=index,
        origins=tuple(poly.origins) + tuple(origines_extra),
        origins_eq=poly.eq_labels(),
    )


__getattr__ = lazy_aliases(
    __name__,
    {
        "construire_polytope": Alias(build_polytope, "archlux.geom.polytope.build_polytope"),
        "figer_contacts": Alias(freeze_contacts, "archlux.geom.polytope.freeze_contacts"),
        "vectoriser": Alias(vectorize, "archlux.geom.polytope.vectorize"),
        "devectoriser": Alias(devectorize, "archlux.geom.polytope.devectorize"),
        "etendre_ecarts_l1": Alias(extend_l1_slack, "archlux.geom.polytope.extend_l1_slack"),
        "CHAMPS": Alias(FIELDS, "archlux.geom.polytope.FIELDS"),
    },
)
