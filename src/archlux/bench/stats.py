"""Pure bench statistical tests (bootstrap, TOST, Holm, power)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from scipy import stats as scipy_stats

from archlux._deprecation import Alias, lazy_aliases, renamed_parameters
from archlux.errors import InvariantViolation

__all__ = ["Interval", "holm", "paired_bootstrap", "power", "tost"]


@dataclass(frozen=True, slots=True)
class Interval:
    """Point estimate and interval bounds."""

    value: float
    low: float
    high: float


def paired_bootstrap(
    a: Sequence[float],
    b: Sequence[float],
    *,
    seed: int,
    n_replications: int = 9999,
    alpha: float = 0.05,
) -> Interval:
    """Bootstrap confidence interval on the mean of paired differences."""
    if len(a) != len(b) or len(a) < 1:
        raise InvariantViolation(("a and b must have the same length >= 1",))
    if n_replications < 1:
        raise InvariantViolation(("n_replications must be >= 1",))
    diffs = np.asarray(a, dtype=float) - np.asarray(b, dtype=float)
    rng = np.random.default_rng(seed)
    n = len(diffs)
    echantillon = rng.choice(diffs, size=(n_replications, n), replace=True)
    moyens = echantillon.mean(axis=1)
    lo, hi = np.quantile(moyens, [alpha / 2.0, 1.0 - alpha / 2.0])
    return Interval(value=float(diffs.mean()), low=float(lo), high=float(hi))


def tost(
    a: Sequence[float],
    b: Sequence[float],
    *,
    delta: float,
    alpha: float = 0.05,
) -> tuple[bool, float]:
    """Equivalence TOST on the mean of paired differences.

    Returns
    -------
    tuple
        ``(equivalent, p)`` where ``p = max(p_inf, p_sup)``.
    """
    if len(a) != len(b) or len(a) < 2:
        raise InvariantViolation(("a and b must have the same length >= 2",))
    if delta <= 0.0:
        raise InvariantViolation(("delta must be > 0",))
    diffs = np.asarray(a, dtype=float) - np.asarray(b, dtype=float)
    n = len(diffs)
    moyenne = float(diffs.mean())
    ecart = float(diffs.std(ddof=1))
    if ecart == 0.0:
        equivalent = abs(moyenne) < delta
        return equivalent, 0.0 if equivalent else 1.0
    se = ecart / np.sqrt(n)
    t_inf = (moyenne - (-delta)) / se
    t_sup = (delta - moyenne) / se
    ddl = n - 1
    p_inf = float(1.0 - scipy_stats.t.cdf(t_inf, ddl))
    p_sup = float(1.0 - scipy_stats.t.cdf(t_sup, ddl))
    p = max(p_inf, p_sup)
    return p < alpha, p


@renamed_parameters({"p_valeurs": "p_values"})
def holm(p_values: Sequence[float], *, alpha: float = 0.05) -> tuple[bool, ...]:
    """Holm-Bonferroni correction for multiple comparisons.

    A paper table typically compares several methods across several orientation
    strata. Without correction, the probability that at least one of the ``m``
    tests comes out significant by chance tends to 1: at ``m = 16`` and
    ``alpha = 0.05``, it is already ``1 - 0.95**16 ~= 0.56``. Holm controls the
    **family-wise** error rate (FWER) without an independence assumption, unlike
    Benjamini-Hochberg which only controls the FDR.

    Parameters
    ----------
    p_values : Sequence[float]
        The ``m`` p-values of the family, in ``[0, 1]``.
    alpha : float, optional
        Targeted family-wise error rate.

    Returns
    -------
    tuple of bool
        ``rejected[i]`` for each p-value, **in input order**.

    Raises
    ------
    InvariantViolation
        Empty family, ``alpha`` outside ``]0, 1[``, or a p-value outside ``[0, 1]``.

    Complexity
    ----------
    ``O(m log m)`` (the sort dominates).

    Examples
    --------
    >>> from archlux.bench.stats import holm
    >>> holm([0.001, 0.04, 0.6])
    (True, False, False)
    """
    p = np.asarray(p_values, dtype=float)
    if p.size == 0:
        raise InvariantViolation(("empty family of p-values",))
    if not 0.0 < alpha < 1.0:
        raise InvariantViolation((f"alpha outside ]0, 1[: {alpha}",))
    if bool(np.any(p < 0.0) or np.any(p > 1.0)) or bool(np.any(np.isnan(p))):
        raise InvariantViolation(("p-values outside [0, 1]",))
    m = p.size
    ordre = np.argsort(p, kind="stable")
    seuils = alpha / (m - np.arange(m))
    sous_seuil = p[ordre] <= seuils
    # Holm stops at the **first** failure: everything after is kept, even if its
    # p-value falls back under its own threshold. The monotone cumulation forces
    # this stop.
    rejets_tries = np.logical_and.accumulate(sous_seuil)
    rejections = np.empty(m, dtype=bool)
    rejections[ordre] = rejets_tries
    return tuple(bool(v) for v in rejections)


@renamed_parameters({"effet": "effect"})
def power(
    effect: float,
    sigma: float,
    *,
    n: int,
    alpha: float = 0.05,
) -> float:
    """Approximate power of a two-sided one-sample t-test."""
    if n < 2:
        raise InvariantViolation(("n must be >= 2",))
    if sigma <= 0.0:
        raise InvariantViolation(("sigma must be > 0",))
    if not 0.0 < alpha < 1.0:
        raise InvariantViolation((f"alpha outside ]0, 1[: {alpha}",))
    ddl = n - 1
    se = sigma / np.sqrt(n)
    t_crit = float(scipy_stats.t.ppf(1.0 - alpha / 2.0, ddl))
    ncp = effect / se
    # Power = P(|T| > t_crit | ncp)
    p_bas = float(scipy_stats.nct.cdf(-t_crit, ddl, ncp))
    p_haut = float(1.0 - scipy_stats.nct.cdf(t_crit, ddl, ncp))
    return float(np.clip(p_bas + p_haut, 0.0, 1.0))


__getattr__ = lazy_aliases(
    __name__,
    {
        "Intervalle": Alias(Interval, "archlux.bench.stats.Interval"),
        "bootstrap_apparie": Alias(paired_bootstrap, "archlux.bench.stats.paired_bootstrap"),
        "puissance": Alias(power, "archlux.bench.stats.power"),
    },
)
