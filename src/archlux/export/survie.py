"""Taux de survie à l'export validé, avec intervalle de Wilson."""

from __future__ import annotations

from collections.abc import Sequence

from archlux.erreurs import InvariantViole
from archlux.export.pathologie import diagnostiquer
from archlux.export.wilson import intervalle_wilson
from archlux.types import Plan

__all__ = ["survival_rate"]


def survival_rate(plans: Sequence[Plan], *, z: float = 1.96) -> tuple[float, tuple[float, float]]:
    """Proportion de plans exportables + intervalle de Wilson.

    Parameters
    ----------
    plans : Sequence[Plan]
        Échantillon (``n ≥ 1``).
    z : float, optional
        Quantile gaussien (1,96 ≈ 95 %).

    Returns
    -------
    tuple
        ``(taux, (lo, hi))`` avec ``0 ≤ lo ≤ taux ≤ hi ≤ 1``.
    """
    n = len(plans)
    if n < 1:
        raise InvariantViole(("plans doit être non vide",))
    succes = sum(1 for plan in plans if diagnostiquer(plan).exportable)
    taux = succes / n
    return taux, intervalle_wilson(succes, n, z=z)
