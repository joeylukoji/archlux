"""Corruption contrôlée d'un plan valide — fabrique des entrées à réparer.

Pourquoi ce module existe
-------------------------
Un corpus réel est **déjà valide** : 398 appartements MSD sur 400 passent
``verify_exactly``. Mesurer « taux de validité avant / après ``legalize`` »
sur ces plans ne dit donc rien. Il faut des entrées invalides dont on **connaît
la faute**, ce qu'aucun corpus ne fournit.

Deux façons d'en obtenir : les sorties d'un modèle génératif, ou la corruption
contrôlée d'un plan réel. La seconde est reproductible à la graine près, donne un
grand effectif, et surtout **on sait ce qu'on a cassé** — ce qui permet de
mesurer si la correction répare la bonne chose, pas seulement si elle rend un
plan valide.

Ce que ce module **ne prétend pas**
-----------------------------------
Ces perturbations ne sont **pas** un modèle des erreurs d'un générateur
particulier. Elles reproduisent les *familles* de fautes que la littérature
rapporte — chevauchements, jours, pièces sous-dimensionnées, cloisons décalées —
sans en calibrer les fréquences sur un modèle réel. Toute publication doit le dire
et compléter par au moins un générateur public.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Literal

import numpy as np

from archlux.erreurs import InvariantViole
from archlux.types import Piece, Plan

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["MODES", "Corruption", "Mode", "corrompre"]

Mode = Literal["deplacer", "elargir", "retrecir", "aplatir"]

MODES: tuple[Mode, ...] = ("deplacer", "elargir", "retrecir", "aplatir")
"""Les quatre familles de fautes, et ce que chacune produit.

===========  =========================================  ===========================
Mode         Perturbation                               Faute produite
===========  =========================================  ===========================
``deplacer``  translation de la pièce                    chevauchement **et** jour
``elargir``   ``w`` ou ``h`` augmenté                    chevauchement
``retrecir``  ``w`` ou ``h`` diminué                     jour
``aplatir``   ``h`` fortement diminué                    surface sous le seuil
===========  =========================================  ===========================

``deplacer`` est la plus proche de ce que produit un générateur : il place une
pièce à peu près au bon endroit, ce qui ouvre un jour d'un côté et un
chevauchement de l'autre.
"""

_TAILLE_MIN = 0.30
"""Plancher, en mètres, sous lequel une pièce corrompue serait dégénérée.

Une pièce d'épaisseur nulle n'est pas un plan invalide : c'est un plan sans
géométrie, que ``geom`` refuse avant même d'avoir pu tenter une correction.
"""


@dataclass(frozen=True, slots=True)
class Corruption:
    """Une perturbation appliquée, telle qu'on pourra la comparer à la correction.

    Attributes
    ----------
    piece_id : str
        Identifiant de la pièce touchée, tel qu'il figure dans ``Plan.pieces``.
    amplitude : float
        Déplacement effectivement appliqué, en mètres. Peut être **inférieur** à
        l'amplitude demandée si le plancher :data:`_TAILLE_MIN` a mordu ; c'est
        cette valeur-ci qui est la vérité terrain, pas la consigne.
    """

    mode: Mode
    piece_id: str
    amplitude: float
    axe: Literal["x", "y"]


def _perturber(
    piece: Piece, mode: Mode, amplitude: float, axe: Literal["x", "y"]
) -> tuple[Piece, float]:
    """Appliquer une perturbation, et rendre l'amplitude réellement appliquée."""
    if mode == "deplacer":
        if axe == "x":
            return replace(piece, x=piece.x + amplitude), amplitude
        return replace(piece, y=piece.y + amplitude), amplitude
    if mode == "elargir":
        if axe == "x":
            return replace(piece, w=piece.w + amplitude), amplitude
        return replace(piece, h=piece.h + amplitude), amplitude
    if mode == "retrecir":
        if axe == "x":
            applique = min(amplitude, max(0.0, piece.w - _TAILLE_MIN))
            return replace(piece, w=piece.w - applique), applique
        applique = min(amplitude, max(0.0, piece.h - _TAILLE_MIN))
        return replace(piece, h=piece.h - applique), applique
    # aplatir : on écrase la plus grande dimension, pour viser la surface.
    if piece.w >= piece.h:
        applique = min(amplitude, max(0.0, piece.w - _TAILLE_MIN))
        return replace(piece, w=piece.w - applique), applique
    applique = min(amplitude, max(0.0, piece.h - _TAILLE_MIN))
    return replace(piece, h=piece.h - applique), applique


def corrompre(
    plan: Plan,
    *,
    seed: int,
    amplitude: float = 0.50,
    n_pieces: int = 1,
    modes: Sequence[Mode] = MODES,
) -> tuple[Plan, tuple[Corruption, ...]]:
    """Perturber ``n_pieces`` pièces d'un plan valide, de façon reproductible.

    Parameters
    ----------
    plan : Plan
        Plan de départ, **supposé valide**. Rien ne l'exige : corrompre un plan
        déjà invalide reste défini, mais la mesure « avant / après » perd son sens.
    seed : int
        Graine, **obligatoire et sans défaut** (`ARCHITECTURE.md` §7). Deux appels
        de même graine sur le même plan rendent exactement le même résultat.
    amplitude : float, optional
        Ampleur visée de la perturbation, en mètres. L'amplitude *appliquée* est
        rapportée par chaque :class:`Corruption` et peut être plus faible.
    n_pieces : int, optional
        Nombre de pièces distinctes à toucher. Plafonné au nombre de pièces.
    modes : sequence of Mode, optional
        Familles de fautes autorisées, tirées uniformément. Restreindre à un seul
        mode permet de mesurer la correction faute par faute.

    Returns
    -------
    tuple
        ``(plan_corrompu, corruptions)``. ``plan_corrompu`` ne porte **jamais** de
        certificat : c'est une entrée à corriger, pas une sortie.

    Raises
    ------
    InvariantViole
        Plan sans pièce, ``n_pieces < 1``, ``amplitude <= 0``, ou ``modes`` vide.

    Examples
    --------
    >>> from archlux.data.corruption import corrompre
    >>> from archlux.types import Piece, Plan
    >>> plan = Plan(
    ...     pieces=(Piece("a", "sejour", 0.0, 0.0, 6.0, 9.0),),
    ...     murs=(), ouvertures=(),
    ...     contour=((0.0, 0.0), (6.0, 0.0), (6.0, 9.0), (0.0, 9.0)),
    ... )
    >>> abime, fautes = corrompre(plan, seed=17, modes=("elargir",))
    >>> len(fautes), fautes[0].mode, fautes[0].piece_id
    (1, 'elargir', 'a')
    >>> abime.certificat is None
    True
    """
    if not plan.pieces:
        raise InvariantViole(("plan sans piece : rien a corrompre",))
    if n_pieces < 1:
        raise InvariantViole((f"n_pieces doit etre >= 1 : {n_pieces}",))
    if amplitude <= 0.0:
        raise InvariantViole((f"amplitude doit etre > 0 : {amplitude}",))
    if not modes:
        raise InvariantViole(("aucun mode de corruption",))

    rng = np.random.default_rng(seed)
    # Tri par identifiant avant tirage : l'ordre de ``plan.pieces`` ne doit pas
    # influer sur le resultat, sinon la graine ne suffit pas a rejouer.
    rangs = sorted(range(len(plan.pieces)), key=lambda i: plan.pieces[i].id)
    combien = min(n_pieces, len(rangs))
    choisis = [rangs[int(i)] for i in rng.choice(len(rangs), size=combien, replace=False)]

    pieces = list(plan.pieces)
    fautes: list[Corruption] = []
    for rang in sorted(choisis):
        mode = modes[int(rng.integers(len(modes)))]
        axe: Literal["x", "y"] = "x" if bool(rng.integers(2)) else "y"
        signe = 1.0 if mode != "deplacer" else float(rng.choice([-1.0, 1.0]))
        piece, applique = _perturber(pieces[rang], mode, amplitude * signe, axe)
        if applique == 0.0:
            continue
        pieces[rang] = piece
        fautes.append(Corruption(mode=mode, piece_id=piece.id, amplitude=float(applique), axe=axe))
    return replace(plan, pieces=tuple(pieces), certificat=None), tuple(fautes)
