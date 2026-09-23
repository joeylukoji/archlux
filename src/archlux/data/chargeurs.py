"""Chargeurs de corpus réels : WKT → :class:`~archlux.types.Plan`.

Le corpus MSD (van Engelenburg *et al.*, ECCV 2024, CC BY-SA 4.0) livre chaque étage
en polygones WKT, **dans le repère du site** : aucun appartement n'est aligné sur
les axes. Or ``geom`` travaille sur des rectangles axés.

La conversion tient en quatre gestes, dans cet ordre :

1. **Redresser.** La direction dominante des murs, de période 90° et pondérée par
   les longueurs (:func:`~archlux.orient.circulaire.direction_dominante`), donne
   l'angle du repère local. Cet angle **est** l'``Orientation`` du plan : il n'est
   pas jeté, il devient la donnée d'entrée du substitut d'éclairement.
2. **Caler.** Après rotation, les arêtes sont à quelques millimètres d'un axe
   (médiane mesurée : 0 mm). On force l'alignement exact sous ``tolerance_calage``,
   sans quoi ``geom.rectilineaire`` refuse le polygone pour « arête diagonale ».
3. **Décomposer.** Peu de pièces réelles sont des rectangles (0,1 % des
   appartements) ; presque toutes sont rectilinéaires. Chaque pièce devient une
   :class:`~archlux.geom.rectilineaire.PieceRectilineaire`, et ses égalités de
   solidarisation passent à ``legalize(..., fusions=)``.
4. **Rattacher les baies.** Une fenêtre est projetée sur le mur le plus proche et
   stockée en ``(mur_id, s, largeur_rel)`` — **jamais** en absolu
   (`ARCHITECTURE.md` §10).

Ce que MSD ne donne pas
-----------------------
**Aucune annotation de mur porteur.** Les seuls sous-types de séparateur sont
``WALL`` et ``COLUMN``. ``Structure.murs_porteurs`` est donc vide et seuls les
poteaux sont renseignés : inventer une portance produirait des égalités ``A_eq``
arbitraires, et un ``structure_preservee`` qui ne veut rien dire.

Aucune simulation d'éclairement non plus : voir ``docs/donnees/verite-terrain.md``.
"""

from __future__ import annotations

import csv
import io
import math
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from shapely import affinity, wkt
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

from archlux.erreurs import InvariantViole
from archlux.geom.rectilineaire import PieceRectilineaire, decomposer
from archlux.orient.circulaire import direction_dominante
from archlux.types import (
    Contexte,
    Mur,
    Orientation,
    Ouverture,
    Piece,
    Plan,
    Referentiel,
    Structure,
)

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

__all__ = [
    "COLONNE_SOLEIL_DEFAUT",
    "TYPES_EXCLUS",
    "AppartementMSD",
    "StatistiquesChargement",
    "charger_etiquettes_sd",
    "charger_msd",
    "decouper_par_site",
    "etiqueter",
]

TYPES_EXCLUS = frozenset({"SHAFT", "ELEVATOR", "STAIRCASE", "VOID", "BALCONY", "TERRACE"})
"""Sous-types d'``area`` écartés : ils ne font pas partie du logement habitable.

Les gaines et cages créent des **trous** dans l'union des pièces ; les balcons et
terrasses en sortent. Dans les deux cas le contour cesse d'être un anneau simple,
que :class:`~archlux.types.Plan` ne sait pas représenter.
"""

COLONNE_SOLEIL_DEFAUT = "sun_201803211200_mean"
"""Colonne d'irradiance retenue par defaut : 21 mars a 12 h, moyenne par piece.

`simulations.csv` en offre **126** : 18 instants x 7 agregations (``max``, ``mean``,
``median``, ``min``, ``p20``, ``p80``, ``stddev``). Le choix ci-dessus est celui de
l'equinoxe a midi, l'instant le moins atypique des dix-huit ; il n'a rien de
canonique et doit etre **cite tel quel** dans toute publication.

!!! danger "Ce n'est pas un sDA"
    Ces colonnes sont des agregats d'irradiance a instants fixes, pas la part du
    sol au-dessus de 300 lux pendant 50 % des heures d'occupation. Calibrer
    dessus borne **ces colonnes**, jamais un sDA LM-83. L'etiquette
    ``indicateur`` d'``archlux`` doit alors se lire comme le nom de la cible
    apprise, pas comme la metrique IES.
"""

_EPS = 1e-9
_LARGEUR_MUR_MAX = 1.0
"""Au-delà, le « mur » est un massif, pas une cloison : son axe long n'a pas de sens."""


@dataclass(frozen=True, slots=True)
class AppartementMSD:
    """Un appartement MSD converti, prêt pour :func:`~archlux.api.legalize`.

    Attributes
    ----------
    fusions : tuple of PieceRectilineaire
        À passer tel quel en ``legalize(..., fusions=...)``. Vide si toutes les
        pièces étaient déjà des rectangles.
    angle_redressement : float
        Rotation appliquée, en degrés. La géométrie rendue est **déjà** redressée ;
        cet angle est reporté dans ``contexte.orientation``.
    site_id : str
        Site Swiss Dwellings d'origine. **C'est l'unité de découpage**, jamais
        l'appartement : deux logements d'un même site partagent masque urbain,
        climat et orientation. Voir :func:`decouper_par_site`.
    aires_sources : tuple of str
        ``area_id`` Swiss Dwellings des pièces **avant décomposition**, dans
        l'ordre où elles ont été lues. Clé de jointure vers les simulations.
    """

    identifiant: str
    plan: Plan
    contexte: Contexte
    fusions: tuple[PieceRectilineaire, ...]
    angle_redressement: float
    site_id: str = ""
    aires_sources: tuple[str, ...] = ()


@dataclass(slots=True)
class StatistiquesChargement:
    """Compte des appartements lus, retenus, et des motifs de rejet.

    Un corpus réel se rejette en partie ; publier le taux de rétention **et** sa
    ventilation est ce qui rend l'échantillon d'un article vérifiable.
    """

    lus: int = 0
    retenus: int = 0
    rejets: Counter[str] = field(default_factory=Counter)

    @property
    def taux_retention(self) -> float:
        """Part des appartements lus effectivement convertis, dans ``[0, 1]``."""
        return self.retenus / self.lus if self.lus else 0.0

    def resume(self) -> str:
        """Rendre un résumé lisible, motifs triés par fréquence décroissante."""
        lignes = [f"lus {self.lus}, retenus {self.retenus} ({100.0 * self.taux_retention:.1f} %)"]
        lignes.extend(f"  rejet {motif} : {n}" for motif, n in self.rejets.most_common())
        return "\n".join(lignes)


def _identifiant(valeur: str) -> str:
    """Normaliser un identifiant numérique.

    MSD écrit ``area_id`` en flottant (``484803.0``), Swiss Dwellings en entier
    (``484803``). Sans ce recalage la jointure rend **0 %** au lieu de 99 %.
    """
    texte = str(valeur).strip()
    try:
        return str(int(float(texte)))
    except ValueError:
        return texte


def _angles_et_longueurs(
    polygones: list[Polygon],
) -> tuple[list[float], list[float]]:
    """Angle et longueur de chaque arête, pour estimer la trame."""
    angles: list[float] = []
    longueurs: list[float] = []
    for poly in polygones:
        coords = list(poly.exterior.coords)[:-1]
        for (x0, y0), (x1, y1) in zip(coords, coords[1:] + coords[:1], strict=True):
            longueur = math.hypot(x1 - x0, y1 - y0)
            if longueur <= _EPS:
                continue
            angles.append(math.degrees(math.atan2(y1 - y0, x1 - x0)))
            longueurs.append(longueur)
    return angles, longueurs


def _caler(poly: Polygon, tolerance: float) -> Polygon:
    """Forcer chaque arête quasi axiale à l'être exactement.

    Le calage propage la coordonnée du sommet précédent : il ferme donc le contour
    sans créer d'arête diagonale résiduelle, ce qu'un simple arrondi ne garantit pas.
    """
    coords = [list(point) for point in list(poly.exterior.coords)[:-1]]
    n = len(coords)
    for i in range(n):
        j = (i + 1) % n
        dx = abs(coords[j][0] - coords[i][0])
        dy = abs(coords[j][1] - coords[i][1])
        if dx <= tolerance and dx <= dy:
            coords[j][0] = coords[i][0]
        elif dy <= tolerance:
            coords[j][1] = coords[i][1]
    return Polygon([(float(x), float(y)) for x, y in coords])


def _trame(valeurs: list[float], tolerance: float) -> dict[float, float]:
    """Regrouper des coordonnées proches et rendre le représentant de chaque groupe.

    Balayage croissant : on ouvre un groupe, on y agrège tant que l'écart au
    **précédent** reste sous ``tolerance``, et le représentant est la moyenne du
    groupe. Le regroupement est donc transitif par construction — deux valeurs
    distantes de plus de ``tolerance`` peuvent finir ensemble si une chaîne les
    relie, ce qui est le comportement voulu pour une enfilade de cloisons.
    """
    if not valeurs:
        return {}
    triees = sorted(valeurs)
    groupes: list[list[float]] = [[triees[0]]]
    for valeur in triees[1:]:
        if valeur - groupes[-1][-1] <= tolerance:
            groupes[-1].append(valeur)
        else:
            groupes.append([valeur])
    correspondance: dict[float, float] = {}
    for groupe in groupes:
        representant = sum(groupe) / len(groupe)
        for valeur in groupe:
            correspondance[valeur] = representant
    return correspondance


def _recoller(polygones: list[Polygon], tolerance: float) -> list[Polygon]:
    r"""Recoller les pièces sur une trame commune, pour qu'elles pavent exactement.

    Dans MSD une ``area`` est la surface **intérieure** d'une pièce : les pièces
    voisines sont séparées par l'épaisseur de la cloison (médiane mesurée
    :math:`0{,}209\\,\\mathrm{m}` de mur, :math:`0{,}067\\,\\mathrm{m}` d'écart entre
    pièces ; 1,7 % seulement sont jointives). Le modèle d'``archlux`` suppose au
    contraire des cloisons d'épaisseur nulle et un pavage exact du contour —
    ``certify.preuve`` rejette tout écart d'aire.

    On quantifie donc les abscisses et les ordonnées de tous les sommets de
    l'appartement sur une trame commune : deux bords distants de moins de
    ``tolerance`` deviennent **le même** bord, à mi-chemin. Les pièces se touchent
    alors exactement, et l'épaisseur réelle reste portée par ``Mur.epaisseur``.

    C'est une **transformation du corpus**, pas une correction : elle déplace les
    cloisons d'au plus ``tolerance / 2``. Toute publication doit citer la valeur
    employée et le biais d'aire qu'elle induit.
    """
    xs: list[float] = []
    ys: list[float] = []
    for poly in polygones:
        for x, y in list(poly.exterior.coords)[:-1]:
            xs.append(float(x))
            ys.append(float(y))
    trame_x = _trame(xs, tolerance)
    trame_y = _trame(ys, tolerance)
    recolles: list[Polygon] = []
    for poly in polygones:
        coords = [
            (trame_x[float(x)], trame_y[float(y)]) for x, y in list(poly.exterior.coords)[:-1]
        ]
        # Le recollage peut aplatir une arête : on retire les sommets consécutifs
        # devenus identiques, sinon shapely rend un polygone invalide.
        propres: list[tuple[float, float]] = []
        for point in coords:
            if not propres or point != propres[-1]:
                propres.append(point)
        if len(propres) >= 2 and propres[0] == propres[-1]:
            propres.pop()
        if len(propres) < 4:
            return []
        recolles.append(Polygon(propres))
    return recolles


def _segment_du_mur(poly: Polygon) -> LineString | None:
    """Axe long d'une cloison, depuis son rectangle englobant minimal."""
    rect = poly.minimum_rotated_rectangle
    if not isinstance(rect, Polygon) or rect.is_empty:
        return None
    coords = list(rect.exterior.coords)[:-1]
    if len(coords) != 4:
        return None
    cotes = [
        (math.dist(coords[i], coords[(i + 1) % 4]), coords[i], coords[(i + 1) % 4])
        for i in range(4)
    ]
    cotes.sort(key=lambda c: c[0])
    epaisseur = cotes[0][0]
    if epaisseur > _LARGEUR_MUR_MAX:
        return None
    _, a, b = cotes[-1]
    centre = poly.centroid
    ux = (b[0] - a[0]) / max(math.dist(a, b), _EPS)
    uy = (b[1] - a[1]) / max(math.dist(a, b), _EPS)
    demi = math.dist(a, b) / 2.0
    return LineString(
        [
            (centre.x - demi * ux, centre.y - demi * uy),
            (centre.x + demi * ux, centre.y + demi * uy),
        ]
    )


def _murs_depuis_polygones(polygones: list[Polygon], epaisseurs: list[float]) -> tuple[Mur, ...]:
    """Convertir des cloisons pleines en segments d'axe, identifiants stables."""
    murs: list[Mur] = []
    for rang, (poly, epaisseur) in enumerate(zip(polygones, epaisseurs, strict=True)):
        segment = _segment_du_mur(poly)
        if segment is None or segment.length <= _EPS:
            continue
        (ax, ay), (bx, by) = list(segment.coords)
        murs.append(
            Mur(
                id=f"m{rang:04d}",
                a=(float(ax), float(ay)),
                b=(float(bx), float(by)),
                porteur=False,
                epaisseur=float(epaisseur),
            )
        )
    return tuple(murs)


def _ouverture_depuis_baie(baie: Polygon, murs: tuple[Mur, ...], rang: int) -> Ouverture | None:
    """Projeter une baie sur le mur le plus proche, en coordonnées **relatives**."""
    if not murs:
        return None
    centre = baie.centroid
    meilleur: tuple[float, Mur] | None = None
    for mur in murs:
        distance = LineString([mur.a, mur.b]).distance(centre)
        if meilleur is None or distance < meilleur[0]:
            meilleur = (distance, mur)
    if meilleur is None:
        return None
    _, mur = meilleur
    axe = LineString([mur.a, mur.b])
    longueur = axe.length
    if longueur <= _EPS:
        return None
    s = float(axe.project(Point(centre.x, centre.y)) / longueur)
    largeur = float(baie.minimum_rotated_rectangle.length / 4.0) if baie.area > 0 else 0.0
    # Longueur de la baie = plus grand côté de son rectangle englobant minimal.
    coords = list(baie.minimum_rotated_rectangle.exterior.coords)[:-1]
    if len(coords) == 4:
        largeur = max(math.dist(coords[i], coords[(i + 1) % 4]) for i in range(4))
    largeur_rel = largeur / longueur
    if not 0.0 < largeur_rel <= 1.0 or not 0.0 <= s <= 1.0:
        return None
    return Ouverture(id=f"b{rang:04d}", mur_id=mur.id, s=s, largeur_rel=largeur_rel)


def _contour_simple(pieces: list[Polygon]) -> tuple[tuple[float, float], ...] | None:
    """Anneau extérieur de l'union des pièces, ou ``None`` s'il n'est pas simple.

    Un plan dont l'union est un ``MultiPolygon`` (appartement en deux morceaux) ou
    percée d'un anneau intérieur n'est pas représentable : ``Plan.contour`` est un
    anneau unique, et ``certify.preuve`` compare une aire d'union à l'aire de **ce**
    contour. Boucher le trou en silence fabriquerait un « jour » inexistant.
    """
    union = unary_union(pieces)
    if not isinstance(union, Polygon) or union.is_empty:
        return None
    if list(union.interiors):
        return None
    return tuple((float(x), float(y)) for x, y in list(union.exterior.coords)[:-1])


def _lire_groupes(
    chemin: Path, types_exclus: frozenset[str]
) -> dict[str, list[tuple[str, str, str, str, str]]]:
    """Grouper le CSV par appartement, en ne gardant que les entités utiles.

    Chaque entité est ``(genre, sous_type, wkt, area_id, site_id)``. Les deux
    derniers ne servent pas à la géométrie : ils portent la jointure vers les
    simulations Swiss Dwellings et l'unité de découpage.
    """
    garde = {("separator", "WALL"), ("separator", "COLUMN"), ("opening", "WINDOW")}
    groupes: dict[str, list[tuple[str, str, str, str, str]]] = defaultdict(list)
    with chemin.open(encoding="utf-8", errors="replace", newline="") as flux:
        for ligne in csv.DictReader(flux):
            genre = ligne["entity_type"]
            sous_type = ligne["entity_subtype"]
            if genre == "area":
                if sous_type in types_exclus:
                    continue
            elif (genre, sous_type) not in garde:
                continue
            groupes[ligne["apartment_id"]].append(
                (
                    genre,
                    sous_type,
                    ligne["geom"],
                    _identifiant(ligne.get("area_id", "")),
                    _identifiant(ligne.get("site_id", "")),
                )
            )
    return groupes


def charger_msd(
    chemin: Path | str,
    *,
    referentiel: Referentiel | None = None,
    max_pieces: int = 15,
    max_rectangles: int = 8,
    tolerance_calage: float = 0.05,
    tolerance_recollage: float = 0.20,
    types_exclus: frozenset[str] = TYPES_EXCLUS,
    statistiques: StatistiquesChargement | None = None,
    limite: int | None = None,
) -> Iterator[AppartementMSD]:
    """Convertir le CSV MSD en appartements exploitables par ``archlux``.

    Parameters
    ----------
    chemin : Path or str
        CSV MSD (``mds_V2_*.csv``), colonnes ``apartment_id``, ``entity_type``,
        ``entity_subtype``, ``geom`` (WKT, mètres).
    referentiel : Referentiel or None, optional
        Seuils réglementaires attachés au contexte. ``None`` = ``aires_min=()`` **et**
        ``largeur_min=0``, le cas neutre : MSD ne porte aucune réglementation.

        Ne pas neutraliser ``largeur_min`` est un piège coûteux. Sa valeur par défaut
        (1,80 m) s'applique à **chaque sous-rectangle**, y compris ceux qu'a produits
        la décomposition d'une pièce en L — or un sous-rectangle est un artefact de
        découpe, pas une pièce : une bande de 1,2 m y est parfaitement normale. Le
        plan réel sort alors de son propre polytope, ``legalize`` élargit les bandes
        pour respecter le seuil, le pavage se déchire, et ``certify.preuve`` rejette
        pour « jour ». Mesuré : 87 % d'échecs sur MSD avec le défaut, 0 % sans.
    max_pieces : int, optional
        Plafond de **sous-rectangles** par appartement, après décomposition.
        Défaut 15, la référence des budgets `ARCHITECTURE.md` §9.
    max_rectangles : int, optional
        Plafond par pièce, transmis à
        :func:`~archlux.geom.rectilineaire.decomposer`.
    tolerance_calage : float, optional
        Écart maximal, en mètres, sous lequel une arête est recalée sur un axe.
    tolerance_recollage : float, optional
        Écart maximal, en mètres, sous lequel deux bords de pièces voisines sont
        fusionnés en un seul (voir :func:`_recoller`). Défaut 0,20 m : c'est la valeur
        qui maximise la rétention sur MSD (22 %), l'écart médian mesuré entre pièces
        voisines étant de 0,067 m et l'épaisseur médiane de cloison de 0,209 m.
    types_exclus : frozenset of str, optional
        Sous-types d'``area`` écartés. Voir :data:`TYPES_EXCLUS`.
    statistiques : StatistiquesChargement or None, optional
        Accumulateur renseigné au fil de l'itération : nombre de lus, de retenus et
        ventilation des motifs de rejet.
    limite : int or None, optional
        Arrêter après ce nombre d'appartements **retenus**.

    Yields
    ------
    AppartementMSD
        Plan redressé, contexte, fusions à passer à ``legalize``.

    Raises
    ------
    InvariantViole
        Fichier absent, ou dépourvu des colonnes attendues.

    Notes
    -----
    La géométrie rendue est **exacte au sens du corpus**, pas légalisée : elle peut
    parfaitement violer ``verifier_exactement``. C'est précisément ce qu'un banc
    d'essai doit mesurer avant correction.
    """
    chemin = Path(chemin)
    if not chemin.is_file():
        raise InvariantViole((f"corpus MSD introuvable : {chemin}",))
    stats = statistiques if statistiques is not None else StatistiquesChargement()
    reglement = (
        referentiel if referentiel is not None else Referentiel(aires_min=(), largeur_min=0.0)
    )
    groupes = _lire_groupes(chemin, types_exclus)

    for identifiant, entites in groupes.items():
        stats.lus += 1
        if limite is not None and stats.retenus >= limite:
            return
        resultat = _convertir(
            identifiant,
            entites,
            reglement=reglement,
            max_pieces=max_pieces,
            max_rectangles=max_rectangles,
            tolerance_calage=tolerance_calage,
            tolerance_recollage=tolerance_recollage,
        )
        if isinstance(resultat, str):
            stats.rejets[resultat] += 1
            continue
        stats.retenus += 1
        yield resultat


def _convertir(
    identifiant: str,
    entites: list[tuple[str, str, str, str, str]],
    *,
    reglement: Referentiel,
    max_pieces: int,
    max_rectangles: int,
    tolerance_calage: float,
    tolerance_recollage: float,
) -> AppartementMSD | str:
    """Convertir un appartement, ou rendre le **motif de rejet** en clair."""
    pieces_brutes: list[tuple[str, Polygon]] = []
    aires_sources: list[str] = []
    murs_bruts: list[Polygon] = []
    poteaux_bruts: list[Polygon] = []
    baies_brutes: list[Polygon] = []
    site = next((s for _, _, _, _, s in entites if s), "")
    for genre, sous_type, texte, aire_id, _site in entites:
        try:
            forme = wkt.loads(texte)
        except Exception:  # WKT tiers : tout echec de lecture est un rejet, pas un bug
            return "wkt illisible"
        if not isinstance(forme, Polygon) or forme.is_empty:
            continue
        if genre == "area":
            pieces_brutes.append((sous_type, forme))
            aires_sources.append(aire_id)
        elif sous_type == "WALL":
            murs_bruts.append(forme)
        elif sous_type == "COLUMN":
            poteaux_bruts.append(forme)
        else:
            baies_brutes.append(forme)

    if not pieces_brutes:
        return "aucune piece habitable"
    if len(pieces_brutes) > max_pieces:
        return "trop de pieces avant decomposition"

    angles, longueurs = _angles_et_longueurs(murs_bruts or [forme for _, forme in pieces_brutes])
    if not angles:
        return "aucune arete exploitable"
    try:
        theta = direction_dominante(angles, longueurs, periode=90.0)
    except InvariantViole:
        return "aucune direction dominante"

    def redresser(forme: Polygon) -> Polygon:
        return _caler(affinity.rotate(forme, -theta, origin=(0.0, 0.0)), tolerance_calage)

    redressees = [redresser(forme) for _, forme in pieces_brutes]
    if any(not d.is_valid or d.area <= _EPS for d in redressees):
        return "piece degeneree apres calage"
    # Recoller AVANT de decomposer : la decomposition suppose des bords exacts, et
    # c'est le recollage qui rend les pieces voisines jointives.
    polygones_pieces = _recoller(redressees, tolerance_recollage)
    if not polygones_pieces:
        return "recollage degenere"
    if any(not d.is_valid or d.area <= _EPS for d in polygones_pieces):
        return "piece degeneree apres recollage"

    pieces: list[Piece] = []
    fusions: list[PieceRectilineaire] = []
    for rang, ((sous_type, _), droit) in enumerate(
        zip(pieces_brutes, polygones_pieces, strict=True)
    ):
        try:
            morceau = decomposer(
                droit,
                id=f"p{rang:03d}",
                type_piece=sous_type.lower(),
                max_rectangles=max_rectangles,
            )
        except InvariantViole as echec:
            motif = str(echec.violations[0])
            if "diagonale" in motif:
                return "piece oblique"
            if "trop de rectangles" in motif:
                return "piece trop decoupee"
            return "piece non decomposable"
        pieces.extend(morceau.rectangles)
        if len(morceau.rectangles) > 1:
            fusions.append(morceau)

    if len(pieces) > max_pieces:
        return "trop de sous-rectangles apres decomposition"

    contour = _contour_simple(polygones_pieces)
    if contour is None:
        return "contour non simple"

    murs = _murs_depuis_polygones(
        [redresser(m) for m in murs_bruts],
        [float(m.minimum_rotated_rectangle.length / 4.0) for m in murs_bruts],
    )
    ouvertures = tuple(
        ouv
        for ouv in (
            _ouverture_depuis_baie(redresser(b), murs, rang) for rang, b in enumerate(baies_brutes)
        )
        if ouv is not None
    )
    poteaux = tuple(
        (float(redresser(p).centroid.x), float(redresser(p).centroid.y)) for p in poteaux_bruts
    )

    plan = Plan(pieces=tuple(pieces), murs=murs, ouvertures=ouvertures, contour=contour)
    contexte = Contexte(
        # MSD n'annote pas la portance : aucun mur n'est declare porteur.
        structure=Structure(murs_porteurs=(), poteaux=poteaux),
        orientation=Orientation(deg=theta),
        contour=contour,
        referentiel=reglement,
        programme=tuple(sorted({sous_type.lower() for sous_type, _ in pieces_brutes})),
    )
    return AppartementMSD(
        identifiant=identifiant,
        plan=plan,
        contexte=contexte,
        site_id=site,
        aires_sources=tuple(aires_sources),
        fusions=tuple(fusions),
        angle_redressement=theta,
    )


# ======================================================================================
# Etiquettes Swiss Dwellings
# ======================================================================================


def _flux_simulations(chemin: Path) -> Iterator[dict[str, str]]:
    """Lire ``simulations.csv``, depuis le zip Zenodo ou depuis le CSV nu."""
    if chemin.suffix.lower() == ".zip":
        with zipfile.ZipFile(chemin) as archive:
            noms = [nom for nom in archive.namelist() if nom.lower().endswith("simulations.csv")]
            if not noms:
                raise InvariantViole((f"pas de simulations.csv dans {chemin}",))
            with archive.open(noms[0]) as brut:
                enveloppe = io.TextIOWrapper(brut, encoding="utf-8", errors="replace", newline="")
                yield from csv.DictReader(enveloppe)
        return
    with chemin.open(encoding="utf-8", errors="replace", newline="") as fichier:
        yield from csv.DictReader(fichier)


def charger_etiquettes_sd(
    chemin: Path | str, *, colonne: str = COLONNE_SOLEIL_DEFAUT
) -> dict[tuple[str, str], tuple[float, float]]:
    """Lire les simulations Swiss Dwellings, indexées par ``(appartement, pièce)``.

    Parameters
    ----------
    chemin : Path or str
        ``swiss-dwellings-v3.0.0.zip`` tel que téléchargé depuis Zenodo, ou le
        ``simulations.csv`` extrait.
    colonne : str, optional
        Colonne d'irradiance à retenir. Voir :data:`COLONNE_SOLEIL_DEFAUT` — et son
        avertissement : **ce n'est pas un sDA**.

    Returns
    -------
    dict
        ``(apartment_id, area_id) -> (valeur, surface)``. La surface vient de
        ``layout_area`` et sert à pondérer l'agrégation par appartement.

    Raises
    ------
    InvariantViole
        Fichier absent, archive sans ``simulations.csv``, ou colonne inconnue.

    Notes
    -----
    Les ``area_id`` sont normalisés : MSD les écrit en flottant, Swiss Dwellings en
    entier. Sans ce recalage la jointure rend 0 %.
    """
    chemin = Path(chemin)
    if not chemin.is_file():
        raise InvariantViole((f"simulations introuvables : {chemin}",))
    table: dict[tuple[str, str], tuple[float, float]] = {}
    connue = False
    for ligne in _flux_simulations(chemin):
        if not connue:
            if colonne not in ligne:
                raise InvariantViole((f"colonne {colonne!r} absente des simulations",))
            connue = True
        try:
            valeur = float(ligne[colonne])
            surface = float(ligne.get("layout_area") or 0.0)
        except (TypeError, ValueError):
            continue
        table[(ligne["apartment_id"], _identifiant(ligne["area_id"]))] = (
            valeur,
            surface,
        )
    if not table:
        raise InvariantViole((f"aucune simulation lue dans {chemin}",))
    return table


def etiqueter(
    appartement: AppartementMSD,
    etiquettes: dict[tuple[str, str], tuple[float, float]],
    *,
    couverture_min: float = 1.0,
) -> float | None:
    """Agréger l'irradiance des pièces d'un appartement, pondérée par surface.

    Parameters
    ----------
    appartement : AppartementMSD
        Doit porter ``aires_sources`` — les ``area_id`` d'avant décomposition.
    etiquettes : dict
        Table rendue par :func:`charger_etiquettes_sd`.
    couverture_min : float, optional
        Part minimale des pièces devant être appariée. Défaut ``1.0`` : **toutes**.
        Un appartement partiellement simulé donne une moyenne portant sur un
        sous-ensemble choisi par la disponibilité des données, pas par le hasard —
        l'accepter introduirait un biais silencieux dans la cible.

    Returns
    -------
    float or None
        Moyenne pondérée, ou ``None`` si la couverture est insuffisante ou si les
        surfaces appariées sont toutes nulles.

    Notes
    -----
    Les locaux techniques — gaines, cages, ascenseurs — n'ont **aucune** simulation :
    ils n'ont pas de lumière à simuler. Ils sont déjà écartés par
    :data:`TYPES_EXCLUS` en amont, si bien que la couverture porte sur les seules
    pièces habitables, appariées à 98–99,5 % selon le type.
    """
    if not appartement.aires_sources:
        return None
    trouvees = [
        etiquettes[(appartement.identifiant, aire)]
        for aire in appartement.aires_sources
        if (appartement.identifiant, aire) in etiquettes
    ]
    couverture = len(trouvees) / len(appartement.aires_sources)
    if couverture < couverture_min or not trouvees:
        return None
    poids = np.array([surface for _, surface in trouvees], dtype=float)
    valeurs = np.array([valeur for valeur, _ in trouvees], dtype=float)
    if float(poids.sum()) <= 0.0:
        return None
    return float(np.average(valeurs, weights=poids))


def decouper_par_site(
    appartements: Sequence[AppartementMSD],
    *,
    seed: int,
    parts: tuple[float, float, float] = (0.6, 0.2, 0.2),
) -> tuple[list[AppartementMSD], list[AppartementMSD], list[AppartementMSD]]:
    """Découper en entraînement / calibration / test **par site**, jamais par plan.

    Deux appartements d'un même site partagent masque urbain, climat et
    orientation. Les répartir au hasard ferait fuiter cette information entre
    entraînement et calibration : la couverture conforme annoncée serait alors
    trop optimiste, et **rien ne le signalerait** — l'erreur silencieuse que
    `ARCHITECTURE.md` §10 déclare fatale. Le découpage porte donc sur ``site_id``.

    Parameters
    ----------
    appartements : sequence of AppartementMSD
        Corpus à découper. Ceux sans ``site_id`` sont refusés plutôt que rangés
        dans un site fictif commun, qui serait la fuite qu'on cherche à éviter.
    seed : int
        Graine, **obligatoire et sans défaut** (`ARCHITECTURE.md` §7).
    parts : tuple of float, optional
        Proportions visées, en **sites**. Le compte d'appartements s'en écarte,
        les sites n'ayant pas tous la même taille.

    Returns
    -------
    tuple
        ``(entrainement, calibration, test)``.

    Raises
    ------
    InvariantViole
        ``site_id`` manquant, proportions non positives, ou moins de trois sites.
    """
    if not appartements:
        raise InvariantViole(("corpus vide : rien a decouper",))
    if any(not a.site_id for a in appartements):
        raise InvariantViole(("site_id manquant : decoupage impossible",))
    if any(p <= 0.0 for p in parts) or abs(sum(parts) - 1.0) > 1e-9:
        raise InvariantViole((f"parts invalides : {parts}",))
    sites = sorted({a.site_id for a in appartements})
    if len(sites) < 3:
        raise InvariantViole((f"{len(sites)} site(s) : decoupage en trois impossible",))
    rng = np.random.default_rng(seed)
    ordre = rng.permutation(len(sites))
    melanges = [sites[int(i)] for i in ordre]
    n_train = max(1, round(parts[0] * len(melanges)))
    n_cal = max(1, round(parts[1] * len(melanges)))
    n_cal = min(n_cal, len(melanges) - n_train - 1)
    attribution = {s: 0 for s in melanges[:n_train]}
    debut_test = n_train + n_cal
    attribution.update({s: 1 for s in melanges[n_train:debut_test]})
    attribution.update({s: 2 for s in melanges[debut_test:]})
    lots: tuple[list[AppartementMSD], list[AppartementMSD], list[AppartementMSD]] = (
        [],
        [],
        [],
    )
    for appartement in appartements:
        lots[attribution[appartement.site_id]].append(appartement)
    return lots
