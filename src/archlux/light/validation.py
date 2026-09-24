"""Validation du gradient d'un substitut. Sans elle, l'optimiseur converge vers du bruit.

Un substitut dont la valeur est excellente mais le gradient faux produit une optimisation
qui *semble* fonctionner : elle converge, elle rend des plans valides, et elle les choisit
au hasard. Aucun test de précision ne détecte cela. Cette vérification est le seul garde-
fou, et elle est obligatoire avant tout usage d'un substitut dans :mod:`archlux.solve`.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

import numpy as np

from archlux.erreurs import SubstitutInvalide

if TYPE_CHECKING:
    from archlux.light.protocole import Substitut
    from archlux.types import Orientation

__all__ = ["RapportGradient", "valider_gradient"]

_NUIT = 1e-8


@dataclass(frozen=True, slots=True)
class RapportGradient:
    """Comparaison du gradient déclaré aux différences finies d'une référence.

    Attributes
    ----------
    accord_de_signe : float
        Fraction de coordonnées dont le signe coïncide. **Point de contrôle** :
        sous 0,80, ne pas passer au jalon 5 (`MILESTONE-4.md` §7).
    """

    erreur_relative_max: float
    cosinus_moyen: float
    accord_de_signe: float
    n_points: int
    graine: int
    conforme: bool


def _differences_finies(
    substitut: Substitut, x: np.ndarray, orientation: Orientation, pas: float
) -> np.ndarray:
    """Pente centrée de ``evaluer`` le long de chaque coordonnée de ``x``."""
    x0 = np.asarray(x, dtype=float).ravel()
    g = np.empty_like(x0)
    for i in range(x0.size):
        plus, moins = x0.copy(), x0.copy()
        plus[i] += pas
        moins[i] -= pas
        g[i] = (
            float(substitut.evaluer(plus, orientation))
            - float(substitut.evaluer(moins, orientation))
        ) / (2.0 * pas)
    return g


def valider_gradient(
    substitut: Substitut,
    points: np.ndarray,
    orientation: Orientation,
    *,
    seed: int,
    reference: Substitut | None = None,
    pas: float = 0.10,
    epsilon: float = 1e-5,
    tolerance: float = 1e-3,
    seuil_signe: float = 0.80,
) -> RapportGradient:
    """Comparer le gradient du substitut aux différences finies.

    Si ``reference`` est fournie (oracle gelé), on compare les **signes**
    au pente réelle — c'est le point de contrôle du projet. Sinon, on vérifie
    la cohérence interne ``gradient`` vs ``evaluer`` du même objet.

    Parameters
    ----------
    substitut : Substitut
        Modèle à valider, analytique ou appris.
    points : numpy.ndarray
        Points d'évaluation, un par ligne.
    orientation : Orientation
        Azimut utilisé pour toutes les évaluations.
    seed : int
        Graine du tirage. **Obligatoire, sans défaut** (`ARCHITECTURE.md` §7).
        Ordonne les points avant agrégation, pour un diagnostic reproductible.
    reference : Substitut or None, optional
        Vérité terrain. ``None`` = auto-contrôle par différences finies.
    pas : float, optional
        Déplacement pour la pente réelle (point de contrôle).
    epsilon : float, optional
        Pas des différences finies d'auto-contrôle.
    tolerance : float, optional
        Erreur relative maximale admise en auto-contrôle.
    seuil_signe : float, optional
        Seuil d'accord de signe. Défaut 0,80.

    Returns
    -------
    RapportGradient
        Diagnostic complet, jamais un simple booléen.

    Raises
    ------
    SubstitutInvalide
        Auto-contrôle hors tolérance, ou accord de signe sous le seuil.

    Notes
    -----
    - ``RapportGradient.conforme`` vaut **toujours** ``True`` dans la valeur rendue :
      l'échec lève, il ne se rapporte pas. Le diagnostic chiffré promis ci-dessus n'est
      donc jamais lisible dans le cas qui l'intéresse le plus. Un appelant qui veut
      inspecter un échec doit passer par l'exception, qui ne porte qu'un message.
    - ``seed`` ne fait que permuter les points ; les agrégats étant un ``max`` et deux
      moyennes, il ne change le résultat qu'au dernier bit d'arrondi. Il satisfait la
      règle « graine obligatoire » du §7 sans rendre la fonction aléatoire.
    - Le mode auto-contrôle compare le gradient déclaré aux différences finies du
      **même** objet : il détecte une dérivée fausse, jamais un modèle faux. Seul le
      mode ``reference`` confronte à l'oracle gelé.
    """
    matrice = np.asarray(points, dtype=float)
    if matrice.ndim == 1:
        matrice = matrice.reshape(1, -1)
    rng = np.random.default_rng(seed)
    matrice = matrice[rng.permutation(matrice.shape[0])]
    oracle = reference
    pas_fd = pas if oracle is not None else epsilon
    erreurs: list[float] = []
    cosinus: list[float] = []
    signes: list[bool] = []
    for x in matrice:
        declare = np.asarray(substitut.gradient(x, orientation), dtype=float).ravel()
        cible = (
            _differences_finies(oracle, x, orientation, pas_fd)
            if oracle is not None
            else _differences_finies(substitut, x, orientation, pas_fd)
        )
        norme_c = float(np.linalg.norm(cible))
        norme_d = float(np.linalg.norm(declare))
        if norme_c < _NUIT and norme_d < _NUIT:
            erreurs.append(0.0)
            cosinus.append(1.0)
            signes.extend([True] * declare.size)
            continue
        denom = max(norme_c, _NUIT)
        erreurs.append(float(np.linalg.norm(declare - cible) / denom))
        if norme_c > _NUIT and norme_d > _NUIT:
            cosinus.append(float(np.dot(declare, cible) / (norme_d * norme_c)))
        else:
            cosinus.append(0.0)
        for a, b in zip(declare, cible, strict=True):
            if abs(b) < 1e-3:
                continue
            if abs(a) < _NUIT:
                signes.append(False)
            else:
                signes.append((a >= 0.0) == (b >= 0.0))
    rapport = RapportGradient(
        erreur_relative_max=max(erreurs) if erreurs else 0.0,
        cosinus_moyen=float(np.mean(cosinus)) if cosinus else 1.0,
        accord_de_signe=float(np.mean(signes)) if signes else 1.0,
        n_points=int(matrice.shape[0]),
        graine=seed,
        conforme=False,
    )
    if oracle is None:
        conforme = rapport.erreur_relative_max <= tolerance
        if not conforme:
            raise SubstitutInvalide(
                f"erreur relative {rapport.erreur_relative_max:.3g} > {tolerance}"
            )
    else:
        conforme = rapport.accord_de_signe >= seuil_signe
        if not conforme:
            raise SubstitutInvalide(
                f"accord de signe {rapport.accord_de_signe:.3f} < {seuil_signe} "
                "— ne pas passer au jalon 5"
            )
    return replace(rapport, conforme=True)
