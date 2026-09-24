"""Pièces rectilinéaires (L, U, T, Z) — décomposition en rectangles + fusions.

Le polytope reste linéaire : les contraintes de fusion sont des égalités dans
``A_eq``. Convention de coupe **obligatoire** (`MILESTONE-6.md` §2) : parmi les
coupes verticales possibles depuis un sommet réflexe, choisir celle d'abscisse
minimale (gauche d'abord) ; en cas d'égalité, ordonnée minimale.

**Repli horizontal.** Un polygone rectilinéaire n'admet pas toujours de corde
verticale séparante : un U ouvert sur un côté, un T couché, un Z. La convention
ci-dessus reste prioritaire — donc les décompositions déjà produites sont
inchangées — mais lorsqu'aucune coupe verticale ne sépare, on essaie la coupe
horizontale d'ordonnée minimale (bas d'abord) avant de déclarer l'échec. Sur le
corpus MSD, ce repli fait passer le taux de décomposition de 45 % à l'essentiel
des pièces  alignées.

Hors branche dédiée : passer ``fusions=`` à :func:`archlux.api.legalize` pour
imposer les égalités de solidarisation.

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

from archlux.erreurs import InvariantViole
from archlux.geom.polytope import Polytope
from archlux.types import Piece, Referentiel

__all__ = [
    "FUSION_DROIT",
    "FUSION_HAUT",
    "MAX_RECTANGLES",
    "PieceRectilineaire",
    "contraintes_fusion",
    "decomposer",
    "etendre_fusions",
    "minimum_area_shares",
    "overlap_constraints",
    "recomposer",
]

FUSION_DROIT = "partage_bord_droit"
"""Le bord droit du rectangle ``i`` coïncide avec le bord gauche de ``j``."""

FUSION_HAUT = "partage_bord_haut"
"""Le bord haut du rectangle ``i`` coïncide avec le bord bas de ``j``."""

MAX_RECTANGLES = 4
"""Plafond historique de sous-rectangles par piece rectilineaire.

Chaque sous-rectangle ajoute 4 variables au polytope et ses egalites de fusion :
le plafond est un garde-fou de budget (`ARCHITECTURE.md` §9), pas une limite de
l'algorithme. `decomposer(..., max_rectangles=)` le releve au cas par cas.
"""

_EPS = 1e-9
_TOL_RECT = 1e-7


@dataclass(frozen=True, slots=True)
class PieceRectilineaire:
    """Pièce non rectangulaire, vue comme rectangles solidaires.

    Attributes
    ----------
    rectangles : tuple of Piece
        1 à 4 rectangles. La coupe verticale à gauche d'abord rend l'ordre
        déterministe.
    fusions : tuple of (int, int, str)
        Paires d'indices et nature du bord partagé
        (``partage_bord_droit`` / ``partage_bord_haut``).
    """

    id: str
    rectangles: tuple[Piece, ...]
    fusions: tuple[tuple[int, int, str], ...]


def _coords_ouverts(poly: Polygon) -> list[tuple[float, float]]:
    """Sommets du contour exterieur, sans repeter le premier point."""
    coords = list(poly.exterior.coords)
    if len(coords) >= 2 and coords[0] == coords[-1]:
        coords = coords[:-1]
    return [(float(x), float(y)) for x, y in coords]


def _est_rectilineaire(poly: Polygon) -> bool:
    """Dire si toutes les aretes sont paralleles a un axe."""
    coords = _coords_ouverts(poly)
    if len(coords) < 4:
        return False
    for (x0, y0), (x1, y1) in zip(coords, coords[1:] + coords[:1], strict=True):
        if abs(x0 - x1) > _EPS and abs(y0 - y1) > _EPS:
            return False
    return True


def _est_rectangle(poly: Polygon) -> bool:
    """Dire si le polygone est exactement sa propre boite englobante."""
    if not _est_rectilineaire(poly):
        return False
    minx, miny, maxx, maxy = poly.bounds
    candidat = box(minx, miny, maxx, maxy)
    return bool(abs(poly.area - candidat.area) <= _TOL_RECT and poly.equals(candidat))


def _vers_piece(poly: Polygon, *, id: str, type_piece: str) -> Piece:
    """Convertir un rectangle Shapely en :class:`~archlux.types.Piece`."""
    minx, miny, maxx, maxy = poly.bounds
    return Piece(
        id=id,
        type=type_piece,
        x=float(minx),
        y=float(miny),
        w=float(maxx - minx),
        h=float(maxy - miny),
    )


def _angle_signe(
    prev: tuple[float, float], curr: tuple[float, float], nxt: tuple[float, float]
) -> float:
    """Produit vectoriel (curr-prev)×(nxt-curr) : >0 = tour à gauche (CCW)."""
    ax, ay = curr[0] - prev[0], curr[1] - prev[1]
    bx, by = nxt[0] - curr[0], nxt[1] - curr[1]
    return ax * by - ay * bx


def _sommets_reflexe(poly: Polygon) -> list[tuple[float, float]]:
    """Sommets d'angle intérieur > π pour un anneau CCW (tour à droite)."""
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
    """Corde verticale intérieure passant par ``(x_coupe, y_sommet)``."""
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
    # GEOS rend l'intersection en morceaux : l'arête de bord qui longe la coupe et la
    # corde intérieure arrivent séparément, bien que colinéaires et jointives au
    # sommet réflexe. Retenir le premier morceau revenait à proposer une arête du
    # polygone comme coupe — elle ne sépare rien. On réunit donc tous les morceaux
    # qui touchent le pivot : partageant ce point sur une même verticale, leur union
    # est un segment unique.
    ys: list[float] = []
    for seg in candidats:
        if seg.length <= _EPS or pivot.distance(seg) > 1e-6:
            continue
        ys.extend(c[1] for c in seg.coords)
    if not ys or max(ys) - min(ys) <= _EPS:
        return None
    return LineString([(x_coupe, min(ys)), (x_coupe, max(ys))])


def _coupe_horizontale(poly: Polygon, y_coupe: float, x_sommet: float) -> LineString | None:
    """Corde horizontale intérieure passant par ``(x_sommet, y_coupe)``.

    Symétrique exacte de :func:`_coupe_verticale`, axes échangés.
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
    # Même réunion des morceaux colinéaires que dans :func:`_coupe_verticale`.
    xs: list[float] = []
    for seg in candidats:
        if seg.length <= _EPS or pivot.distance(seg) > 1e-6:
            continue
        xs.extend(c[0] for c in seg.coords)
    if not xs or max(xs) - min(xs) <= _EPS:
        return None
    return LineString([(min(xs), y_coupe), (max(xs), y_coupe)])


def _meilleure_coupe_verticale(poly: Polygon) -> LineString | None:
    """Coupe verticale depuis un réflexe, abscisse minimale (gauche d'abord)."""
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
    """Coupe horizontale depuis un réflexe, ordonnée minimale (bas d'abord).

    N'est consultée que si aucune coupe verticale ne sépare : la convention
    verticale de `MILESTONE-6.md` §2 garde la priorité, donc les décompositions
    antérieures sont bit-à-bit inchangées.
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
    """Partition guillotine récursive : verticale à gauche, puis horizontale en bas."""
    poly = Polygon(poly.exterior)
    if not poly.is_valid or poly.area <= _EPS:
        raise InvariantViole(("polygone invalide ou d'aire nulle",))
    if _est_rectangle(poly):
        return [poly]
    coupe = _meilleure_coupe_verticale(poly)
    if coupe is None:
        coupe = _meilleure_coupe_horizontale(poly)
    if coupe is None:
        raise InvariantViole(("aucune coupe guillotine reproductible trouvée",))
    parties = [g for g in split(poly, coupe).geoms if g.geom_type == "Polygon" and g.area > _EPS]
    if len(parties) < 2:
        raise InvariantViole(("la coupe verticale n'a pas séparé le polygone",))
    parties.sort(key=lambda g: (round(g.bounds[0], 9), round(g.bounds[1], 9)))
    resultat: list[Polygon] = []
    for partie in parties:
        resultat.extend(_decouper(partie))
    return resultat


def _detecter_fusions(rects: tuple[Piece, ...]) -> tuple[tuple[int, int, str], ...]:
    """Une fusion par bord partagé, orientation canonique (gauche→droite / bas→haut)."""
    propres: list[tuple[int, int, str]] = []
    for i, a in enumerate(rects):
        for j in range(i + 1, len(rects)):
            b = rects[j]
            if abs((a.x + a.w) - b.x) <= _TOL_RECT:
                y0 = max(a.y, b.y)
                y1 = min(a.y + a.h, b.y + b.h)
                if y1 - y0 > _TOL_RECT:
                    propres.append((i, j, FUSION_DROIT))
            elif abs((b.x + b.w) - a.x) <= _TOL_RECT:
                y0 = max(a.y, b.y)
                y1 = min(a.y + a.h, b.y + b.h)
                if y1 - y0 > _TOL_RECT:
                    propres.append((j, i, FUSION_DROIT))
            if abs((a.y + a.h) - b.y) <= _TOL_RECT:
                x0 = max(a.x, b.x)
                x1 = min(a.x + a.w, b.x + b.w)
                if x1 - x0 > _TOL_RECT:
                    propres.append((i, j, FUSION_HAUT))
            elif abs((b.y + b.h) - a.y) <= _TOL_RECT:
                x0 = max(a.x, b.x)
                x1 = min(a.x + a.w, b.x + b.w)
                if x1 - x0 > _TOL_RECT:
                    propres.append((j, i, FUSION_HAUT))
    propres.sort()
    return tuple(propres)


def decomposer(
    polygone: Polygon,
    *,
    id: str = "piece",
    type_piece: str = "piece",
    max_rectangles: int = MAX_RECTANGLES,
) -> PieceRectilineaire:
    """Découper un polygone rectilinéaire en rectangles solidaires.

    Coupe guillotine récursive : verticale d'abscisse minimale d'abord
    (`MILESTONE-6.md` §2), horizontale d'ordonnée minimale en repli lorsqu'aucune
    verticale ne sépare (U couché, T couché, Z).

    Parameters
    ----------
    polygone : shapely.geometry.Polygon
        Contour simple, arêtes uniquement horizontales ou verticales.
    id, type_piece : str, optional
        Identité métier reportée sur chaque sous-rectangle (suffixe ``__k``).
    max_rectangles : int, optional
        Plafond de sous-rectangles. Défaut :data:`MAX_RECTANGLES` (4), valeur
        historique conservée pour ne pas changer le comportement des appelants
        existants. Chaque sous-rectangle ajoute 4 variables au polytope et ses
        égalités de fusion : relever ce plafond alourdit le LP, donc le budget
        `ARCHITECTURE.md` §9. Un corpus réel demande couramment 6 à 8.

    Returns
    -------
    PieceRectilineaire
        Rectangles ordonnés (min x, puis min y) et fusions de bords partagés.

    Raises
    ------
    InvariantViole
        Polygone non rectilinéaire, invalide, non découpable sous la convention,
        ou dépassant ``max_rectangles``.
    """
    if not isinstance(polygone, Polygon) or polygone.is_empty:
        raise InvariantViole(("polygone attendu, non vide",))
    if not polygone.is_valid:
        raise InvariantViole(("polygone invalide",))
    if max_rectangles < 1:
        raise InvariantViole((f"max_rectangles doit être ≥ 1 : {max_rectangles}",))
    if not _est_rectilineaire(polygone):
        raise InvariantViole(("polygone non rectilinéaire : arête diagonale",))
    parties = _decouper(polygone)
    if len(parties) > max_rectangles:
        raise InvariantViole((f"trop de rectangles ({len(parties)}) : max {max_rectangles}",))
    parties.sort(key=lambda g: (round(g.bounds[0], 9), round(g.bounds[1], 9)))
    rectangles = tuple(
        _vers_piece(p, id=f"{id}__{k}", type_piece=type_piece) for k, p in enumerate(parties)
    )
    return PieceRectilineaire(id=id, rectangles=rectangles, fusions=_detecter_fusions(rectangles))


def recomposer(piece: PieceRectilineaire) -> Polygon:
    """Recomposer le polygone d'origine depuis ses rectangles.

    Returns
    -------
    shapely.geometry.Polygon
        Union des rectangles. Pour une partition sans trou, égal au polygone
        d'entrée de :func:`decomposer`.
    """
    if not piece.rectangles:
        raise InvariantViole(("PieceRectilineaire sans rectangle",))
    boites = [box(r.x, r.y, r.x + r.w, r.y + r.h) for r in piece.rectangles]
    union = unary_union(boites)
    if union.geom_type != "Polygon":
        raise InvariantViole((f"recomposition non connexe : {union.geom_type}",))
    return union


def contraintes_fusion(
    piece: PieceRectilineaire, index: dict[str, int]
) -> tuple[tuple[str, dict[str, float], float], ...]:
    """Traduire les fusions en égalités affines ``Σ a_k v_k = b``.

    ``partage_bord_droit`` : ``x_i + w_i − x_j = 0``.
    ``partage_bord_haut`` : ``y_i + h_i − y_j = 0``.
    """
    egalites: list[tuple[str, dict[str, float], float]] = []
    for i, j, nature in piece.fusions:
        a, b = piece.rectangles[i], piece.rectangles[j]
        if nature == FUSION_DROIT:
            for nom in (f"{a.id}.x", f"{a.id}.w", f"{b.id}.x"):
                if nom not in index:
                    raise InvariantViole((f"variable absente de l'index : {nom}",))
            egalites.append(
                (
                    f"fusion verticale {a.id}|{b.id}",
                    {f"{a.id}.x": 1.0, f"{a.id}.w": 1.0, f"{b.id}.x": -1.0},
                    0.0,
                )
            )
        elif nature == FUSION_HAUT:
            for nom in (f"{a.id}.y", f"{a.id}.h", f"{b.id}.y"):
                if nom not in index:
                    raise InvariantViole((f"variable absente de l'index : {nom}",))
            egalites.append(
                (
                    f"fusion horizontale {a.id}|{b.id}",
                    {f"{a.id}.y": 1.0, f"{a.id}.h": 1.0, f"{b.id}.y": -1.0},
                    0.0,
                )
            )
        else:
            raise InvariantViole((f"nature de fusion inconnue : {nature!r}",))
    return tuple(egalites)


def minimum_area_shares(
    rooms: tuple[Piece, ...],
    fusions: tuple[PieceRectilineaire, ...],
    referentiel: Referentiel,
) -> dict[str, float]:
    """Split the minimum area of each fused room across its sub-rectangles.

    ``w h >= a`` is handled per rectangle by the solver (:mod:`archlux.lmo.coupes`),
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
    for piece in fusions:
        members = [by_id[r.id] for r in piece.rectangles if r.id in by_id]
        if not members:
            continue
        minimum = max(referentiel.a_min(member.type) for member in members)
        total = sum(member.w * member.h for member in members)
        if total <= 0.0:
            raise InvariantViole((f"fused room {piece.id} has no area",))
        for member in members:
            shares[member.id] = minimum * (member.w * member.h) / total
    return shares


_Row = tuple[str, dict[str, float], float]
"""A labelled affine row ``(label, {variable: coefficient}, right-hand side)``."""


def _interval(room: Piece, axis: str) -> tuple[float, float, dict[str, float], dict[str, float]]:
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
    piece: PieceRectilineaire, index: dict[str, int], *, min_contact: float = 0.0
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
    InvariantViole
        A variable is missing from ``index``, or the fusion kind is unknown.
    """
    equalities: list[_Row] = []
    inequalities: list[_Row] = []
    for i, j, kind in piece.fusions:
        if kind not in (FUSION_DROIT, FUSION_HAUT):
            raise InvariantViole((f"unknown fusion kind: {kind!r}",))
        a, b = piece.rectangles[i], piece.rectangles[j]
        axis = "y" if kind == FUSION_DROIT else "x"
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
                raise InvariantViole((f"variable missing from the index: {name}",))
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


def etendre_fusions(
    poly: Polytope, piece: PieceRectilineaire, *, min_contact: float = 0.0
) -> Polytope:
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
    fusions = tuple(
        (f"fusion {label}", terms, rhs)
        for label, terms, rhs in contraintes_fusion(piece, poly.index)
    )
    aligned, ordered = overlap_constraints(piece, poly.index, min_contact=min_contact)
    equalities = fusions + aligned
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
        origines=(*poly.origines, *(label for label, _, _ in ordered)),
        origines_eq=poly.labels_eq() + tuple(label for label, _, _ in equalities),
    )
