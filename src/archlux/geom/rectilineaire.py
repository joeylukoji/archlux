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
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np
from scipy import sparse
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import split, unary_union

from archlux.erreurs import InvariantViole
from archlux.geom.polytope import Polytope
from archlux.types import Piece

__all__ = [
    "FUSION_DROIT",
    "FUSION_HAUT",
    "MAX_RECTANGLES",
    "PieceRectilineaire",
    "contraintes_fusion",
    "decomposer",
    "etendre_fusions",
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


def etendre_fusions(poly: Polytope, piece: PieceRectilineaire) -> Polytope:
    """Ajouter les égalités de fusion au polytope (``A_eq``, ``b_eq``).

    Parameters
    ----------
    poly : Polytope
        Système déjà assemblé pour les sous-rectangles.
    piece : PieceRectilineaire
        Fusions à imposer. Les ids des sous-rectangles doivent figurer dans
        ``poly.index``.

    Returns
    -------
    Polytope
        Nouvelle instance ; ``origines`` inchangées (les fusions sont des égalités,
        pas des inégalités dualisées).
    """
    egalites = contraintes_fusion(piece, poly.index)
    if not egalites:
        return poly
    n_var = len(poly.index)
    n_new = len(egalites)
    lignes: list[int] = []
    colonnes: list[int] = []
    valeurs: list[float] = []
    b_extra: list[float] = []
    labels: list[str] = []
    for rang, (libelle, termes, borne) in enumerate(egalites):
        for nom, coef in termes.items():
            lignes.append(rang)
            colonnes.append(poly.index[nom])
            valeurs.append(coef)
        b_extra.append(borne)
        labels.append(f"fusion {libelle}")
    a_extra = sparse.coo_matrix((valeurs, (lignes, colonnes)), shape=(n_new, n_var)).tocsr()
    if poly.A_eq.shape[0]:
        a_eq = sparse.vstack([poly.A_eq, a_extra], format="csr")
        b_eq = np.concatenate([poly.b_eq, np.asarray(b_extra, dtype=float)])
    else:
        a_eq = a_extra
        b_eq = np.asarray(b_extra, dtype=float)
    return replace(poly, A_eq=a_eq, b_eq=b_eq, origines_eq=poly.labels_eq() + tuple(labels))
