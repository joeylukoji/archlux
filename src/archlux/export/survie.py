"""Survival rate on validated export, with Wilson interval."""

from __future__ import annotations

from collections.abc import Sequence

from archlux.errors import InvariantViolation
from archlux.export.pathologies import diagnose
from archlux.export.wilson import wilson_interval
from archlux.types import Plan

__all__ = ["survival_rate"]


def survival_rate(plans: Sequence[Plan], *, z: float = 1.96) -> tuple[float, tuple[float, float]]:
    """Proportion of exportable plans + Wilson interval.

    Parameters
    ----------
    plans : Sequence[Plan]
        Sample (``n >= 1``).
    z : float, optional
        Gaussian quantile (1.96 ~= 95%).

    Returns
    -------
    tuple
        ``(rate, (lo, hi))`` with ``0 <= lo <= rate <= hi <= 1``.
    """
    n = len(plans)
    if n < 1:
        raise InvariantViolation(("plans must be non-empty",))
    successes = sum(1 for plan in plans if diagnose(plan).exportable)
    taux = successes / n
    return taux, wilson_interval(successes, n, z=z)
