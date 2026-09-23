r"""Vérification exacte, **indépendante du solveur**.

Formule
=======
Quatre prédicats booléens, conjonction pour ``valide``. Aucun n'est probabiliste.

Chevauchement
-------------
Pour deux rectangles :math:`R_i, R_j`, l'aire d'intersection
:math:`|R_i \\cap R_j|` (GEOS / Shapely, algorithme de clipping de Vatti /
plan de Balaban ; complexité :math:`O(n^2)` paires, assumée). Chevauchement
ssi :math:`|R_i \\cap R_j| > 0` au-delà de la tolérance numérique.

Jours
-----
Soit :math:`U = \\bigcup_i R_i` et :math:`C` le polygone du contour. Un pavage exact
vérifie :math:`U = C` à mesure nulle près, ce qui se teste par les **deux** différences
ensemblistes :

.. math::

    \\lambda(C \\setminus U) > \\tau \\quad\\text{(jour)}, \\qquad
    \\lambda(U \\setminus C) > \\tau \\quad\\text{(débord)}, \\qquad
    \\tau = 10^{-6}\\,\\mathrm{m}^2.

L'identité d'aires :math:`|\\lambda(U) - \\lambda(C)| > \\tau` **ne suffit pas** :
un jour de :math:`a` m² compensé par un débord de :math:`a` m² hors du contour laisse
les aires égales et passerait le contrôle. Les différences ensemblistes le refusent.
Complétée par :math:`\\lambda(R_i \\cap R_j)=0` pour :math:`i \\ne j`, la conjonction
caractérise bien un pavage de :math:`C`.

Surfaces
--------
:math:`w_p h_p \\ge a_{\\min}(\\mathrm{type}(p))` pour chaque pièce.

Structure
---------
Chaque mur porteur de :math:`\\mathrm{ctx}` apparaît dans le plan, identifié par
``id``, avec les mêmes extrémités (tolérance métrique).

Déplacement
-----------
:math:`\\delta_\\infty = \\max_p \\max\\bigl(|\\Delta x|,|\\Delta y|,|\\Delta w|,|\\Delta h|\\bigr)`
en mètres, par rapport au plan de référence.

Dérivation, tolérances et cas d'usage : ``docs/formules/preuve-exacte.md``.
"""

from __future__ import annotations

from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from archlux.types import Contexte, Mur, Piece, Plan, PreuveGeometrique

__all__ = ["verifier_exactement"]

TOLERANCE_JOUR_M2 = 1e-6
"""Tolérance de surface pour la détection des jours, en mètres carrés."""

_TOLERANCE_MUR_M = 1e-7
_TOLERANCE_AIRE_M2 = 1e-9


def _formater_m2(valeur: float) -> str:
    """Rendre une aire avec virgule décimale française."""
    return f"{valeur:.2f}".replace(".", ",") + " m²"


def _rectangle(piece: Piece) -> Polygon:
    """Rectangle fermé de la pièce, coin bas-gauche + (w, h)."""
    return box(piece.x, piece.y, piece.x + piece.w, piece.y + piece.h)


def _polygone_contour(contour: tuple[tuple[float, float], ...]) -> Polygon | None:
    """Polygone du contour, ou ``None`` s'il est dégénéré."""
    if len(contour) < 3:
        return None
    polygone = Polygon(contour)
    if not polygone.is_valid or polygone.area <= 0.0:
        return None
    return polygone


def _disjoints(a: Piece, b: Piece) -> bool:
    """Rejet exact de deux rectangles à axes alignés, sans passer par GEOS.

    Les pièces sont des boîtes : si leurs intervalles se séparent sur ``x`` ou sur
    ``y``, l'aire d'intersection est **exactement** nulle. Ce test purement
    arithmétique évite l'appel shapely sur la grande majorité des paires, ce qui tient
    le budget de certification du §9 sans rien changer au résultat.
    """
    return (
        a.x + a.w <= b.x or b.x + b.w <= a.x or a.y + a.h <= b.y or b.y + b.h <= a.y
    )


def _chevauchements(pieces: tuple[Piece, ...]) -> tuple[bool, tuple[str, ...]]:
    """Toutes les paires, aire d'intersection.

    La tolérance est ``_TOLERANCE_AIRE_M2 = 1e-9 m²`` : deux pièces qui se touchent par
    une arête ont une intersection d'aire nulle et ne sont pas signalées, alors qu'un
    éclat de 1 m sur 1 nm le serait tout juste. Elle est distincte de
    :data:`TOLERANCE_JOUR_M2`, mille fois plus lâche, parce qu'un jour se mesure sur
    l'union entière et non sur une paire.
    """
    violations: list[str] = []
    rectangles = [_rectangle(piece) for piece in pieces]
    for i, a in enumerate(pieces):
        for decalage, b in enumerate(pieces[i + 1 :], start=i + 1):
            if _disjoints(a, b):
                continue
            aire = rectangles[i].intersection(rectangles[decalage]).area
            if aire > _TOLERANCE_AIRE_M2:
                paire = "|".join(sorted((a.id, b.id)))
                violations.append(f"chevauchement {paire} : {_formater_m2(aire)}")
    return (bool(violations), tuple(violations))


def _jours(
    pieces: tuple[Piece, ...], contour: tuple[tuple[float, float], ...]
) -> tuple[bool, tuple[str, ...]]:
    """Différences ensemblistes union / contour : jour intérieur **et** débord.

    Comparer les seules aires laisserait passer un jour compensé par une pièce hors du
    contour ; les deux différences ensemblistes sont donc testées séparément.
    """
    enveloppe = _polygone_contour(contour)
    if enveloppe is None:
        return True, ("contour dégénéré : aucun pavage n'est définissable",)
    if not pieces:
        return True, ("aucune pièce",)
    union = unary_union([_rectangle(piece) for piece in pieces])
    manque = float(enveloppe.difference(union).area)
    debord = float(union.difference(enveloppe).area)
    violations: list[str] = []
    if manque > TOLERANCE_JOUR_M2:
        violations.append(f"jours : aire non couverte {_formater_m2(manque)}")
    if debord > TOLERANCE_JOUR_M2:
        violations.append(f"jours : débord hors contour {_formater_m2(debord)}")
    return (bool(violations), tuple(violations))


def _surfaces(pieces: tuple[Piece, ...], ctx: Contexte) -> tuple[bool, tuple[str, ...]]:
    """Aire ``w h`` contre ``a_min`` par type."""
    violations: list[str] = []
    for piece in pieces:
        seuil = ctx.referentiel.a_min(piece.type)
        if seuil <= 0.0:
            continue
        if piece.aire + _TOLERANCE_AIRE_M2 < seuil:
            violations.append(
                f"surface {piece.id} : {_formater_m2(piece.aire)} < {_formater_m2(seuil)}"
            )
    return (not violations, tuple(violations))


def _meme_mur(a: Mur, b: Mur) -> bool:
    """Même géométrie à tolérance près, extrémités éventuellement permutées."""
    def proche(p: tuple[float, float], q: tuple[float, float]) -> bool:
        return abs(p[0] - q[0]) <= _TOLERANCE_MUR_M and abs(p[1] - q[1]) <= _TOLERANCE_MUR_M

    return (proche(a.a, b.a) and proche(a.b, b.b)) or (proche(a.a, b.b) and proche(a.b, b.a))


def _structure(plan: Plan, ctx: Contexte) -> tuple[bool, tuple[str, ...]]:
    """Murs porteurs inchangés."""
    par_id = {mur.id: mur for mur in plan.murs}
    violations: list[str] = []
    for mur in ctx.structure.murs_porteurs:
        actuel = par_id.get(mur.id)
        if actuel is None or not _meme_mur(mur, actuel):
            violations.append(f"structure : mur porteur {mur.id} déplacé ou absent")
    return (not violations, tuple(violations))


def _deplacement_max(plan: Plan, reference: Plan | None) -> float:
    """L-infini sur (x, y, w, h) des pièces de même identifiant."""
    if reference is None:
        return 0.0
    par_id = {piece.id: piece for piece in reference.pieces}
    delta = 0.0
    for piece in plan.pieces:
        origine = par_id.get(piece.id)
        if origine is None:
            continue
        delta = max(
            delta,
            abs(piece.x - origine.x),
            abs(piece.y - origine.y),
            abs(piece.w - origine.w),
            abs(piece.h - origine.h),
        )
    return delta


def verifier_exactement(
    plan: Plan, ctx: Contexte, *, reference: Plan | None = None
) -> PreuveGeometrique:
    """Vérifier qu'un plan est valide, sans rien emprunter au solveur.

    Parameters
    ----------
    plan : Plan
        Plan à vérifier.
    ctx : Contexte
        Contour, structure porteuse et référentiel.
    reference : Plan or None, optional
        Plan proposé, pour ``deplacement_max``. ``None`` rend ``0.0``.

    Returns
    -------
    PreuveGeometrique
        Quatre prédicats et messages de violation.

    Guarantees
    ----------
    - Géométrique : **exacte**, inspection finie. ``valide`` est la conjonction.
    - Performance : **aucune**.

    Notes
    -----
    Formules : ``docs/formules/preuve-exacte.md``.
    """
    chevauche, v_chev = _chevauchements(plan.pieces)
    jours, v_jours = _jours(plan.pieces, ctx.contour)
    surfaces_ok, v_surf = _surfaces(plan.pieces, ctx)
    structure_ok, v_struct = _structure(plan, ctx)
    violations = v_chev + v_jours + v_surf + v_struct
    valide = (not chevauche) and (not jours) and surfaces_ok and structure_ok
    return PreuveGeometrique(
        valide=valide,
        chevauchement=chevauche,
        jours=jours,
        surfaces_ok=surfaces_ok,
        structure_preservee=structure_ok,
        deplacement_max=_deplacement_max(plan, reference),
        violations=violations,
    )
