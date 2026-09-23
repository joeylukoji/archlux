"""Frank-Wolfe : maximiser un substitut sur le polytope, sans jamais sortir du valide.

L'algorithme est choisi pour une raison structurelle, pas de commodité : son oracle
linéaire **est** le solveur de légalisation. Chaque itération résout exactement le même
LP qu'une légalisation classique, avec un autre vecteur de coûts. Il n'y a donc qu'un
solveur dans tout le projet, et chaque itéré est un plan valide — pas de projection, pas
d'étape intermédiaire illégale.

Dépendances : ``types``, ``geom``, ``lmo``, et le **protocole** ``light.protocole``.
Jamais une implémentation concrète de substitut.

Formules : ``docs/formules/frank-wolfe.md``.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

import numpy as np

from archlux.erreurs import InvariantViole
from archlux.geom.polytope import Polytope
from archlux.lmo.coupes import MAX_COUPES_PAR_PIECE, Coupe, coupe_surface, surfaces_violees
from archlux.lmo.solveur import resoudre
from archlux.solve.trace import Iteration, Trace

if TYPE_CHECKING:
    from collections.abc import Sequence

    from archlux.light.protocole import Baies, Substitut
    from archlux.types import Contexte, Orientation, Piece

__all__ = ["ResultatFW", "frank_wolfe"]

_POIDS_MIN = 1e-12


@dataclass(frozen=True, slots=True)
class ResultatFW:
    """Itéré final, garanties d'optimalité et trace.

    Attributes
    ----------
    gap : float
        Gap de dualité de Frank-Wolfe. **Borne supérieure certifiée** sur l'écart à
        l'optimum du substitut — une garantie d'optimisation, à ne pas confondre avec
        la garantie de performance lumineuse, qui est probabiliste. La borne n'est
        certifiée que si le substitut est concave ; sinon c'est un diagnostic.
    iterations : int
        Longueur de ``trace.iterations``, **entrée initiale ``k = -1`` comprise** : le
        nombre de pas effectivement franchis vaut ``iterations - 1``.
    duaux : numpy.ndarray or None
        Prix duaux du dernier LP, alignés sur les lignes de ``poly.A``. Les égalités
        produites par :func:`archlux.geom.polytope.figer_contacts` n'y figurent pas :
        le diagnostic dual d'une passe performantielle est donc souvent vide.
    """

    x: np.ndarray
    valeur: float
    gap: float
    iterations: int
    trace: Trace
    duaux: np.ndarray | None = None


def _restreindre_budget(poly: Polytope, centre: np.ndarray, rayon: float) -> Polytope:
    """Intersection du polytope avec la boîte ``‖x − centre‖_∞ ≤ rayon``."""
    nouvelles: list[tuple[float, float]] = []
    for i, (lo, hi) in enumerate(poly.bornes):
        bas = max(lo, float(centre[i]) - rayon)
        haut = min(hi, float(centre[i]) + rayon)
        if bas > haut + 1e-12:
            raise InvariantViole((f"budget {rayon} m incompatible avec les bornes en colonne {i}",))
        nouvelles.append((bas, haut))
    return replace(poly, bornes=tuple(nouvelles))


def _index_sommet(sommets: list[np.ndarray], candidat: np.ndarray) -> int | None:
    """Indice d'un sommet déjà stocké, à tolérance près."""
    for rang, sommet in enumerate(sommets):
        if np.allclose(sommet, candidat, atol=1e-9, rtol=0.0):
            return rang
    return None


def _enrichir_coupes(
    liste: list[Coupe],
    x: np.ndarray,
    domaine: Polytope,
    ctx: Contexte | None,
    pieces: tuple[Piece, ...] | None,
) -> None:
    """Ajouter des tangentes AM-GM si une pièce passe sous ``a_min``."""
    if ctx is None or not pieces:
        return
    if len(liste) >= MAX_COUPES_PAR_PIECE * len(pieces):
        return
    for identifiant in surfaces_violees(x, domaine, ctx, pieces=pieces):
        largeur = float(x[domaine.index[f"{identifiant}.w"]])
        hauteur = float(x[domaine.index[f"{identifiant}.h"]])
        a_min = ctx.referentiel.a_min(next(p.type for p in pieces if p.id == identifiant))
        if largeur > 0.0 and hauteur > 0.0 and a_min > 0.0:
            liste.append(coupe_surface(largeur, hauteur, a_min, piece=identifiant))


def _normaliser(poids: list[float]) -> None:
    """Ramener la somme des poids à 1, en place.

    Le filtrage des masses numériquement nulles a lieu **avant** l'appel, chez
    l'appelant, qui seul peut retirer le sommet correspondant en même temps : élaguer
    les poids ici désynchroniserait les deux listes.
    """
    total = sum(poids)
    if total <= 0.0:
        return
    for rang, masse in enumerate(poids):
        poids[rang] = masse / total


def frank_wolfe(
    poly: Polytope,
    substitut: Substitut,
    orientation: Orientation,
    depart: np.ndarray,
    *,
    max_iter: int = 50,
    tol: float = 1e-4,
    budget: float | None = None,
    away_steps: bool = True,
    coupes: Sequence[Coupe] | None = None,
    pieces: tuple[Piece, ...] | None = None,
    ctx: Contexte | None = None,
    baies: Baies | None = None,
) -> ResultatFW:
    """Maximiser ``substitut`` sur le polytope, en partant de ``depart``.

    Parameters
    ----------
    poly : Polytope
        Domaine admissible ; tous les itérés y restent.
    substitut : Substitut
        Objectif. Le solveur ne sait pas s'il est analytique, appris ou simulé.
    orientation : Orientation
        Azimut du plan.
    depart : numpy.ndarray
        Itéré initial — typiquement le résultat de la légalisation classique.
    max_iter : int, optional
        Nombre maximal d'itérations.
    tol : float, optional
        Arrêt lorsque le gap de dualité passe sous ce seuil.
    budget : float or None, optional
        Déplacement maximal autorisé, en mètres, par rapport à ``depart``.
    away_steps : bool, optional
        Pas d'écartement : accélère la convergence sur les optima situés sur une face.
    coupes : sequence of Coupe or None, optional
        **Legacy, no caller since 0.10.** Outer tangent cuts; they do not guarantee
        minimum areas and disable the LP warm start. Pass a domain built with
        :func:`archlux.lmo.coupes.inner_area_constraints` instead. Removal planned in
        PLAN.md phase 4.
    pieces, ctx : optional
        **Legacy**, same status: with them, Kelley cuts are added when a minimum area
        is broken on the way.

    Returns
    -------
    ResultatFW
        Itéré final et gap certifié.

    Guarantees
    ----------
    - Géométrique : **exacte** à chaque itération vis-à-vis de ``poly`` — tout itéré
      est une combinaison convexe de ``depart`` et de sommets du polytope, donc sans
      chevauchement ni jour.
    - Optimisation : ``gap`` borne l'écart à l'optimum **du substitut** si celui-ci
      est concave.
    - Performance lumineuse : **aucune ici**. Elle est produite par
      :mod:`archlux.uq` et n'est que probabiliste.

    Warnings
    --------
    Minimum areas are guaranteed **only if** ``poly`` already contains an inner
    approximation of them (:func:`archlux.lmo.coupes.inner_area_constraints`), which is
    what :func:`archlux.api.legalize` passes: every point of such a domain keeps every
    minimum area, hence every iterate does. The legacy ``coupes``/``pieces``/``ctx``
    path adds *outer* tangent cuts on the way; a cut added mid-run is violated by the
    current iterate, ``gap`` may turn negative and ``x`` may stay below ``a_min``. That
    path is kept for compatibility and is no longer used by ``legalize``.

    Complexity
    ----------
    ``max_iter`` appels LP, **tous à chaud** via ``depart=``. Omettre ce paramètre
    coûte un facteur 3 à 5. Budget : < 500 ms pour 15 pièces et 50 itérations.
    """
    domaine = poly if budget is None else _restreindre_budget(poly, depart, budget)
    x = np.asarray(depart, dtype=float).copy()
    if x.shape != (len(domaine.index),):
        raise InvariantViole((f"départ de dimension {x.shape}, attendu ({len(domaine.index)},)",))

    sommets = [x.copy()]
    poids = [1.0]
    liste_coupes: list[Coupe] = list(coupes) if coupes else []
    n_coupes = len(liste_coupes)
    gap = 0.0
    valeur = float(substitut.evaluer(x, orientation, baies=baies))
    historique: list[Iteration] = [
        Iteration(
            k=-1,
            valeur=valeur,
            gap=float("inf"),
            pas=0.0,
            away_step=False,
            temps_lp_ms=0.0,
            n_coupes=n_coupes,
            x=x.copy(),
        )
    ]
    dernier_oracle = None

    for k in range(max_iter):
        gradient = np.asarray(substitut.gradient(x, orientation, baies=baies), dtype=float)
        oracle = resoudre(
            domaine,
            -gradient,
            depart=x,
            coupes=liste_coupes or None,
            duaux=(k == max_iter - 1),
        )
        dernier_oracle = oracle
        if oracle.statut != "optimal":
            break
        sommet_fw = oracle.x
        gap = float(gradient @ (sommet_fw - x))
        if gap <= tol:
            historique.append(
                Iteration(
                    k=k,
                    valeur=valeur,
                    gap=gap,
                    pas=0.0,
                    away_step=False,
                    temps_lp_ms=oracle.temps_ms,
                    n_coupes=n_coupes,
                    x=x.copy(),
                )
            )
            break

        away = False
        direction = sommet_fw - x
        gamma_max = 1.0
        indice_away: int | None = None
        if away_steps and len(sommets) > 1:
            scores = [float(gradient @ sommet) for sommet in sommets]
            indice_away = int(np.argmin(scores))
            sommet_away = sommets[indice_away]
            direction_away = x - sommet_away
            if (
                float(gradient @ direction_away) > float(gradient @ direction)
                and poids[indice_away] < 1.0 - _POIDS_MIN
            ):
                direction = direction_away
                gamma_max = poids[indice_away] / (1.0 - poids[indice_away])
                away = True

        gamma = min(2.0 / (k + 2), gamma_max)
        for _ in range(12):
            candidat = x + gamma * direction
            valeur_nouvelle = float(substitut.evaluer(candidat, orientation, baies=baies))
            if valeur_nouvelle >= valeur - 1e-12:
                valeur = valeur_nouvelle
                x = candidat
                break
            gamma *= 0.5
        else:
            historique.append(
                Iteration(
                    k=k,
                    valeur=valeur,
                    gap=gap,
                    pas=0.0,
                    away_step=away,
                    temps_lp_ms=oracle.temps_ms,
                    n_coupes=n_coupes,
                    x=x.copy(),
                )
            )
            break

        if away and indice_away is not None:
            for rang in range(len(poids)):
                poids[rang] *= 1.0 + gamma
            poids[indice_away] -= gamma
        else:
            for rang in range(len(poids)):
                poids[rang] *= 1.0 - gamma
            deja = _index_sommet(sommets, sommet_fw)
            if deja is None:
                sommets.append(sommet_fw.copy())
                poids.append(gamma)
            else:
                poids[deja] += gamma

        conserves_s: list[np.ndarray] = []
        conserves_p: list[float] = []
        for sommet, masse in zip(sommets, poids, strict=True):
            if masse > _POIDS_MIN:
                conserves_s.append(sommet)
                conserves_p.append(masse)
        sommets, poids = conserves_s, conserves_p
        _normaliser(poids)
        _enrichir_coupes(liste_coupes, x, domaine, ctx, pieces)
        n_coupes = len(liste_coupes)

        historique.append(
            Iteration(
                k=k,
                valeur=valeur,
                gap=gap,
                pas=gamma,
                away_step=away,
                temps_lp_ms=oracle.temps_ms,
                n_coupes=n_coupes,
                x=x.copy(),
            )
        )

    duaux = None
    if dernier_oracle is not None and dernier_oracle.duaux is not None:
        duaux = dernier_oracle.duaux
    elif dernier_oracle is not None and dernier_oracle.statut == "optimal":
        extra = resoudre(
            domaine,
            -np.asarray(substitut.gradient(x, orientation, baies=baies), dtype=float),
            depart=x,
            coupes=liste_coupes or None,
            duaux=True,
        )
        if extra.statut == "optimal":
            duaux = extra.duaux

    return ResultatFW(
        x=x,
        valeur=valeur,
        gap=gap,
        iterations=len(historique),
        trace=Trace(iterations=tuple(historique)),
        duaux=duaux,
    )
