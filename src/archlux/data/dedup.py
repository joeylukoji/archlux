"""Empreinte géométrique et distance de Hausdorff — dédupliquer avant de découper."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from shapely.geometry import box
from shapely.ops import unary_union

if TYPE_CHECKING:
    from collections.abc import Sequence

    from archlux.types import Plan

__all__ = [
    "SEUIL_HAUSDORFF_M",
    "distance_cotes",
    "empreinte_geometrique",
    "hausdorff",
    "paires_quasi_identiques",
]

SEUIL_HAUSDORFF_M = 0.02
"""Seuil en mètres : deux pavages plus proches sont le même logement (`MILESTONE-4.md`)."""


def empreinte_geometrique(plan: Plan) -> str:
    """Hacher le pavage arrondi au millimètre, pièces triées par identifiant."""
    pieces = tuple(
        (
            p.id,
            p.type,
            round(p.x, 3),
            round(p.y, 3),
            round(p.w, 3),
            round(p.h, 3),
        )
        for p in sorted(plan.pieces, key=lambda piece: piece.id)
    )
    return hashlib.blake2b(repr(pieces).encode(), digest_size=16).hexdigest()


def distance_cotes(a: Plan, b: Plan) -> float:
    """Écart L-infini des cotes, pièces appariées par identifiant.

    La Hausdorff des *unions* est nulle pour deux pavages du même contour :
    elle ne détecte pas un doublon de partition. C'est l'écart des rectangles
    qui compte pour dédupliquer avant de découper.
    """
    gauche = {p.id: p for p in a.pieces}
    droite = {p.id: p for p in b.pieces}
    if gauche.keys() != droite.keys():
        return hausdorff(a, b)
    if not gauche:
        # Deux pavages vides sont identiques ; ``max`` sur un vide lèverait un
        # ``ValueError`` nu, hors du domaine d'erreurs du projet (§7).
        return 0.0
    return max(
        max(
            abs(gauche[i].x - droite[i].x),
            abs(gauche[i].y - droite[i].y),
            abs(gauche[i].w - droite[i].w),
            abs(gauche[i].h - droite[i].h),
        )
        for i in gauche
    )


def hausdorff(a: Plan, b: Plan) -> float:
    """Distance de Hausdorff entre les unions de rectangles, en mètres."""
    ua = unary_union([box(p.x, p.y, p.x + p.w, p.y + p.h) for p in a.pieces])
    ub = unary_union([box(p.x, p.y, p.x + p.w, p.y + p.h) for p in b.pieces])
    return float(ua.hausdorff_distance(ub))


def paires_quasi_identiques(
    plans: Sequence[tuple[str, Plan]], *, seuil: float = SEUIL_HAUSDORFF_M
) -> tuple[tuple[str, str], ...]:
    """Paires d'identifiants dont l'écart de cotes est sous ``seuil``.

    La relation « écart ≤ seuil » n'est **pas transitive** : ``a ~ b`` et ``b ~ c``
    n'impliquent pas ``a ~ c``. Cette fonction rend donc les arêtes du graphe de
    similarité, jamais des classes. Un appelant qui déduplique doit fermer ces arêtes
    en composantes connexes (union-find) avant de découper, sinon deux membres d'une
    même chaîne peuvent atterrir de part et d'autre d'une frontière train/test.

    Complexity
    ----------
    ``O(n²)`` comparaisons ; les empreintes sont calculées **une fois par plan**
    (``O(n)``) et non par paire.
    """
    empreintes = [empreinte_geometrique(plan) for _, plan in plans]
    paires: list[tuple[str, str]] = []
    for i, (ida, pa) in enumerate(plans):
        for decalage, (idb, pb) in enumerate(plans[i + 1 :]):
            j = i + 1 + decalage
            if empreintes[i] == empreintes[j] or distance_cotes(pa, pb) <= seuil:
                paires.append((ida, idb) if ida < idb else (idb, ida))
    return tuple(paires)
