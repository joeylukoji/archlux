"""Statistiques circulaires pour l'orientation.

Une orientation est un point sur un cercle, pas un réel. Traiter 359° et 1° comme
éloignés de 358° produit des moyennes fausses, des régressions fausses et des conclusions
fausses — et rien dans les tests usuels ne le signale.

Toute grandeur dérivée de :class:`archlux.types.Orientation` passe par ce module.

Formules : ``docs/formules/circulaire.md`` (Mardia & Jupp, 2000).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from archlux.erreurs import InvariantViole
from archlux.types import Orientation

__all__ = [
    "ResultatRegression",
    "concentration",
    "difference_angulaire",
    "direction_dominante",
    "encode",
    "encoder",
    "moyenne_circulaire",
    "rayleigh",
    "regression_circulaire_lineaire",
    "stratifier",
    "variance_circulaire",
]

_NOMS_HUIT = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
_EPS_ANGLE = 1e-9
"""Tolerance de recalage d'un angle sur le bord de sa periode."""
_EPS_RESULTANTE = 1e-12
"""Sous ce module de resultante, aucune direction n'est dominante."""


@dataclass(frozen=True, slots=True)
class ResultatRegression:
    r"""Ajustement :math:`y \approx a\cos\theta + b\sin\theta + c`."""

    a: float
    b: float
    c: float
    residus: np.ndarray


def encode(deg: float, *, harmoniques: int = 3) -> np.ndarray:
    """Encoder un azimut en ``(cos θ, sin θ, cos 2θ, sin 2θ, …)``.

    Parameters
    ----------
    deg : float
        Azimut, en degrés. N'est **jamais** renvoyé tel quel.
    harmoniques : int, optional
        Nombre d'harmoniques. Une seule ne capture pas l'asymétrie est/ouest.

    Returns
    -------
    numpy.ndarray
        Vecteur de dimension ``2 * harmoniques``, borné, continu en 0°/360°.
    """
    if harmoniques < 1:
        raise ValueError(f"harmoniques doit être ≥ 1, reçu {harmoniques}")
    theta = math.radians(deg)
    composantes = np.empty(2 * harmoniques, dtype=float)
    for rang in range(1, harmoniques + 1):
        composantes[2 * (rang - 1)] = math.cos(rang * theta)
        composantes[2 * (rang - 1) + 1] = math.sin(rang * theta)
    return composantes


def encoder(orientation: Orientation, *, harmoniques: int = 2) -> np.ndarray:
    """Encoder un :class:`~archlux.types.Orientation` en harmoniques de Fourier.

    Parameters
    ----------
    orientation : Orientation
        Azimut, en degrés.
    harmoniques : int, optional
        Nombre d'harmoniques. Défaut 2 (contrat historique du squelette).

    Returns
    -------
    numpy.ndarray
        Vecteur de dimension ``2 * harmoniques``.
    """
    return encode(orientation.deg, harmoniques=harmoniques)


def _radians(degres: np.ndarray | Sequence[float]) -> np.ndarray:
    """Convertir une séquence d'azimuts en radians, aplatis."""
    valeurs = np.ravel(np.asarray(degres, dtype=float))
    if valeurs.size == 0:
        raise ValueError("au moins une orientation est requise")
    return np.asarray(np.radians(valeurs), dtype=float)


def _resultante(degres: np.ndarray | Sequence[float]) -> tuple[float, float, int]:
    """Somme des vecteurs unitaires ``(C, S)`` et effectif ``n``."""
    theta = _radians(degres)
    return float(np.cos(theta).sum()), float(np.sin(theta).sum()), int(theta.size)


def moyenne_circulaire(degres: np.ndarray | Sequence[float]) -> float:
    """Direction moyenne, via la somme des vecteurs unitaires.

    Returns
    -------
    float
        Azimut moyen en degrés, dans ``[0, 360)``. ``360°`` est identifié à ``0°``.
    """
    cosinus, sinus, _n = _resultante(degres)
    deg = float(np.degrees(np.arctan2(sinus, cosinus))) % 360.0
    return 0.0 if deg > 360.0 - 1e-9 else deg


def direction_dominante(
    degres: np.ndarray | Sequence[float],
    poids: np.ndarray | Sequence[float] | None = None,
    *,
    periode: float = 90.0,
) -> float:
    r"""Direction moyenne d'un jeu d'axes, pondérée et de période ``periode``.

    Une arête de mur n'a pas de sens de parcours : ``10°`` et ``190°`` décrivent la
    même direction, et sur un plan orthogonal ``10°``, ``100°``, ``190°``, ``280°``
    décrivent la même *trame*. Une moyenne circulaire ordinaire (période 360°) les
    annulerait mutuellement et rendrait une direction arbitraire.

    La méthode est celle des données axiales (Mardia & Jupp, §2.3.3), généralisée à
    une période :math:`p` : on multiplie l'angle par :math:`m = 360/p` pour ramener
    les directions équivalentes sur un même point du cercle, on y prend la moyenne
    circulaire pondérée, puis on divise par :math:`m` :

    .. math::

        \bar\theta = \frac{1}{m}\,\operatorname{arg}
        \sum_k \ell_k \, e^{\,i\,m\,\theta_k},
        \qquad m = \frac{360}{p}.

    Les poids sont typiquement des **longueurs** : un mur de 6 m doit peser plus
    qu'un ébrasement de 10 cm.

    Parameters
    ----------
    degres : array_like
        Angles des axes, en degrés.
    poids : array_like or None, optional
        Poids positifs, même longueur. ``None`` = poids unitaires.
    periode : float, optional
        Période de la symétrie, en degrés. ``90`` pour une trame orthogonale
        (défaut), ``180`` pour des axes non orientés, ``360`` pour des vecteurs.

    Returns
    -------
    float
        Direction dominante, en degrés, dans ``[0, periode)``.

    Raises
    ------
    InvariantViole
        Entrée vide, longueurs incohérentes, ``periode`` hors ``]0, 360]``, poids
        négatifs, ou résultante nulle — dans ce dernier cas aucune direction n'est
        dominante et rendre un angle serait inventer une information.

    Examples
    --------
    >>> from archlux.orient.circulaire import direction_dominante
    >>> round(direction_dominante([10.0, 100.0, 190.0, 280.0]), 6)
    10.0
    >>> round(direction_dominante([0.0, 90.0], [1.0, 3.0]), 6)
    0.0
    """
    angles = np.asarray(degres, dtype=float).ravel()
    if angles.size == 0:
        raise InvariantViole(("aucun axe : direction dominante indéfinie",))
    if not 0.0 < periode <= 360.0:
        raise InvariantViole((f"periode hors ]0, 360] : {periode}",))
    if poids is None:
        longueurs = np.ones_like(angles)
    else:
        longueurs = np.asarray(poids, dtype=float).ravel()
        if longueurs.size != angles.size:
            raise InvariantViole(("degres et poids de longueurs distinctes",))
        if bool(np.any(longueurs < 0.0)):
            raise InvariantViole(("poids négatif",))
    m = 360.0 / periode
    phases = np.radians(m * angles)
    cosinus = float(np.sum(longueurs * np.cos(phases)))
    sinus = float(np.sum(longueurs * np.sin(phases)))
    if math.hypot(cosinus, sinus) <= _EPS_RESULTANTE:
        raise InvariantViole(("résultante nulle : aucune direction dominante",))
    deg = float(np.degrees(math.atan2(sinus, cosinus)) / m) % periode
    # Une direction juste sous ``periode`` est la même que ``0`` : sans ce recalage,
    # une trame parfaitement alignée sur l'axe x sort à 89,999999° au lieu de 0°,
    # parce que ``atan2`` rend un angle infinitésimalement négatif.
    return 0.0 if deg > periode - _EPS_ANGLE else deg


def concentration(degres: np.ndarray | Sequence[float]) -> float:
    """Longueur de la résultante moyenne, dans ``[0, 1]``.

    Returns
    -------
    float
        ``0`` = orientations uniformes, ``1`` = toutes identiques. C'est l'analogue
        circulaire de l'inverse d'une variance, et il n'a pas d'unité d'angle.
    """
    cosinus, sinus, effectif = _resultante(degres)
    return math.hypot(cosinus, sinus) / effectif


def variance_circulaire(degres: np.ndarray | Sequence[float]) -> float:
    r"""Variance circulaire :math:`V = 1 - \bar R` (Mardia & Jupp, §2.3)."""
    return 1.0 - concentration(degres)


def rayleigh(degres: np.ndarray | Sequence[float]) -> tuple[float, float]:
    r"""Test d'uniformité de Rayleigh sur le cercle.

    Returns
    -------
    tuple of float
        ``(R̄, p)``. Sous l'hypothèse d'uniformité, :math:`n\bar R^2` est
        approximativement exponentielle : :math:`p \approx e^{-n\bar R^2}`.

    Notes
    -----
    Le nom n'est pas ``test_rayleigh`` : pytest collecterait la fonction comme un test.

    L'approximation :math:`p = e^{-Z}`, :math:`Z = n\bar R^2`, est le **premier ordre**
    de Mardia & Jupp (§6.3.1). Elle est anti-conservatrice à petit ``n`` : elle rend un
    ``p`` trop petit, donc rejette l'uniformité trop souvent. La correction usuelle
    :math:`p \approx e^{-Z}\,[1 + (2Z - Z^2)/(4n)]` n'est pas appliquée ici. En dessous
    d'une cinquantaine d'observations, ne pas publier ce ``p`` sans le corriger.
    """
    resultante = concentration(degres)
    effectif = _radians(degres).size
    p_valeur = math.exp(-effectif * resultante * resultante)
    return resultante, p_valeur


def difference_angulaire(a: float, b: float) -> float:
    """Écart signé le plus court entre deux azimuts, dans ``]-180, 180]``."""
    ecart = (a - b + 180.0) % 360.0 - 180.0
    if ecart <= -180.0:
        return 180.0
    return float(ecart)


def regression_circulaire_lineaire(
    theta: np.ndarray, y: np.ndarray
) -> ResultatRegression:
    r"""Régression :math:`y \sim a\cos\theta + b\sin\theta + c`.

    Parameters
    ----------
    theta : numpy.ndarray
        Azimuts, en degrés.
    y : numpy.ndarray
        Réponse linéaire (indicateur, gain, …).
    """
    azimut = np.ravel(np.asarray(theta, dtype=float))
    reponse = np.ravel(np.asarray(y, dtype=float))
    if azimut.size != reponse.size:
        raise ValueError("theta et y doivent avoir la même longueur")
    if azimut.size < 3:
        raise ValueError("au moins trois observations sont requises")
    radians = np.radians(azimut)
    dessin = np.column_stack((np.cos(radians), np.sin(radians), np.ones(azimut.size)))
    coeffs, *_reste = np.linalg.lstsq(dessin, reponse, rcond=None)
    residus = reponse - dessin @ coeffs
    return ResultatRegression(
        a=float(coeffs[0]),
        b=float(coeffs[1]),
        c=float(coeffs[2]),
        residus=residus,
    )


def stratifier(
    degres: np.ndarray | Sequence[float],
    *,
    n_secteurs: int = 8,
) -> dict[str, np.ndarray]:
    """Découper des azimuts en secteurs d'égale ouverture.

    Parameters
    ----------
    degres : array-like
        Azimuts, en degrés.
    n_secteurs : int, optional
        Nombre de secteurs. 8 → rose des vents nommée (N, NE, …).
    """
    if n_secteurs < 1:
        raise ValueError(f"n_secteurs doit être ≥ 1, reçu {n_secteurs}")
    valeurs = np.ravel(np.asarray(degres, dtype=float))
    largeur = 360.0 / n_secteurs
    decale = (valeurs % 360.0 + largeur / 2.0) % 360.0
    indices = np.floor(decale / largeur).astype(int) % n_secteurs
    noms = _NOMS_HUIT if n_secteurs == 8 else tuple(str(i) for i in range(n_secteurs))
    return {
        nom: valeurs[indices == rang]
        for rang, nom in enumerate(noms)
    }
