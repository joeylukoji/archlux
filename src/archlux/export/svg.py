"""Rendu SVG d'un plan — pour **regarder** ce que la correction a fait.

Pourquoi ce module existe
-------------------------
Un taux de réparation ne dit pas à quoi ressemble une réparation. « plan certifié
valide » et « déplacement médian de 43 % du côté » sont deux énoncés justes qui,
seuls, laissent croire à des choses opposées. Les regarder côte à côte tranche en
une seconde ce qu'un tableau met une page à suggérer.

C'est ainsi qu'a été trouvé le défaut le plus grave du jalon 8 : des pièces réduites
à une épaisseur nulle par la correction. Aucune table ne le montrait — le compte de
pièces restait juste — et une seule figure a suffi.

Le format est du SVG écrit à la main : aucune dépendance ajoutée — ``export`` ne
peut importer que ``types`` et ``erreurs`` —, une sortie vectorielle lisible dans
n'importe quel navigateur, et un texte que ``git diff`` sait comparer.

Ce que le rendu montre, et pourquoi
-----------------------------------
- Les pièces sont **semi-transparentes** : un chevauchement se voit comme une zone
  plus dense, sans qu'aucun calcul ne l'annote.
- Un **jour** se lit comme du fond resté visible à l'intérieur du contour.
- Le contour visé est tracé en tirets, même quand aucune pièce ne l'atteint.
- :func:`comparer` impose **une seule échelle aux deux panneaux**. Deux plans
  rendus chacun à sa propre échelle donneraient à un plan rétréci l'air d'un plan
  intact : c'est l'erreur que cette contrainte interdit.

Ce module ne mesure rien et ne prouve rien : voir
:mod:`archlux.geom.diagnostic` et :mod:`archlux.certify.preuve`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from archlux.types import Mur, Plan, Point

__all__ = ["comparer", "planche", "rendre"]

_MARGE = 28.0
_LARGEUR_PANNEAU = 380.0
_ESPACE = 12.0

# Teintes par type de pièce. Un type inconnu retombe sur le gris : inventer une
# couleur par hachage rendrait deux corpus incomparables d'un rendu à l'autre.
_TEINTES = {
    "living": "#c8d9ec",
    "living_room": "#c8d9ec",
    "living_dining": "#c3d6ea",
    "salon": "#c8d9ec",
    "sejour": "#c8d9ec",
    "kitchen": "#e8d9bd",
    "cuisine": "#e8d9bd",
    "kitchen_dining": "#e5d5b8",
    "bedroom": "#d6e0cd",
    "chambre": "#d6e0cd",
    "room": "#d9e2d1",
    "bathroom": "#d5dfe6",
    "sdb": "#d5dfe6",
    "hallway": "#e4e0d8",
    "corridor": "#e4e0d8",
    "couloir": "#e4e0d8",
    "dining": "#ded4e2",
    "office": "#dcdce6",
    "storage": "#e0dcd6",
    "storeroom": "#e0dcd6",
}
_GRIS = "#dcdcdc"


def _echapper(texte: str) -> str:
    """Neutraliser les cinq caractères que XML ne tolère pas dans un nœud texte."""
    for brut, entite in (
        ("&", "&amp;"),
        ("<", "&lt;"),
        (">", "&gt;"),
        ('"', "&quot;"),
        ("'", "&apos;"),
    ):
        texte = texte.replace(brut, entite)
    return texte


def _etendue(
    plans: tuple[Plan, ...], contours: tuple[tuple[Point, ...], ...]
) -> tuple[float, float, float, float]:
    """Boîte englobante commune, en mètres. Vide si rien n'est traçable."""
    xs: list[float] = []
    ys: list[float] = []
    for plan in plans:
        for piece in plan.pieces:
            xs.extend((piece.x, piece.x + piece.w))
            ys.extend((piece.y, piece.y + piece.h))
    for contour in contours:
        xs.extend(point[0] for point in contour)
        ys.extend(point[1] for point in contour)
    if not xs:
        return (0.0, 0.0, 1.0, 1.0)
    return (min(xs), min(ys), max(xs), max(ys))


def _panneau(
    plan: Plan,
    contour: tuple[Point, ...],
    titre: str,
    etendue: tuple[float, float, float, float],
    decalage_x: float,
    decalage_y: float = 0.0,
    walls: tuple[Mur, ...] = (),
) -> list[str]:
    """Un panneau : cadre, contour en tirets, pièces, murs, titre. Coordonnées SVG.

    Load-bearing walls are drawn thick and dark (class ``wall-load-bearing``), other
    walls thin and grey (class ``wall``).
    """
    x0, y0, x1, y1 = etendue
    largeur_m = max(x1 - x0, 1e-9)
    hauteur_m = max(y1 - y0, 1e-9)
    utile = _LARGEUR_PANNEAU - 2 * _MARGE
    echelle = min(utile / largeur_m, utile / hauteur_m)
    hauteur_px = hauteur_m * echelle + 2 * _MARGE

    def vers_svg(x: float, y: float) -> tuple[float, float]:
        # L'axe y du SVG descend ; celui d'un plan monte. Sans ce retournement le
        # rendu serait le miroir du plan certifié.
        return (
            decalage_x + _MARGE + (x - x0) * echelle,
            decalage_y + _MARGE + (y1 - y) * echelle,
        )

    parties = [
        f'<rect x="{decalage_x + 1:.1f}" y="{decalage_y + 1:.1f}" '
        f'width="{_LARGEUR_PANNEAU - 2:.1f}" height="{hauteur_px - 2:.1f}" '
        'fill="#ffffff" stroke="#c9c9c9" stroke-width="1"/>',
        f'<text x="{decalage_x + _MARGE:.1f}" y="{decalage_y + 18:.1f}" '
        'font-family="system-ui,sans-serif" '
        f'font-size="13" font-weight="600" fill="#333">{_echapper(titre)}</text>',
    ]

    if contour:
        points = " ".join(
            f"{x:.2f},{y:.2f}" for x, y in map(lambda p: vers_svg(p[0], p[1]), contour)
        )
        parties.append(
            f'<polygon points="{points}" fill="none" stroke="#b04a4a" '
            'stroke-width="1.4" stroke-dasharray="6 4"/>'
        )

    for piece in plan.pieces:
        coin_x, coin_y = vers_svg(piece.x, piece.y + piece.h)
        teinte = _TEINTES.get(piece.type.lower(), _GRIS)
        parties.append(
            f'<rect x="{coin_x:.2f}" y="{coin_y:.2f}" '
            f'width="{piece.w * echelle:.2f}" height="{piece.h * echelle:.2f}" '
            f'fill="{teinte}" fill-opacity="0.55" stroke="#4a4a4a" '
            'stroke-width="1"/>'
        )
        centre_x, centre_y = vers_svg(piece.x + piece.w / 2, piece.y + piece.h / 2)
        parties.append(
            f'<text x="{centre_x:.2f}" y="{centre_y:.2f}" text-anchor="middle" '
            'font-family="system-ui,sans-serif" font-size="9" fill="#2a2a2a">'
            f"{_echapper(piece.type[:12])}</text>"
        )

    # Walls last, on top of rooms: a load-bearing wall crossed by a room must be visible.
    declared = {wall.id for wall in plan.murs}
    for wall in plan.murs + tuple(w for w in walls if w.id not in declared):
        (xa, ya), (xb, yb) = vers_svg(*wall.a), vers_svg(*wall.b)
        css_class, colour, width = (
            ("wall-load-bearing", "#1f1f1f", 4.0) if wall.porteur else ("wall", "#6b6b6b", 1.5)
        )
        parties.append(
            f'<line class="{css_class}" x1="{xa:.2f}" y1="{ya:.2f}" x2="{xb:.2f}" '
            f'y2="{yb:.2f}" stroke="{colour}" stroke-width="{width}" '
            'stroke-linecap="square"/>'
        )
    return parties


def rendre(
    plan: Plan,
    *,
    contour: tuple[Point, ...] = (),
    titre: str = "",
    walls: tuple[Mur, ...] = (),
) -> str:
    """Rendre un plan en SVG autonome.

    Parameters
    ----------
    plan : Plan
        Plan à tracer. Peut être invalide — c'est le cas d'usage.
    contour : tuple of Point, optional
        Contour visé, tracé en tirets. Défaut : celui du plan.
    titre : str, optional
        Libellé porté en haut du panneau.
    walls : tuple of Mur, optional
        Extra walls to draw, typically ``ctx.structure.murs_porteurs``: a plan does not
        have to repeat its load-bearing structure, but a drawing should show it.

    Returns
    -------
    str
        Document SVG complet, encodable tel quel en UTF-8.

    Examples
    --------
    >>> from archlux.types import Piece, Plan
    >>> plan = Plan(
    ...     pieces=(Piece(id="a", type="salon", x=0.0, y=0.0, w=3.0, h=2.0),),
    ...     murs=(), ouvertures=(), contour=(),
    ... )
    >>> rendre(plan, titre="essai").startswith("<svg")
    True
    """
    vise = contour or plan.contour
    etendue = _etendue((plan,), (vise,) if vise else ())
    parties = _panneau(plan, vise, titre, etendue, 0.0, walls=walls)
    hauteur = _hauteur(etendue)
    return _document(_LARGEUR_PANNEAU, hauteur, parties)


def comparer(
    avant: Plan,
    apres: Plan,
    *,
    contour: tuple[Point, ...] = (),
    titres: tuple[str, str] = ("avant", "après"),
    walls: tuple[Mur, ...] = (),
) -> str:
    """Rendre deux plans côte à côte, **à la même échelle**.

    Parameters
    ----------
    avant, apres : Plan
        Les deux états à comparer.
    contour : tuple of Point, optional
        Contour visé, commun aux deux panneaux. Défaut : celui d'``avant``.
    titres : tuple of str, optional
        Libellés des deux panneaux.
    walls : tuple of Mur, optional
        Extra walls drawn in both panels (see :func:`rendre`).

    Returns
    -------
    str
        Document SVG complet.

    Notes
    -----
    L'échelle est calculée sur l'union des deux étendues, jamais panneau par
    panneau : un plan rétréci doit **paraître** rétréci.

    Examples
    --------
    >>> from archlux.types import Piece, Plan
    >>> a = Plan(pieces=(Piece(id="p", type="salon", x=0.0, y=0.0, w=4.0, h=3.0),),
    ...          murs=(), ouvertures=(), contour=())
    >>> b = Plan(pieces=(Piece(id="p", type="salon", x=0.0, y=0.0, w=2.0, h=3.0),),
    ...          murs=(), ouvertures=(), contour=())
    >>> svg = comparer(a, b)
    >>> svg.count("<rect") >= 4        # deux cadres, deux pièces
    True
    """
    return planche(((avant, titres[0]), (apres, titres[1])), contour=contour, walls=walls)


def planche(
    volets: tuple[tuple[Plan, str], ...],
    *,
    contour: tuple[Point, ...] = (),
    colonnes: int = 4,
    walls: tuple[Mur, ...] = (),
) -> str:
    """Rendre une **série** de variantes en grille, toutes à la même échelle.

    Parameters
    ----------
    volets : tuple of (Plan, str)
        Les variantes et leur légende, dans l'ordre d'affichage.
    contour : tuple of Point, optional
        Contour visé, commun à tous les volets. Défaut : celui du premier plan.
    colonnes : int, optional
        Volets par rangée.
    walls : tuple of Mur, optional
        Extra walls drawn in every panel (see :func:`rendre`).

    Returns
    -------
    str
        Document SVG complet.

    Raises
    ------
    ValueError
        Série vide : il n'y a rien à tracer, et rendre un document vide
        masquerait l'erreur en amont.

    Notes
    -----
    Conçu pour les balayages — une variante par azimut solaire, par exemple. Une
    échelle unique pour toute la planche est ce qui rend la série lisible : sinon
    chaque volet se recadre sur lui-même et les déplacements deviennent invisibles.

    Examples
    --------
    >>> from archlux.types import Piece, Plan
    >>> plans = tuple(
    ...     (Plan(pieces=(Piece(id="p", type="salon", x=float(k), y=0.0,
    ...                        w=3.0, h=2.0),),
    ...           murs=(), ouvertures=(), contour=()), f"{k}°")
    ...     for k in range(3)
    ... )
    >>> planche(plans, colonnes=2).startswith("<svg")
    True
    """
    if not volets:
        raise ValueError("planche vide : rien à tracer")
    vise = contour or volets[0][0].contour
    etendue = _etendue(tuple(p for p, _ in volets), (vise,) if vise else ())
    pas_x = _LARGEUR_PANNEAU + _ESPACE
    pas_y = _hauteur(etendue) + _ESPACE

    parties: list[str] = []
    for rang, (plan, titre) in enumerate(volets):
        colonne, rangee = rang % colonnes, rang // colonnes
        parties += _panneau(
            plan, vise, titre, etendue, colonne * pas_x, rangee * pas_y, walls=walls
        )
    n_colonnes = min(len(volets), colonnes)
    n_rangees = (len(volets) + colonnes - 1) // colonnes
    return _document(n_colonnes * pas_x - _ESPACE, n_rangees * pas_y - _ESPACE, parties)


def _hauteur(etendue: tuple[float, float, float, float]) -> float:
    """Hauteur du document, en pixels, pour une étendue métrique donnée."""
    x0, y0, x1, y1 = etendue
    largeur_m = max(x1 - x0, 1e-9)
    hauteur_m = max(y1 - y0, 1e-9)
    utile = _LARGEUR_PANNEAU - 2 * _MARGE
    return hauteur_m * min(utile / largeur_m, utile / hauteur_m) + 2 * _MARGE


def _document(largeur: float, hauteur: float, parties: list[str]) -> str:
    """Envelopper les fragments dans un document SVG autonome."""
    corps = "\n  ".join(parties)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{largeur:.0f}" '
        f'height="{hauteur:.0f}" viewBox="0 0 {largeur:.0f} {hauteur:.0f}">\n'
        f'  <rect width="{largeur:.0f}" height="{hauteur:.0f}" fill="#f7f6f3"/>\n'
        f"  {corps}\n</svg>\n"
    )
