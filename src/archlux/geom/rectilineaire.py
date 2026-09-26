"""Rectilinear rooms (L, U, T, Z) — decomposition into rectangles + fusions.

The polytope stays linear: the fusion constraints are equalities in ``A_eq``.
**Mandatory** cut convention (`MILESTONE-6.md` §2): among the possible vertical cuts
from a reflex vertex, choose the one with the smallest abscissa (left first); on a
tie, the smallest ordinate.

**Horizontal fallback.** A rectilinear polygon does not always admit a separating
vertical chord: a U open on one side, a lying T, a Z. The convention above keeps
priority — so the decompositions already produced are unchanged — but when no
vertical cut separates, the horizontal cut with the smallest ordinate (bottom first)
is tried before declaring failure. On the MSD corpus, this fallback raises the
decomposition rate from 45 % to nearly all aligned rooms.

Outside a dedicated branch: pass ``fusions=`` to :func:`archlux.api.legalize` to
impose the solidarity equalities.

Shape and area of a fused room (PLAN.md batch 1.7): :func:`overlap_constraints` keeps
the order of the sub-rectangle ends along each shared edge and a minimum shared length,
so an L cannot slide into a Z or split; :func:`minimum_area_shares` splits the room's
minimum area across its sub-rectangles for the solver, while the proof checks it on the
union (:func:`archlux.certify.proof.verify_exactly`).
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np
from scipy import sparse
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import split, unary_union

from archlux._deprecation import Alias, lazy_aliases
from archlux.errors import InvariantViolation, UnsupportedInput
from archlux.geom.polytope import Polytope
from archlux.tolerances import AREA_PROOF_M2
from archlux.types import Regulation, Room

__all__ = [
    "MAX_RECTANGLES",
    "MERGE_RIGHT",
    "MERGE_TOP",
    "RectilinearRoom",
    "decompose",
    "extend_merges",
    "merge_constraints",
    "minimum_area_shares",
    "overlap_constraints",
    "recompose",
]

MERGE_RIGHT = "partage_bord_droit"
"""The right edge of rectangle ``i`` coincides with the left edge of ``j``."""

MERGE_TOP = "partage_bord_haut"
"""The top edge of rectangle ``i`` coincides with the bottom edge of ``j``."""

MAX_RECTANGLES = 4
"""Historical cap on sub-rectangles per rectilinear room.

Each sub-rectangle adds 4 variables to the polytope and its fusion equalities: the
cap is a budget safeguard (`ARCHITECTURE.md` §9), not a limit of the algorithm.
`decompose(..., max_rectangles=)` raises it case by case.
"""

_EPS = 1e-9
_TOL_RECT = 1e-7


@dataclass(frozen=True, slots=True)
class RectilinearRoom:
    """Non-rectangular room, seen as rectangles glued together.

    Attributes
    ----------
    rectangles : tuple of Room
        1 to 4 rectangles. The vertical cut on the left first makes the order
        deterministic.
    merges : tuple of (int, int, str)
        Index pairs and kind of shared edge
        (``partage_bord_droit`` / ``partage_bord_haut``).
    """

    id: str
    rectangles: tuple[Room, ...]
    merges: tuple[tuple[int, int, str], ...]


def _coords_ouverts(poly: Polygon) -> list[tuple[float, float]]:
    """Vertices of the exterior ring, without repeating the first point."""
    coords = list(poly.exterior.coords)
    if len(coords) >= 2 and coords[0] == coords[-1]:
        coords = coords[:-1]
    return [(float(x), float(y)) for x, y in coords]


def _is_rectilinear(poly: Polygon) -> bool:
    """Say whether every edge is parallel to an axis."""
    coords = _coords_ouverts(poly)
    if len(coords) < 4:
        return False
    for (x0, y0), (x1, y1) in zip(coords, coords[1:] + coords[:1], strict=True):
        if abs(x0 - x1) > _EPS and abs(y0 - y1) > _EPS:
            return False
    return True


def _is_rectangle(poly: Polygon) -> bool:
    """Say whether the polygon is exactly its own bounding box."""
    if not _is_rectilinear(poly):
        return False
    minx, miny, maxx, maxy = poly.bounds
    candidat = box(minx, miny, maxx, maxy)
    return bool(abs(poly.area - candidat.area) <= _TOL_RECT and poly.equals(candidat))


def _vers_piece(poly: Polygon, *, id: str, room_type: str) -> Room:
    """Convert a Shapely rectangle into a :class:`~archlux.types.Room`."""
    minx, miny, maxx, maxy = poly.bounds
    return Room(
        id=id,
        type=room_type,
        x=float(minx),
        y=float(miny),
        w=float(maxx - minx),
        h=float(maxy - miny),
    )


def _angle_signe(
    prev: tuple[float, float], curr: tuple[float, float], nxt: tuple[float, float]
) -> float:
    """Cross product (curr-prev)×(nxt-curr): >0 = left turn (CCW)."""
    ax, ay = curr[0] - prev[0], curr[1] - prev[1]
    bx, by = nxt[0] - curr[0], nxt[1] - curr[1]
    return ax * by - ay * bx


def _sommets_reflexe(poly: Polygon) -> list[tuple[float, float]]:
    """Vertices with interior angle > π for a CCW ring (right turn)."""
    coords = _coords_ouverts(poly)
    if poly.exterior.is_ccw is False:
        coords = list(reversed(coords))
    n = len(coords)
    reflex: list[tuple[float, float]] = []
    for i in range(n):
        prev = coords[(i - 1) % n]
        curr = coords[i]
        nxt = coords[(i + 1) % n]
        if _angle_signe(prev, curr, nxt) < -_EPS:
            reflex.append(curr)
    return reflex


def _coupe_verticale(poly: Polygon, x_coupe: float, y_sommet: float) -> LineString | None:
    """Interior vertical chord through ``(x_coupe, y_sommet)``."""
    minx, miny, maxx, maxy = poly.bounds
    if not (minx + _EPS < x_coupe < maxx - _EPS):
        return None
    ligne = LineString([(x_coupe, miny - 1.0), (x_coupe, maxy + 1.0)])
    inter = ligne.intersection(poly)
    if inter.is_empty:
        return None
    candidats: list[LineString] = []
    if inter.geom_type == "LineString":
        candidats = [inter]
    elif inter.geom_type == "MultiLineString":
        candidats = list(inter.geoms)
    elif inter.geom_type == "GeometryCollection":
        candidats = [g for g in inter.geoms if g.geom_type == "LineString"]
    pivot = Point(x_coupe, y_sommet)
    # GEOS returns the intersection in pieces: the boundary edge running along the cut
    # and the interior chord arrive separately, although collinear and joined at the
    # reflex vertex. Keeping the first piece amounted to proposing an edge of the
    # polygon as the cut — it separates nothing. So all the pieces touching the pivot
    # are joined: sharing that point on one vertical, their union is a single segment.
    ys: list[float] = []
    for seg in candidats:
        if seg.length <= _EPS or pivot.distance(seg) > 1e-6:
            continue
        ys.extend(c[1] for c in seg.coords)
    if not ys or max(ys) - min(ys) <= _EPS:
        return None
    return LineString([(x_coupe, min(ys)), (x_coupe, max(ys))])


def _coupe_horizontale(poly: Polygon, y_coupe: float, x_sommet: float) -> LineString | None:
    """Interior horizontal chord through ``(x_sommet, y_coupe)``.

    Exact mirror of :func:`_coupe_verticale`, axes swapped.
    """
    minx, miny, maxx, maxy = poly.bounds
    if not (miny + _EPS < y_coupe < maxy - _EPS):
        return None
    ligne = LineString([(minx - 1.0, y_coupe), (maxx + 1.0, y_coupe)])
    inter = ligne.intersection(poly)
    if inter.is_empty:
        return None
    candidats: list[LineString] = []
    if inter.geom_type == "LineString":
        candidats = [inter]
    elif inter.geom_type == "MultiLineString":
        candidats = list(inter.geoms)
    elif inter.geom_type == "GeometryCollection":
        candidats = [g for g in inter.geoms if g.geom_type == "LineString"]
    pivot = Point(x_sommet, y_coupe)
    # Same joining of collinear pieces as in :func:`_coupe_verticale`.
    xs: list[float] = []
    for seg in candidats:
        if seg.length <= _EPS or pivot.distance(seg) > 1e-6:
            continue
        xs.extend(c[0] for c in seg.coords)
    if not xs or max(xs) - min(xs) <= _EPS:
        return None
    return LineString([(min(xs), y_coupe), (max(xs), y_coupe)])


def _meilleure_coupe_verticale(poly: Polygon) -> LineString | None:
    """Vertical cut from a reflex vertex, smallest abscissa (left first)."""
    meilleures: list[tuple[float, float, LineString]] = []
    for x, y in _sommets_reflexe(poly):
        seg = _coupe_verticale(poly, x, y)
        if seg is None:
            continue
        parties = [g for g in split(poly, seg).geoms if g.geom_type == "Polygon"]
        if len(parties) < 2:
            continue
        meilleures.append((x, y, seg))
    if not meilleures:
        return None
    meilleures.sort(key=lambda t: (t[0], t[1]))
    return meilleures[0][2]


def _meilleure_coupe_horizontale(poly: Polygon) -> LineString | None:
    """Horizontal cut from a reflex vertex, smallest ordinate (bottom first).

    Consulted only if no vertical cut separates: the vertical convention of
    `MILESTONE-6.md` §2 keeps priority, so earlier decompositions are bit-for-bit
    unchanged.
    """
    meilleures: list[tuple[float, float, LineString]] = []
    for x, y in _sommets_reflexe(poly):
        seg = _coupe_horizontale(poly, y, x)
        if seg is None:
            continue
        parties = [g for g in split(poly, seg).geoms if g.geom_type == "Polygon"]
        if len(parties) < 2:
            continue
        meilleures.append((y, x, seg))
    if not meilleures:
        return None
    meilleures.sort(key=lambda t: (t[0], t[1]))
    return meilleures[0][2]


def _decouper(poly: Polygon) -> list[Polygon]:
    """Recursive guillotine partition: vertical on the left, then horizontal at the bottom."""
    poly = Polygon(poly.exterior)
    if not poly.is_valid or poly.area <= _EPS:
        raise InvariantViolation(("invalid or zero-area polygon",))
    if _is_rectangle(poly):
        return [poly]
    coupe = _meilleure_coupe_verticale(poly)
    if coupe is None:
        coupe = _meilleure_coupe_horizontale(poly)
    if coupe is None:
        raise InvariantViolation(("no reproducible guillotine cut found",))
    parties = [g for g in split(poly, coupe).geoms if g.geom_type == "Polygon" and g.area > _EPS]
    if len(parties) < 2:
        raise InvariantViolation(("the cut did not split the polygon",))
    parties.sort(key=lambda g: (round(g.bounds[0], 9), round(g.bounds[1], 9)))
    resultat: list[Polygon] = []
    for partie in parties:
        resultat.extend(_decouper(partie))
    return resultat


def _detecter_fusions(rects: tuple[Room, ...]) -> tuple[tuple[int, int, str], ...]:
    """One fusion per shared edge, canonical orientation (left→right / bottom→top)."""
    propres: list[tuple[int, int, str]] = []
    for i, a in enumerate(rects):
        for j in range(i + 1, len(rects)):
            b = rects[j]
            if abs((a.x + a.w) - b.x) <= _TOL_RECT:
                y0 = max(a.y, b.y)
                y1 = min(a.y + a.h, b.y + b.h)
                if y1 - y0 > _TOL_RECT:
                    propres.append((i, j, MERGE_RIGHT))
            elif abs((b.x + b.w) - a.x) <= _TOL_RECT:
                y0 = max(a.y, b.y)
                y1 = min(a.y + a.h, b.y + b.h)
                if y1 - y0 > _TOL_RECT:
                    propres.append((j, i, MERGE_RIGHT))
            if abs((a.y + a.h) - b.y) <= _TOL_RECT:
                x0 = max(a.x, b.x)
                x1 = min(a.x + a.w, b.x + b.w)
                if x1 - x0 > _TOL_RECT:
                    propres.append((i, j, MERGE_TOP))
            elif abs((b.y + b.h) - a.y) <= _TOL_RECT:
                x0 = max(a.x, b.x)
                x1 = min(a.x + a.w, b.x + b.w)
                if x1 - x0 > _TOL_RECT:
                    propres.append((j, i, MERGE_TOP))
    propres.sort()
    return tuple(propres)


def decompose(
    polygon: Polygon,
    *,
    id: str = "piece",
    room_type: str = "piece",
    max_rectangles: int = MAX_RECTANGLES,
) -> RectilinearRoom:
    """Cut a rectilinear polygon into rectangles glued together.

    Recursive guillotine cut: vertical with the smallest abscissa first
    (`MILESTONE-6.md` §2), horizontal with the smallest ordinate as a fallback when no
    vertical cut separates (lying U, lying T, Z).

    Parameters
    ----------
    polygon : shapely.geometry.Polygon
        Simple outline, edges only horizontal or vertical.
    id, room_type : str, optional
        Domain identity carried over to each sub-rectangle (suffix ``__k``).
    max_rectangles : int, optional
        Cap on sub-rectangles. Default :data:`MAX_RECTANGLES` (4), the historical value
        kept so as not to change the behaviour of existing callers. Each sub-rectangle
        adds 4 variables to the polytope and its fusion equalities: raising this cap
        makes the LP heavier, hence the budget of `ARCHITECTURE.md` §9. A real corpus
        commonly needs 6 to 8.

    Returns
    -------
    RectilinearRoom
        Rectangles ordered (min x, then min y) and fusions of shared edges.

    Raises
    ------
    InvariantViolation
        Polygon that is non-rectilinear, invalid, not cuttable under the convention,
        or exceeding ``max_rectangles``.
    """
    if not isinstance(polygon, Polygon) or polygon.is_empty:
        raise InvariantViolation(("non-empty polygon expected",))
    if not polygon.is_valid:
        raise InvariantViolation(("invalid polygon",))
    if max_rectangles < 1:
        raise InvariantViolation((f"max_rectangles must be ≥ 1: {max_rectangles}",))
    if not _is_rectilinear(polygon):
        raise InvariantViolation(("non-rectilinear polygon: diagonal edge",))
    parties = _decouper(polygon)
    if len(parties) > max_rectangles:
        raise InvariantViolation((f"too many rectangles ({len(parties)}): max {max_rectangles}",))
    parties.sort(key=lambda g: (round(g.bounds[0], 9), round(g.bounds[1], 9)))
    rectangles = tuple(
        _vers_piece(p, id=f"{id}__{k}", room_type=room_type) for k, p in enumerate(parties)
    )
    return RectilinearRoom(id=id, rectangles=rectangles, merges=_detecter_fusions(rectangles))


def recompose(piece: RectilinearRoom) -> Polygon:
    """Rebuild the original polygon from its rectangles.

    Returns
    -------
    shapely.geometry.Polygon
        Union of the rectangles. For a partition without holes, equal to the input
        polygon of :func:`decompose`.
    """
    if not piece.rectangles:
        raise InvariantViolation(("RectilinearRoom without rectangle",))
    boites = [box(r.x, r.y, r.x + r.w, r.y + r.h) for r in piece.rectangles]
    union = unary_union(boites)
    if union.geom_type != "Polygon":
        raise InvariantViolation((f"disconnected recomposition: {union.geom_type}",))
    return union


def merge_constraints(
    piece: RectilinearRoom, index: dict[str, int]
) -> tuple[tuple[str, dict[str, float], float], ...]:
    """Translate the fusions into affine equalities ``Σ a_k v_k = b``.

    ``partage_bord_droit``: ``x_i + w_i − x_j = 0``.
    ``partage_bord_haut``: ``y_i + h_i − y_j = 0``.
    """
    egalites: list[tuple[str, dict[str, float], float]] = []
    for i, j, nature in piece.merges:
        a, b = piece.rectangles[i], piece.rectangles[j]
        if nature == MERGE_RIGHT:
            for nom in (f"{a.id}.x", f"{a.id}.w", f"{b.id}.x"):
                if nom not in index:
                    raise InvariantViolation((f"variable missing from the index: {nom}",))
            egalites.append(
                (
                    f"fusion verticale {a.id}|{b.id}",
                    {f"{a.id}.x": 1.0, f"{a.id}.w": 1.0, f"{b.id}.x": -1.0},
                    0.0,
                )
            )
        elif nature == MERGE_TOP:
            for nom in (f"{a.id}.y", f"{a.id}.h", f"{b.id}.y"):
                if nom not in index:
                    raise InvariantViolation((f"variable missing from the index: {nom}",))
            egalites.append(
                (
                    f"fusion horizontale {a.id}|{b.id}",
                    {f"{a.id}.y": 1.0, f"{a.id}.h": 1.0, f"{b.id}.y": -1.0},
                    0.0,
                )
            )
        else:
            raise InvariantViolation((f"unknown fusion kind: {nature!r}",))
    return tuple(egalites)


def minimum_area_shares(
    rooms: tuple[Room, ...],
    merges: tuple[RectilinearRoom, ...],
    regulation: Regulation,
) -> dict[str, float]:
    """Split the minimum area of each fused room across its sub-rectangles.

    ``w h >= a`` is handled per rectangle by the solver (:mod:`archlux.lmo.cuts`),
    but the minimum of a fused room applies to the union of its sub-rectangles, whose
    area ``Σ w_k h_k`` is not a convex constraint. Each sub-rectangle ``k`` gets the
    share ``a · (w_k h_k) / Σ_j w_j h_j`` of the room minimum ``a``, in proportion to
    its area in ``rooms``.

    Parameters
    ----------
    rooms : tuple of Piece
        Rooms of the plan whose proportions set the shares (the proposed plan, or the
        start point of an optimization).
    fusions : tuple of PieceRectilineaire
        Fused rooms; their sub-rectangles are found in ``rooms`` by id.
    referentiel : Referentiel
        Minimum area by room type; a fused room takes the largest minimum of the types
        of its sub-rectangles.

    Returns
    -------
    dict of str to float
        Minimum area of every sub-rectangle found in ``rooms``; other rooms are absent.

    Guarantees
    ----------
    - Geometric: **exact** (sound). The shares add up to the room minimum, so
      sub-rectangles that meet their shares and do not overlap cover at least the
      minimum. It is an inner approximation: a plan moving area from one arm of the L
      to the other beyond the proposed proportions may be refused although valid.
    """
    by_id = {room.id: room for room in rooms}
    shares: dict[str, float] = {}
    for piece in merges:
        members = [by_id[r.id] for r in piece.rectangles if r.id in by_id]
        if not members:
            continue
        minimum = max(regulation.min_area(member.type) for member in members)
        total = sum(member.w * member.h for member in members)
        if total <= 0.0:
            raise UnsupportedInput(f"fused room {piece.id} has no area in the proposed plan")
        for member in members:
            # The solver accepts each rectangle up to AREA_PROOF_M2 below its share; the
            # proof accepts the union up to AREA_PROOF_M2 once. Adding that tolerance to
            # every share keeps k sub-rectangles from missing the minimum by k * tol.
            shares[member.id] = minimum * (member.w * member.h) / total + (
                AREA_PROOF_M2 if minimum > 0.0 else 0.0
            )
    return shares


_Row = tuple[str, dict[str, float], float]
"""A labelled affine row ``(label, {variable: coefficient}, right-hand side)``."""


def _interval(room: Room, axis: str) -> tuple[float, float, dict[str, float], dict[str, float]]:
    """Proposed interval of ``room`` on ``axis`` and the affine forms of its two ends."""
    position, size = ("y", "h") if axis == "y" else ("x", "w")
    low = float(getattr(room, position))
    high = low + float(getattr(room, size))
    low_form = {f"{room.id}.{position}": 1.0}
    return low, high, low_form, {**low_form, f"{room.id}.{size}": 1.0}


def _difference(left: dict[str, float], right: dict[str, float]) -> dict[str, float]:
    """Affine form ``left - right``."""
    terms = dict(left)
    for name, coefficient in right.items():
        terms[name] = terms.get(name, 0.0) - coefficient
    return terms


def overlap_constraints(
    piece: RectilinearRoom, index: dict[str, int], *, min_contact: float = 0.0
) -> tuple[tuple[_Row, ...], tuple[_Row, ...]]:
    """Keep the shape of a fused room on the axis orthogonal to each shared edge.

    A fusion glues one edge line (:func:`contraintes_fusion`) but lets the two
    sub-rectangles slide along it: an L could turn into a T, a Z, or two detached
    pieces (AUDIT.md §5.2). For each fusion, with ``[a0, a1]`` and ``[b0, b1]`` the
    intervals of the two sub-rectangles along the shared edge:

    - ends that coincide in the decomposition (within ``SNAP_M``) stay equal;
    - other ends keep their order, non-strictly (``a0 < b0`` gives ``a0 <= b0``);
    - the shared edge keeps a length of at least ``min_contact``:
      ``min(a1, b1) - max(a0, b0) >= min_contact``, linear since the order is fixed.

    The generator decides the order, the solver the dimensions: an L stays an L (or
    degenerates into a rectangle when its step closes), a T stays a T or an L.

    Parameters
    ----------
    piece : PieceRectilineaire
        Fused room; its rectangles give the order to keep.
    index : dict of str to int
        Variables of the polytope.
    min_contact : float, optional
        Minimum length of every shared edge, in metres.

    Returns
    -------
    tuple
        ``(equalities, inequalities)``: rows ``Σ a_k v_k = b`` and ``Σ a_k v_k <= b``.

    Raises
    ------
    InvariantViolation
        A variable is missing from ``index``, or the fusion kind is unknown.
    """
    equalities: list[_Row] = []
    inequalities: list[_Row] = []
    for i, j, kind in piece.merges:
        if kind not in (MERGE_RIGHT, MERGE_TOP):
            raise InvariantViolation((f"unknown fusion kind: {kind!r}",))
        a, b = piece.rectangles[i], piece.rectangles[j]
        axis = "y" if kind == MERGE_RIGHT else "x"
        a0, a1, a_low, a_high = _interval(a, axis)
        b0, b1, b_low, b_high = _interval(b, axis)
        pair = f"{a.id}|{b.id}"
        for end, (va, vb, fa, fb) in (
            ("low", (a0, b0, a_low, b_low)),
            ("high", (a1, b1, a_high, b_high)),
        ):
            if abs(va - vb) <= _TOL_RECT:
                equalities.append((f"fusion {pair}: aligned {end} ends", _difference(fa, fb), 0.0))
            elif va < vb:
                inequalities.append((f"fusion {pair}: {end} end order", _difference(fa, fb), 0.0))
            else:
                inequalities.append((f"fusion {pair}: {end} end order", _difference(fb, fa), 0.0))
        max_low = a_low if a0 >= b0 else b_low
        min_high = a_high if a1 <= b1 else b_high
        inequalities.append(
            (f"fusion {pair}: minimum contact", _difference(max_low, min_high), -min_contact)
        )
    for _, terms, _ in (*equalities, *inequalities):
        for name in terms:
            if name not in index:
                raise InvariantViolation((f"variable missing from the index: {name}",))
    return tuple(equalities), tuple(inequalities)


def _rows(rows: tuple[_Row, ...], index: dict[str, int]) -> tuple[sparse.csr_matrix, np.ndarray]:
    """Sparse matrix and right-hand side of labelled rows."""
    lines: list[int] = []
    columns: list[int] = []
    values: list[float] = []
    for rank, (_, terms, _) in enumerate(rows):
        for name, coefficient in terms.items():
            if coefficient != 0.0:
                lines.append(rank)
                columns.append(index[name])
                values.append(coefficient)
    matrix = sparse.coo_matrix((values, (lines, columns)), shape=(len(rows), len(index))).tocsr()
    return matrix, np.asarray([rhs for _, _, rhs in rows], dtype=float)


def extend_merges(poly: Polytope, piece: RectilinearRoom, *, min_contact: float = 0.0) -> Polytope:
    """Add the fusion equalities and the overlap constraints of a fused room.

    Parameters
    ----------
    poly : Polytope
        System already assembled for the sub-rectangles.
    piece : PieceRectilineaire
        Fusions to impose. The ids of the sub-rectangles must be in ``poly.index``.
    min_contact : float, optional
        Minimum length of every shared edge, in metres
        (:func:`overlap_constraints`). :func:`archlux.api.legalize` passes
        ``referentiel.largeur_min``.

    Returns
    -------
    Polytope
        New instance: fusion equalities and aligned ends in ``A_eq`` (labelled in
        ``origines_eq``), end order and minimum contact in ``A`` (labelled in
        ``origines``).
    """
    merges = tuple(
        (f"fusion {label}", terms, rhs)
        for label, terms, rhs in merge_constraints(piece, poly.index)
    )
    aligned, ordered = overlap_constraints(piece, poly.index, min_contact=min_contact)
    equalities = merges + aligned
    if not equalities and not ordered:
        return poly
    a_eq, b_eq, a, b = poly.A_eq, poly.b_eq, poly.A, poly.b
    if equalities:
        extra, rhs = _rows(equalities, poly.index)
        a_eq = sparse.vstack([poly.A_eq, extra], format="csr") if poly.A_eq.shape[0] else extra
        b_eq = np.concatenate([poly.b_eq, rhs]) if poly.A_eq.shape[0] else rhs
    if ordered:
        extra, rhs = _rows(ordered, poly.index)
        a = sparse.vstack([poly.A, extra], format="csr") if poly.A.shape[0] else extra
        b = np.concatenate([poly.b, rhs]) if poly.A.shape[0] else rhs
    return replace(
        poly,
        A=a,
        b=b,
        A_eq=a_eq,
        b_eq=b_eq,
        origins=(*poly.origins, *(label for label, _, _ in ordered)),
        origins_eq=poly.eq_labels() + tuple(label for label, _, _ in equalities),
    )


__getattr__ = lazy_aliases(
    __name__,
    {
        "PieceRectilineaire": Alias(RectilinearRoom, "archlux.geom.rectilineaire.RectilinearRoom"),
        "decomposer": Alias(decompose, "archlux.geom.rectilineaire.decompose"),
        "recomposer": Alias(recompose, "archlux.geom.rectilineaire.recompose"),
        "contraintes_fusion": Alias(
            merge_constraints, "archlux.geom.rectilineaire.merge_constraints"
        ),
        "etendre_fusions": Alias(extend_merges, "archlux.geom.rectilineaire.extend_merges"),
        "FUSION_DROIT": Alias(MERGE_RIGHT, "archlux.geom.rectilineaire.MERGE_RIGHT"),
        "FUSION_HAUT": Alias(MERGE_TOP, "archlux.geom.rectilineaire.MERGE_TOP"),
    },
)
