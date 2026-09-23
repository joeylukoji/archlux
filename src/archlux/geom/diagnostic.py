"""Quantifier **comment** un plan est invalide, et pas seulement s'il l'est.

Pourquoi ce module existe
-------------------------
:func:`~archlux.certify.preuve.verifier_exactement` rend un verdict et nomme les
violations. C'est ce qu'il faut pour certifier ; ce n'est pas ce qu'il faut pour
**caractériser un corpus d'entrées**. « invalide » ne distingue pas un plan dont
une cloison a glissé de deux centimètres d'un plan dont les pièces flottent en
archipel — or ces deux régimes n'appellent pas la même correction, et la seconde
n'est pas réparable au même coût.

Les cinq mesures rendues ici sont celles qui décident si
:func:`~archlux.api.legalize` a une chance :

- ``recouvrements`` — combien de pièces chaque pièce en recouvre, en moyenne.
  C'est la grandeur que les auteurs de MSD rapportent pour leur propre baseline
  (4,11 ± 2,25), donc la seule directement comparable à la littérature.
- ``part_jour`` — part de la boîte englobante que l'union ne couvre pas.
- ``part_trou`` — part occupée par des trous **intérieurs** à l'union. Séparer
  les deux est indispensable : un jour de bord n'est peut-être qu'une emprise non
  rectangulaire, alors qu'un trou intérieur est un défaut sans ambiguïté.
- ``morceaux`` — nombre de composantes connexes. Au-delà de 1, l'« appartement »
  est un archipel, et aucune trame ne le rattrapera à budget raisonnable. Deux
  pièces qui ne se touchent **que par un coin** comptent pour deux morceaux :
  un coin partagé n'est ni un mur mitoyen ni un passage, et pour le pavage il
  reste un jour.
- ``cellules`` — taille de la trame implicite, ``(|X| - 1) × (|Y| - 1)`` sur les
  lignes portées par les bords. Dans un plan réel les pièces partagent leurs
  murs et ce nombre reste petit ; s'il explose, c'est que la structure
  combinatoire du pavage **n'existe pas** — voir :mod:`archlux.geom.pavage`.

Aucune de ces grandeurs n'est une garantie : ce module décrit, il ne prouve rien.
La preuve reste dans ``certify``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from shapely.geometry import MultiPolygon, Polygon, box
from shapely.ops import unary_union

if TYPE_CHECKING:
    from archlux.types import Plan

__all__ = ["Diagnostic", "diagnostiquer"]

_AIRE_MIN = 1e-6


@dataclass(frozen=True, slots=True)
class Diagnostic:
    """Portrait chiffré d'un plan proposé. Aucune de ces valeurs n'est une preuve.

    Attributes
    ----------
    recouvrements : float
        Nombre moyen de pièces recouvertes par une pièce. ``0.0`` si aucune paire
        ne se recouvre.
    part_jour : float
        Part de la boîte englobante non couverte, dans ``[0, 1]``.
    part_trou : float
        Part occupée par des trous **intérieurs** à l'union, dans ``[0, 1]``.
        Toujours ``<= part_jour``.
    morceaux : int
        Composantes connexes de l'union. ``1`` pour un plan d'un seul tenant.
    cellules : int
        Cardinal de la trame implicite portée par les bords des pièces.
    cote : float
        Côté caractéristique, ``sqrt(aire de la boîte englobante)``, en mètres.
        Un déplacement en mètres ne se lit pas sans lui.
    """

    recouvrements: float
    part_jour: float
    part_trou: float
    morceaux: int
    cellules: int
    cote: float


def diagnostiquer(plan: Plan) -> Diagnostic:
    """Mesurer les cinq pathologies d'un plan proposé.

    Parameters
    ----------
    plan : Plan
        Plan à décrire. Peut être invalide — c'est le cas d'usage.

    Returns
    -------
    Diagnostic
        Le portrait chiffré. Voir :class:`Diagnostic` pour chaque champ.

    Raises
    ------
    ValueError
        Le plan ne porte aucune pièce : il n'y a rien à décrire, et rendre des
        zéros laisserait croire à un plan sain.

    Notes
    -----
    Le contour de ``ctx`` n'est **pas** consulté : les mesures portent sur la
    boîte englobante de l'union, afin de rester comparables entre des plans dont
    les contours sont fixés différemment.

    Complexity
    ----------
    O(n²) sur le nombre de pièces, pour le comptage des recouvrements. n est une
    dizaine en pratique.

    Examples
    --------
    Deux pièces jointives pavant exactement leur boîte englobante :

    >>> from archlux.types import Piece, Plan
    >>> plan = Plan(
    ...     pieces=(
    ...         Piece(id="a", type="salon", x=0.0, y=0.0, w=3.0, h=2.0),
    ...         Piece(id="b", type="cuisine", x=3.0, y=0.0, w=2.0, h=2.0),
    ...     ),
    ...     murs=(), ouvertures=(), contour=(),
    ... )
    >>> diag = diagnostiquer(plan)
    >>> diag.recouvrements, diag.part_jour, diag.morceaux, diag.cellules
    (0.0, 0.0, 1, 2)

    Écarter la seconde pièce ouvre un jour et coupe le plan en deux :

    >>> troue = Plan(
    ...     pieces=(plan.pieces[0], Piece(
    ...         id="b", type="cuisine", x=4.0, y=0.0, w=2.0, h=2.0)),
    ...     murs=(), ouvertures=(), contour=(),
    ... )
    >>> diag = diagnostiquer(troue)
    >>> round(diag.part_jour, 3), diag.morceaux
    (0.167, 2)
    """
    if not plan.pieces:
        raise ValueError("plan sans pièce : rien à diagnostiquer")

    formes = [box(p.x, p.y, p.x + p.w, p.y + p.h) for p in plan.pieces]
    n = len(formes)
    recouvrements = sum(
        1
        for i in range(n)
        for j in range(n)
        if i != j and formes[i].intersection(formes[j]).area > _AIRE_MIN
    ) / n

    union = unary_union(formes)
    x0, y0, x1, y1 = union.bounds
    aire_boite = (x1 - x0) * (y1 - y0)
    parts = list(union.geoms) if isinstance(union, MultiPolygon) else [union]
    aire_trous = sum(
        Polygon(anneau).area for forme in parts for anneau in forme.interiors
    )

    lignes_x = {p.x for p in plan.pieces} | {p.x + p.w for p in plan.pieces}
    lignes_y = {p.y for p in plan.pieces} | {p.y + p.h for p in plan.pieces}

    return Diagnostic(
        recouvrements=float(recouvrements),
        part_jour=float(1.0 - union.area / aire_boite) if aire_boite > 0 else 0.0,
        part_trou=float(aire_trous / aire_boite) if aire_boite > 0 else 0.0,
        morceaux=len(parts),
        cellules=(len(lignes_x) - 1) * (len(lignes_y) - 1),
        cote=math.sqrt(aire_boite),
    )
