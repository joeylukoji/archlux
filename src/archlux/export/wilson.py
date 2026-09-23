"""Intervalle de Wilson pour une proportion (taux de survie)."""

from __future__ import annotations

import math

from archlux.erreurs import InvariantViole

__all__ = ["intervalle_wilson"]


def intervalle_wilson(
    succes: int, n: int, *, z: float = 1.96
) -> tuple[float, float]:
    """Intervalle de confiance de Wilson pour une proportion.

    Contrairement à l'approximation normale, les bornes restent dans ``[0, 1]``
    même pour de petits ``n`` ou des taux proches de 0 / 1.

    Aux deux extrêmes, les bornes sont posées **exactement** plutôt que calculées.
    En ``p̂ = 0``, la formule donne analytiquement ``centre = marge = z²/(2n)`` : la
    soustraction s'annule en arithmétique exacte, mais la racine carrée introduit un
    ulp d'écart et ``centre - marge`` sort à ~1e-17 **au-dessus** de zéro. Le
    ``max(0, ·)`` final ne rattrapait rien — la valeur était positive — et
    l'intervalle rendu ne contenait alors pas son propre estimateur ponctuel :
    ``intervalle_wilson(0, 3)`` rendait ``(4.9e-17, 0.561)`` pour un taux nul,
    contredisant le contrat ``0 ≤ lo ≤ taux ≤ hi ≤ 1`` de
    :func:`~archlux.export.survie.survival_rate`. Symétriquement, ``p̂ = 1`` rendait
    ``hi = 0.9999999999999999``.

    Parameters
    ----------
    succes : int
        Nombre de succès (``0 ≤ succes ≤ n``).
    n : int
        Taille d'échantillon (``≥ 1``).
    z : float, optional
        Quantile gaussien (1,96 ≈ 95 %).

    Returns
    -------
    tuple of float
        ``(borne_inf, borne_sup)``, avec ``0 ≤ borne_inf ≤ succes/n ≤ borne_sup ≤ 1``.

    Notes
    -----
    Sans correction de continuité : l'intervalle est celui du score de Wilson brut.

    Raises
    ------
    InvariantViole
        ``n < 1``, ``succes`` hors ``[0, n]``, ou ``z ≤ 0``.
    """
    if n < 1:
        raise InvariantViole(("n doit être ≥ 1",))
    if not 0 <= succes <= n:
        raise InvariantViole((f"succes={succes} hors [0, {n}]",))
    if z <= 0.0:
        raise InvariantViole(("z doit être > 0",))
    phat = succes / n
    z2 = z * z
    denom = 1.0 + z2 / n
    centre = phat + z2 / (2.0 * n)
    marge = z * math.sqrt((phat * (1.0 - phat) + z2 / (4.0 * n)) / n)
    lo = 0.0 if succes == 0 else max(0.0, (centre - marge) / denom)
    hi = 1.0 if succes == n else min(1.0, (centre + marge) / denom)
    return lo, hi
