"""Trust region whose radius comes from the calibration set, not from a hand-set value.

The conformal bound is only as good as the plans it was calibrated on. A plan that moves
farther from its generated plan than any calibration plan did leaves the domain where
the scores were measured, and the bound says nothing there. The radius of the trust
region ``B_inf(x0, r)`` is therefore read off the calibration set: the conformal
quantile of the Chebyshev displacements ``||x_i - x0_i||_inf`` of the calibration plans
from the plans they were derived from. Pass it as ``budget=`` to
:func:`archlux.legalize`: the box is polyhedral, so the Frank-Wolfe oracle stays a
linear programme.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from archlux.errors import InvariantViolation
from archlux.types import Plan
from archlux.uq.conformal import conformal_quantile

__all__ = ["TrustRadius", "chebyshev_displacement", "trust_radius"]


@dataclass(frozen=True, slots=True)
class TrustRadius:
    """Radius of the trust region and the calibration it was read from.

    Attributes
    ----------
    radius : float
        Radius in metres, Chebyshev norm: the conformal quantile of the calibration
        displacements.
    alpha : float
        Level: under exchangeability, a new plan from the same process moves at most
        ``radius`` from its generated plan with probability ``>= 1 - alpha``.
    n : int
        Number of calibration displacements. Report it: for a small ``n`` the
        ``1 / (n + 1)`` term is not negligible.
    """

    radius: float
    alpha: float
    n: int


def chebyshev_displacement(plan: Plan, reference: Plan) -> float:
    """Largest coordinate move of any room between ``reference`` and ``plan``.

    Parameters
    ----------
    plan : Plan
        Plan after legalization.
    reference : Plan
        Plan it was derived from (the generated plan ``x0``), same room identifiers.

    Returns
    -------
    float
        ``max_i max(|dx_i|, |dy_i|, |dw_i|, |dh_i|)`` in metres.

    Raises
    ------
    InvariantViolation
        If the two plans do not have the same room identifiers.
    """
    before = {room.id: room for room in reference.rooms}
    after = {room.id: room for room in plan.rooms}
    if before.keys() != after.keys():
        missing = sorted(before.keys() ^ after.keys())
        raise InvariantViolation((f"room identifiers differ between the plans: {missing}",))
    moves = [
        abs(getattr(after[key], attr) - getattr(before[key], attr))
        for key in before
        for attr in ("x", "y", "w", "h")
    ]
    return float(max(moves, default=0.0))


def trust_radius(displacements: Sequence[float] | np.ndarray, alpha: float) -> TrustRadius:
    """Radius of the trust region, read off the calibration displacements.

    Parameters
    ----------
    displacements : sequence of float
        Chebyshev displacement of each calibration plan from its generated plan, in
        metres (see :func:`chebyshev_displacement`), on the calibration set of the
        conformal bound.
    alpha : float
        Level, the same as the conformal bound's.

    Returns
    -------
    TrustRadius
        The conformal quantile of the displacements, with ``alpha`` and ``n``.

    Raises
    ------
    InvariantViolation
        If a displacement is negative or not finite, or if the set is too small for
        ``alpha`` (see :func:`archlux.uq.conformal.conformal_quantile`).

    Examples
    --------
    >>> trust_radius([0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0], 0.2).radius
    4.5
    """
    values = np.asarray(displacements, dtype=float).ravel()
    if values.size and (not bool(np.all(np.isfinite(values))) or bool(np.any(values < 0.0))):
        raise InvariantViolation(("displacements must be finite and non-negative",))
    radius = conformal_quantile(values, alpha)
    return TrustRadius(radius=radius, alpha=float(alpha), n=int(values.size))
