"""Wilson interval for a proportion (survival rate)."""

from __future__ import annotations

import math

from archlux._deprecation import Alias, lazy_aliases, renamed_parameters
from archlux.errors import InvariantViolation

__all__ = ["wilson_interval"]


@renamed_parameters({"succes": "successes"})
def wilson_interval(successes: int, n: int, *, z: float = 1.96) -> tuple[float, float]:
    """Wilson confidence interval for a proportion.

    Unlike the normal approximation, the bounds stay within ``[0, 1]`` even for
    small ``n`` or rates close to 0 / 1.

    At both extremes, the bounds are set **exactly** rather than computed. At
    ``p_hat = 0``, the formula analytically gives ``centre = margin = z^2/(2n)``: the
    subtraction cancels out in exact arithmetic, but the square root introduces an
    ulp of drift, and ``centre - margin`` comes out ~1e-17 **above** zero. The final
    ``max(0, ·)`` caught nothing — the value was positive — so the returned interval
    then did not contain its own point estimate:
    ``wilson_interval(0, 3)`` returned ``(4.9e-17, 0.561)`` for a zero rate,
    contradicting the ``0 <= lo <= rate <= hi <= 1`` contract of
    :func:`~archlux.export.survie.survival_rate`. Symmetrically, ``p_hat = 1`` gave
    ``hi = 0.9999999999999999``.

    Parameters
    ----------
    successes : int
        Number of successes (``0 <= successes <= n``).
    n : int
        Sample size (``>= 1``).
    z : float, optional
        Gaussian quantile (1.96 ~= 95%).

    Returns
    -------
    tuple of float
        ``(lower_bound, upper_bound)``, with
        ``0 <= lower_bound <= successes/n <= upper_bound <= 1``.

    Notes
    -----
    Without continuity correction: the interval is that of the raw Wilson score.

    Raises
    ------
    InvariantViolation
        ``n < 1``, ``successes`` outside ``[0, n]``, or ``z <= 0``.
    """
    if n < 1:
        raise InvariantViolation(("n must be >= 1",))
    if not 0 <= successes <= n:
        raise InvariantViolation((f"successes={successes} outside [0, {n}]",))
    if z <= 0.0:
        raise InvariantViolation(("z must be > 0",))
    phat = successes / n
    z2 = z * z
    denom = 1.0 + z2 / n
    centre = phat + z2 / (2.0 * n)
    marge = z * math.sqrt((phat * (1.0 - phat) + z2 / (4.0 * n)) / n)
    lo = 0.0 if successes == 0 else max(0.0, (centre - marge) / denom)
    hi = 1.0 if successes == n else min(1.0, (centre + marge) / denom)
    return lo, hi


__getattr__ = lazy_aliases(
    __name__,
    {
        "intervalle_wilson": Alias(wilson_interval, "archlux.export.wilson.wilson_interval"),
    },
)
