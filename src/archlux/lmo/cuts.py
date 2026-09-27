r"""Tangent cuts for the minimum-area constraints.

Formula
=======
The area of a rectangle is the product :math:`a(w,h) = w h`. The regulatory
constraint :math:`w h \\ge a_{\\min}` is **not linear**. GLOP can only handle it
through a linear approximation.

Convexity
---------
On :math:`\\mathbb{R}_{>0}^2`, :math:`g(w,h) = \\log w + \\log h` is concave
(Boyd & Vandenberghe, *Convex Optimization*, Cambridge University Press, 2004,
§3.1.5, composition with the log). Its superlevel sets

.. math::

    K = \\{(w,h) : w>0,\\ h>0,\\ w h \\ge a_{\\min}\\}
      = \\{ g \\ge \\log a_{\\min} \\}

are therefore **convex** (ibid., §3.1.6).

Tangent
-------
At the contact point :math:`(w_0,h_0)` of the hyperbola :math:`w_0 h_0 = a_{\\min}`,
:math:`\\nabla g = (1/w_0,\\ 1/h_0)` and the supporting half-space containing
:math:`K` is written

.. math::

    \\frac{w-w_0}{w_0} + \\frac{h-h_0}{h_0} \\ge 0
    \\quad\\Longleftrightarrow\\quad
    h_0 w + w_0 h \\ge 2 a_{\\min}.

This is also the AM-GM inequality (Hardy, Littlewood, Polya, *Inequalities*, 2nd ed.,
Cambridge, 1952, th. 16): :math:`(w/w_0 + h/h_0)/2 \\ge \\sqrt{wh/(w_0 h_0)}`, which is
:math:`\\ge 1` as soon as :math:`wh \\ge a_{\\min}`.

If the current point violates the constraint, it is first **projected** onto the
hyperbola while keeping the aspect ratio
:math:`(w_0,h_0) \\leftarrow \\sqrt{a_{\\min}/(wh)}\\,(w,h)`, without which a
tangent written at a point inside the infeasible region **excludes** feasible points
(same ratio, product :math:`= a_{\\min}`).

The Kelley loop (Kelley, J. E., *The cutting-plane method for solving convex
programs*, SIAM J. 8, 1960) adds these tangents until satisfaction or
``MAX_CUTS_PER_ROOM``.

Step-by-step derivation, use cases and DOI: ``docs/formules/coupes-surface.md``.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from itertools import pairwise
from math import sqrt
from typing import TYPE_CHECKING

import numpy as np
from scipy import sparse

from archlux._deprecation import renamed_parameters
from archlux.arrays import VecteurF
from archlux.errors import InvariantViolation
from archlux.lmo.solveur import solve
from archlux.tolerances import AREA_PROOF_M2, AREA_TARGET_MARGIN_M2, SNAP_M

if TYPE_CHECKING:
    from archlux.geom.polytope import Polytope
    from archlux.lmo.solveur import LPSolution
    from archlux.types import Context, Room

__all__ = [
    "INNER_AREA_SPREAD",
    "MAX_CUTS_PER_ROOM",
    "Cut",
    "area_cut",
    "inner_area_constraints",
    "solve_with_areas",
    "violated_areas",
]

MAX_CUTS_PER_ROOM = 10
"""Beyond it, ``log.warning("coupe.limite", piece=...)`` and stop for that room."""

_TOLERANCE_AIRE = AREA_PROOF_M2
"""Acceptance: a room is short of its minimum area when ``w h + tol < a_min``. Equal to
the proof tolerance, so that the loop never stops on a plan the proof then rejects
(the "10.35 m² < 10.35 m²" refusals). For a room found in deficit, the cuts and the
bound tightening aim at ``_target``, slightly above the minimum, so that LP noise cannot
leave it below; rooms that meet their minimum are never pushed by the margin."""


def _target(min_area: float, margin: float = AREA_TARGET_MARGIN_M2) -> float:
    """Area the cuts aim at: the minimum plus a margin larger than the LP noise."""
    return min_area + margin


_TOLERANCE_BORNE = 1e-12
"""Tolerance for membership in the bounds box, in metres."""
_TOLERANCE_LONGUEUR = 1e-6
"""Tolerance for comparing a length to a bound, in metres.

Distinct from :data:`_TOLERANCE_AIRE`: one is in square metres, the other in metres.
Conflating them would make any revision of one silently dependent on the other.
"""


def _points_appui_hyperbole(
    min_area: float, w_min: float, w_max: float, h_min: float, h_max: float
) -> tuple[tuple[float, float], ...]:
    """Points of the hyperbola ``wh = a_min`` within the bounds box.

    The tangents at these points form the initial outer approximation (Kelley, 1960):
    the ends of the feasible arc and the square, if it fits.
    """
    points: list[tuple[float, float]] = []
    cote = sqrt(min_area)

    def _in_box(largeur: float, hauteur: float) -> bool:
        """Say whether the pair ``(largeur, hauteur)`` fits within the LP bounds."""
        return (
            w_min - _TOLERANCE_BORNE <= largeur <= w_max + _TOLERANCE_BORNE
            and h_min - _TOLERANCE_BORNE <= hauteur <= h_max + _TOLERANCE_BORNE
        )

    if _in_box(cote, cote):
        points.append((cote, cote))
    if w_min > 0.0 and _in_box(w_min, min_area / w_min):
        points.append((w_min, min_area / w_min))
    if h_min > 0.0 and _in_box(min_area / h_min, h_min):
        points.append((min_area / h_min, h_min))
    uniques: list[tuple[float, float]] = []
    for candidat in points:
        if not any(
            abs(candidat[0] - vu[0]) < _TOLERANCE_BORNE
            and abs(candidat[1] - vu[1]) < _TOLERANCE_BORNE
            for vu in uniques
        ):
            uniques.append(candidat)
    return tuple(uniques)


def _minimum_areas(
    ctx: Context, rooms: tuple[Room, ...], minima: Mapping[str, float] | None
) -> dict[str, float]:
    """Minimum area of each room: ``minima`` if it names the room, else its type's."""
    overrides = minima or {}
    return {
        piece.id: overrides.get(piece.id, ctx.regulation.min_area(piece.type)) for piece in rooms
    }


def _coupes_initiales(
    poly: Polytope, need: Mapping[str, float], rooms: tuple[Room, ...]
) -> list[Cut]:
    """Envelope tangents, before the first solve."""
    cuts: list[Cut] = []
    for piece in rooms:
        seuil = need[piece.id]
        if seuil <= 0.0:
            continue
        w_min, w_max = poly.bounds[poly.index[f"{piece.id}.w"]]
        h_min, h_max = poly.bounds[poly.index[f"{piece.id}.h"]]
        # Exact minimum here, no margin: these outer tangents are satisfied by any valid
        # plan, and a margin would force rooms that sit exactly at their minimum to grow.
        for largeur, hauteur in _points_appui_hyperbole(seuil, w_min, w_max, h_min, h_max):
            cuts.append(area_cut(largeur, hauteur, seuil, piece=piece.id))
    return cuts


@dataclass(frozen=True, slots=True)
class Cut:
    """Linear inequality ``Σ coefficients[v]·v ≥ lower_bound`` added to the polytope.

    Attributes
    ----------
    coefficients : tuple of (str, float)
        Pairs ``(variable name, coefficient)``, sorted.
    lower_bound : float
        Right-hand side of the inequality.
    origin : str
        Label fed back into the dual diagnosis.
    """

    coefficients: tuple[tuple[str, float], ...]
    lower_bound: float
    origin: str

    def satisfied(self, w: float, h: float, tol: float = 1e-9) -> bool:
        """Say whether the pair ``(w, h)`` satisfies the area cut.

        Parameters
        ----------
        w, h : float
            Width and height tested, in metres.
        tol : float, optional
            Additive tolerance on the inequality.

        Returns
        -------
        bool
            ``True`` if ``Σ coef·variable ≥ lower_bound - tol``.
        """
        total = 0.0
        for nom, coefficient in self.coefficients:
            champ = nom.rsplit(".", 1)[-1]
            if champ == "w":
                total += coefficient * w
            elif champ == "h":
                total += coefficient * h
        return bool(total + tol >= self.lower_bound)


@renamed_parameters({"a_min": "min_area"})
def area_cut(w0: float, h0: float, min_area: float, *, piece: str = "") -> Cut:
    """Tangent to the hyperbola ``w h = a_min`` at the projected point of ``(w₀, h₀)``.

    Parameters
    ----------
    w0, h0 : float
        Linearisation point, strictly positive (current solution).
    min_area : float
        Minimum area, in square metres, strictly positive.
    piece : str, optional
        Room identifier, prefix of the variables ``<id>.w`` / ``<id>.h``.

    Returns
    -------
    Cut
        ``h_★ w + w_★ h ≥ 2 a_min`` at the point ``(w_★, h_★)`` of the hyperbola.

    Raises
    ------
    InvariantViolation
        Point that is not strictly positive, or ``min_area`` not strictly positive.

    Guarantees
    ----------
    - Geometric: **exact**. No ``(w,h)`` with product ``≥ a_min`` is excluded.

    Notes
    -----
    Formula and sources: ``docs/formules/coupes-surface.md``.
    """
    if w0 <= 0.0 or h0 <= 0.0:
        raise InvariantViolation((f"linearisation point not strictly positive: {(w0, h0)}",))
    if min_area <= 0.0:
        raise InvariantViolation((f"minimum area not strictly positive: {min_area}",))
    produit = w0 * h0
    scale = sqrt(min_area / produit)
    w_star, h_star = w0 * scale, h0 * scale
    nom_w = f"{piece}.w" if piece else "w"
    nom_h = f"{piece}.h" if piece else "h"
    coefficients = tuple(sorted(((nom_w, h_star), (nom_h, w_star))))
    origin = f"surface {piece}" if piece else "surface"
    return Cut(coefficients=coefficients, lower_bound=2.0 * min_area, origin=origin)


@renamed_parameters({"pieces": "rooms"})
def violated_areas(
    x: VecteurF | Sequence[float],
    poly: Polytope,
    ctx: Context,
    *,
    rooms: tuple[Room, ...],
    minima: Mapping[str, float] | None = None,
) -> tuple[str, ...]:
    """List the rooms whose ``w h`` is strictly below ``min_area``.

    Parameters
    ----------
    x : numpy.ndarray
        Current LP solution.
    poly : Polytope
        Provides ``index``.
    ctx : Context
        Provides the regulation's minimum areas.
    rooms : tuple of Room
        Identifiers and types — the polytope does not carry the programme.
    minima : mapping of str to float, optional
        Minimum area per room id, overriding the type's (the sub-rectangles of a fused
        room, :func:`archlux.geom.rectilineaire.minimum_area_shares`).

    Returns
    -------
    tuple of str
        Sorted identifiers.
    """
    return _short_of_area(x, poly, _minimum_areas(ctx, rooms, minima), rooms)


def _short_of_area(
    x: VecteurF | Sequence[float],
    poly: Polytope,
    need: Mapping[str, float],
    rooms: tuple[Room, ...],
) -> tuple[str, ...]:
    """Rooms whose ``w h`` is strictly below ``need``, sorted."""
    vecteur = np.asarray(x, dtype=float)
    violees: list[str] = []
    for piece in rooms:
        seuil = need[piece.id]
        if seuil <= 0.0:
            continue
        largeur = float(vecteur[poly.index[f"{piece.id}.w"]])
        hauteur = float(vecteur[poly.index[f"{piece.id}.h"]])
        if largeur * hauteur + _TOLERANCE_AIRE < seuil:
            violees.append(piece.id)
    return tuple(sorted(violees))


def _target_on_hyperbola(
    largeur: float,
    hauteur: float,
    min_area: float,
    w_min: float,
    w_max: float,
    h_min: float,
    h_max: float,
) -> tuple[float, float] | None:
    """Point of ``wh = a_min`` in the box, same aspect ratio if possible.

    If the ray leaves through an edge, slide along the arc to the hyperbola–box
    intersection (a real vertex of ``K``, reachable by the simplex).
    """
    if largeur <= 0.0 or hauteur <= 0.0 or min_area <= 0.0:
        return None
    if largeur * hauteur + _TOLERANCE_AIRE >= min_area:
        return None
    facteur = sqrt(min_area / (largeur * hauteur))
    w_star, h_star = largeur * facteur, hauteur * facteur
    w_star = min(max(w_star, w_min), w_max)
    h_star = min_area / w_star if w_star > 0.0 else h_max
    if h_min - _TOLERANCE_LONGUEUR <= h_star <= h_max + _TOLERANCE_LONGUEUR:
        return w_star, min(max(h_star, h_min), h_max)
    h_star = min(max(hauteur * facteur, h_min), h_max)
    w_star = min_area / h_star if h_star > 0.0 else w_max
    if w_min - _TOLERANCE_LONGUEUR <= w_star <= w_max + _TOLERANCE_LONGUEUR:
        return min(max(w_star, w_min), w_max), h_star
    return None


def _resserrer_bornes(
    poly: Polytope,
    x: VecteurF,
    need: Mapping[str, float],
    rooms: tuple[Room, ...],
    *,
    margin: float = AREA_TARGET_MARGIN_M2,
) -> Polytope:
    """Raise the lower bounds of ``w,h`` up to the current hyperbola.

    The simplex only returns vertices of a polyhedron. On ``{wh ≥ a}``, strictly
    convex, the optimum (AM-GM: minimise ``w+h``) is never a vertex of a finite
    approximation: the vertices oscillate on a chord, product ``a − δ²``. Imposing
    ``w ≥ w★``, ``h ≥ h★`` forces the next vertex to respect the area, and lets GLOP
    readjust ``x, y`` (Kelley, 1960, plus bound tightening).
    """
    bornes = list(poly.bounds)
    change = False
    for piece in rooms:
        seuil = need[piece.id]
        if seuil <= 0.0:
            continue
        idx_w = poly.index[f"{piece.id}.w"]
        idx_h = poly.index[f"{piece.id}.h"]
        if float(x[idx_w]) * float(x[idx_h]) + _TOLERANCE_AIRE >= seuil:
            continue  # not short of its minimum: the margin only serves rooms in deficit
        w_min, w_max = bornes[idx_w]
        h_min, h_max = bornes[idx_h]
        cible = _target_on_hyperbola(
            float(x[idx_w]), float(x[idx_h]), _target(seuil, margin), w_min, w_max, h_min, h_max
        )
        if cible is None:
            continue
        w_star, h_star = cible
        if w_star > w_min + _TOLERANCE_LONGUEUR:
            bornes[idx_w] = (w_star, w_max)
            change = True
        if h_star > h_min + _TOLERANCE_LONGUEUR:
            bornes[idx_h] = (h_star, h_max)
            change = True
    return replace(poly, bounds=tuple(bornes)) if change else poly


def _identifiants_a_couper(
    x: VecteurF,
    poly: Polytope,
    need: Mapping[str, float],
    rooms: tuple[Room, ...],
    comptes: Counter[str],
) -> list[str]:
    """Rooms still below ``min_area`` and under the cut cap."""
    restantes: list[str] = []
    for identifiant in _short_of_area(x, poly, need, rooms):
        if comptes[identifiant] >= MAX_CUTS_PER_ROOM:
            # Lazy: structlog costs up to 0.4 s at import and this path is rare.
            import structlog

            structlog.get_logger("archlux.lmo.coupes").warning("coupe.limite", piece=identifiant)
            continue
        restantes.append(identifiant)
    return restantes


def _empiler_tangentes(
    restantes: list[str],
    x: VecteurF,
    poly: Polytope,
    need: Mapping[str, float],
    cuts: list[Cut],
    comptes: Counter[str],
    *,
    margin: float = AREA_TARGET_MARGIN_M2,
) -> None:
    """Add one Kelley tangent per remaining room (Kelley, 1960)."""
    for identifiant in restantes:
        largeur = float(x[poly.index[f"{identifiant}.w"]])
        hauteur = float(x[poly.index[f"{identifiant}.h"]])
        cuts.append(
            area_cut(largeur, hauteur, _target(need[identifiant], margin), piece=identifiant)
        )
        comptes[identifiant] += 1


@renamed_parameters({"pieces": "rooms", "depart": "start", "duaux": "duals"})
def solve_with_areas(
    poly: Polytope,
    c: VecteurF,
    ctx: Context,
    rooms: tuple[Room, ...],
    *,
    start: VecteurF | None = None,
    duals: bool = False,
    minima: Mapping[str, float] | None = None,
) -> LPSolution:
    """Solve the LP, adding area tangents until satisfaction.

    Parameters
    ----------
    poly : Polytope
        Linear domain (separations, outline, possibly L1 slacks).
    c : numpy.ndarray
        Objective, dimension ``len(poly.index)``.
    ctx : Context
        Area regulation.
    rooms : tuple of Room
        Programme, to give each identifier its type.
    start : numpy.ndarray or None, optional
        Warm start of the first call.
    duals : bool, optional
        Extract the duals of the last LP.
    minima : mapping of str to float, optional
        Minimum area per room id, overriding the type's. The sub-rectangles of a fused
        room get their share of the room's minimum
        (:func:`archlux.geom.rectilineaire.minimum_area_shares`).

    Returns
    -------
    LPSolution
        Last solution. Status unchanged if the original LP is infeasible.

    Warnings
    --------
    ``status == "optimal"`` **does not guarantee** ``w·h ≥ a_min``:

    - the loop hands back as soon as a room reaches ``MAX_CUTS_PER_ROOM``, with the
      last solution as is. This is a termination cap, not a proof;
    - :func:`_resserrer_bornes` **restricts** the domain (``w ≥ w★`` and ``h ≥ h★``
      simultaneously, whereas ``{wh ≥ a_min}`` allows trading one for the other). The
      optimum returned is therefore that of the tightened domain, not of the exact
      domain, and it may be strictly worse.

    In both cases, only :func:`archlux.certify.proof.verify_exactly` decides.
    The duals returned are those of the rows of ``A``, unchanged by the tightening: the
    pressure exerted by the minimum areas does not appear in them.

    Notes
    -----
    Derivation, sources and use cases: ``docs/formules/coupes-surface.md``.
    """
    need = _minimum_areas(ctx, rooms, minima)
    first = _solve_with_area_cuts(poly, c, need, rooms, start, duals, AREA_TARGET_MARGIN_M2)
    if _meets_areas(first, poly, need, rooms):
        return first
    # The margin needs room the plan may not have (minimum areas that fill the outline
    # exactly, review of batch 1.5): aim at the exact minimum before giving up.
    exact = _solve_with_area_cuts(poly, c, need, rooms, start, duals, 0.0)
    if _meets_areas(exact, poly, need, rooms) or first.status != "optimal":
        return exact
    return first


def _meets_areas(
    solution: LPSolution, poly: Polytope, need: Mapping[str, float], rooms: tuple[Room, ...]
) -> bool:
    """An optimal point inside the polytope (up to SNAP_M) with no area in deficit."""
    return (
        solution.status == "optimal"
        and not _short_of_area(solution.x, poly, need, rooms)
        and poly.contains(solution.x, tol=SNAP_M)
    )


def _solve_with_area_cuts(
    poly: Polytope,
    c: VecteurF,
    need: Mapping[str, float],
    rooms: tuple[Room, ...],
    start: VecteurF | None,
    duals: bool,
    margin: float,
) -> LPSolution:
    """The Kelley loop of :func:`solve_with_areas`, aiming ``margin`` above minima."""
    domaine = poly
    cuts: list[Cut] = _coupes_initiales(domaine, need, rooms)
    comptes: Counter[str] = Counter()
    courant = start
    while True:
        solution = solve(domaine, c, start=courant, cuts=cuts or None, duals=duals)
        if solution.status != "optimal":
            if domaine is not poly:
                # Tightened bounds are not an outer approximation: an infeasible verdict
                # on them says nothing about the original problem (AUDIT.md §5.2). Solve
                # the original domain, so that an infeasibility certificate, if any, is
                # about the real system; a feasible answer goes on to the exact proof.
                return solve(poly, c, start=courant, cuts=cuts or None, duals=duals)
            return solution
        if not _short_of_area(solution.x, domaine, need, rooms):
            return solution
        resserre = _resserrer_bornes(domaine, solution.x, need, rooms, margin=margin)
        if resserre is not domaine:
            affine = solve(resserre, c, start=solution.x, cuts=cuts or None, duals=duals)
            if affine.status == "optimal":
                if not _short_of_area(affine.x, resserre, need, rooms):
                    return affine
                domaine = resserre
                solution = affine
        restantes = _identifiants_a_couper(solution.x, domaine, need, rooms, comptes)
        if not restantes:
            return solution
        _empiler_tangentes(restantes, solution.x, domaine, need, cuts, comptes, margin=margin)
        courant = solution.x


INNER_AREA_SPREAD: tuple[float, ...] = tuple(1.1**k for k in range(-24, 25))
"""Widths, relative to the start, of the hyperbola points joined by chords.

A geometric sequence of ratio 1.1, from about 0.10 to 9.85 times the start width: every
chord asks for the same extra area, (1.1 - 1)^2 / (4 * 1.1) = 0.23 %. Measured on the
200 benchmark scenarios against a 235-node reference (ratio 1.02): median 0.9985 of the
reference gain, at least 0.95 of it in 96 % of scenarios, for +4 ms median; the coarser
1.25-ratio grid reached 0.95 in only 81 % of them."""


@renamed_parameters({"pieces": "rooms"})
def inner_area_constraints(
    poly: Polytope,
    x: VecteurF,
    ctx: Context,
    rooms: tuple[Room, ...],
    *,
    spread: tuple[float, ...] = INNER_AREA_SPREAD,
    minima: Mapping[str, float] | None = None,
) -> Polytope:
    """Add an **inner** linear approximation of every minimum area ``w h >= a``.

    Tangent cuts (:func:`area_cut`) are an *outer* approximation: their vertices
    can lie below the hyperbola, so a convex combination of a valid point and such a
    vertex can break the minimum area. That is how Frank-Wolfe went below ``min_area``
    (AUDIT.md §3 n°6). This function does the opposite: every point it keeps satisfies
    the minimum area, and so does every convex combination of such points.

    For each room with ``a > 0`` and start dimensions ``(w0, h0)``, take the nodes
    ``w_k = f_k w0`` (``f_k`` in ``spread``, always including 1) and ``h_k = a / w_k`` on
    the hyperbola. Nodes are not filtered by the variable bounds: the region is
    intersected with them anyway, and filtering would freeze a room whose height a
    contact has fixed (it would keep ``w >= w0`` instead of ``w >= a / h0``). Keep

    - ``w >= w_first`` and ``h >= a / w_last`` (bounds), and
    - ``h >= h_k + s_k (w - w_k)`` for each chord ``[w_k, w_{k+1}]``, slope ``s_k``
      (rows ``s_k w - h <= s_k w_k - h_k``).

    Soundness. ``h = a / w`` is convex, so it lies below each of its chords: on
    ``[w_first, w_last]`` the piecewise-linear interpolant is at least ``a / w``. That
    interpolant is itself convex, hence the maximum of its (extended) chords, so the
    rows above describe exactly its epigraph. Beyond ``w_last``, ``h >= a / w_last >
    a / w``. The region is convex and included in ``{w h >= a}``.

    The start stays admissible: ``w0`` is a node, so the rows only require
    ``h0 >= a / w0``. If the start sits below ``a`` by less than the proof tolerance
    (``tolerances.AREA_PROOF_M2``), ``a`` is lowered to ``w0 h0`` for that room rather
    than excluding the start; any larger deficit is refused.

    Compared with a single corner ``w >= w0, h >= h0``, the chords let a room trade
    width for height within ``spread`` instead of freezing its shape. Each chord of
    node ratio ``r`` asks for at most ``(r - 1)^2 / (4 r)`` extra area, at its midpoint.

    Parameters
    ----------
    poly : Polytope
        Domain to restrict.
    x : numpy.ndarray
        Start point, typically the classic legalization result.
    ctx : Contexte
        Provides the minimum area of each room type.
    rooms : tuple of Piece
        Rooms, for their types.
    spread : tuple of float, optional
        Relative node widths.
    minima : mapping of str to float, optional
        Minimum area per room id, overriding the type's (the shares of a fused room,
        :func:`archlux.geom.rectilineaire.minimum_area_shares`).

    Returns
    -------
    Polytope
        ``poly`` with tighter bounds and one row per chord, labelled
        ``"minimum area <room>: chord <k>"``.

    Raises
    ------
    InvariantViolation
        The start is below a minimum area by more than the proof tolerance: it is not
        a valid legalized plan.
    """
    bornes = list(poly.bounds)
    rows: list[int] = []
    cols: list[int] = []
    vals: list[float] = []
    rhs: list[float] = []
    labels: list[str] = []
    need = _minimum_areas(ctx, rooms, minima)
    for piece in rooms:
        min_area = need[piece.id]
        iw, ih = poly.index[f"{piece.id}.w"], poly.index[f"{piece.id}.h"]
        w0, h0 = float(x[iw]), float(x[ih])
        if min_area <= 0.0 or w0 <= 0.0 or h0 <= 0.0:
            continue
        if w0 * h0 < min_area - AREA_PROOF_M2:
            raise InvariantViolation(
                (f"minimum area {piece.id}: start {w0 * h0:.9f} m² below {min_area:.9f} m²",)
            )
        # A start within the proof tolerance below a_min keeps its own area as target.
        area = min(min_area, w0 * h0)
        (w_lo, w_hi), (h_lo, h_hi) = bornes[iw], bornes[ih]
        # Nodes are not filtered by the bounds: the region is intersected with them
        # anyway, and filtering froze rooms whose height is fixed by a contact.
        nodes = sorted({w0} | {w0 * factor for factor in spread if factor > 0.0})
        bornes[iw] = (max(w_lo, nodes[0]), w_hi)
        bornes[ih] = (max(h_lo, area / nodes[-1]), h_hi)
        for k, (w_left, w_right) in enumerate(pairwise(nodes)):
            h_left, h_right = area / w_left, area / w_right
            slope = (h_right - h_left) / (w_right - w_left)
            line = len(labels)
            rows += [line, line]
            cols += [iw, ih]
            vals += [slope, -1.0]
            rhs.append(slope * w_left - h_left)
            labels.append(f"minimum area {piece.id}: chord {k}")

    extra = sparse.coo_matrix((vals, (rows, cols)), shape=(len(labels), poly.A.shape[1])).tocsr()
    return replace(
        poly,
        A=sparse.vstack([poly.A, extra], format="csr"),
        b=np.concatenate([poly.b, np.asarray(rhs, dtype=float)]),
        bounds=tuple(bornes),
        origins=(*poly.origins, *labels),
    )
