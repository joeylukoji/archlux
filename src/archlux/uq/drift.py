"""Drift control: say when the conformal guarantee stops applying.

Exchangeability with the calibration set is not a permanent property. A batch of
plans from a new generator can fall outside the calibrated domain; the bound is then
still computable, but it no longer guarantees anything. This module detects that and
says so.

``uq`` imports neither ``light`` nor ``solve``: :func:`measure_drift` works on
arrays that are already evaluated.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from archlux._deprecation import Alias, lazy_aliases
from archlux.errors import InvariantViolation
from archlux.uq.conformal import Calibration

__all__ = [
    "DriftDiagnostic",
    "DriftReport",
    "check_drift",
    "measure_drift",
]

_P_THRESHOLD = 0.05
_N_PERMUTATIONS = 199


@dataclass(frozen=True, slots=True)
class DriftDiagnostic:
    """Exchangeability verdict, with its statistic and threshold."""

    echangeable: bool
    statistique: float
    threshold: float
    n_observations: int
    message: str


@dataclass(frozen=True, slots=True)
class DriftReport:
    """Prediction - truth gap on **selected** plans, not on the calibration set.

    A growing positive drift means the optimizer is exploiting the surrogate's
    errors. This is not conformal coverage: exchangeability is doubtful here.
    """

    derive_moyenne: float
    tendance_pente: float
    tendance_pvalue: float
    n_echantillons: int


def check_drift(
    observations: np.ndarray, calibration: Calibration, *, seed: int
) -> DriftDiagnostic:
    """Test exchangeability of the observations with the calibration set.

    Parameters
    ----------
    observations : numpy.ndarray
        Non-conformity scores observed in production.
    calibration : Calibration
        Reference.
    seed : int
        Seed of the permutation test. **Mandatory, no default.**

    Returns
    -------
    DriftDiagnostic
        Readable verdict. A detected drift **invalidates the bound**, it does not
        widen it: the certificate must then carry ``NOT EVALUABLE``, never an
        interval.

    Notes
    -----
    What the test guarantees, and what it does not:

    - **Exact level.** The Monte-Carlo p-value ``(exceedances + 1) / (B + 1)`` with
      ``B = 199`` (Phipson & Smyth, 2010) is valid at finite distance; since
      ``0.05 x 200 = 10`` is an integer, rejecting at ``p <= 0.05`` gives a level of
      exactly 5 % under the null hypothesis of exchangeability.
    - **No multiplicity correction.** Each call is an independent test. A check run on
      every batch will drift toward an almost certain false positive
      (``1 - 0.95^k``). Continuous monitoring must go through a sequential test
      (e-value, conformal martingale mixture) or at least a corrected threshold.
    - **Power not characterized.** No power analysis accompanies the threshold: for
      small ``n_observations``, ``echangeable=True`` means "drift not detected", not
      "no drift". :func:`archlux.certify.bound.build_bound` nonetheless treats
      this boolean as authorization to publish.
    - **Poorly targeted statistic.** Kolmogorov-Smirnov is most sensitive to the
      center of the distribution, while conformal coverage depends only on the
      **upper tail** of the scores, near ``q_hat``. A drift that only thickens that
      tail is precisely the one that breaks coverage, and the one KS sees least well.
      A test dedicated to the tail (or directly a tracker of ``mean(score > q_hat)``)
      would be better aligned with the guarantee being protected.
    """
    obs = np.asarray(observations, dtype=float).ravel()
    cal = np.asarray(calibration.scores, dtype=float).ravel()
    if obs.size == 0 or cal.size == 0:
        raise InvariantViolation(("observations and calibration must be non-empty",))
    if not bool(np.all(np.isfinite(obs))) or not bool(np.all(np.isfinite(cal))):
        raise InvariantViolation(("non-finite scores for drift control",))
    from scipy.stats import ks_2samp  # lazy: scipy.stats costs 1.3 s at import

    # Kolmogorov-Smirnov (not a test of means): a variance drift also breaks
    # exchangeability, even with an unchanged mean.
    statistique = float(ks_2samp(obs, cal).statistic)
    rng = np.random.default_rng(seed)
    pooled = np.concatenate([obs, cal])
    n_obs = int(obs.size)
    exceedances = 0
    for _ in range(_N_PERMUTATIONS):
        rng.shuffle(pooled)
        permute = float(ks_2samp(pooled[:n_obs], pooled[n_obs:]).statistic)
        if permute >= statistique:
            exceedances += 1
    p_value = (exceedances + 1) / (_N_PERMUTATIONS + 1)
    echangeable = p_value > _P_THRESHOLD
    if echangeable:
        message = "exchangeability holds: the conformal bound remains interpretable"
    else:
        message = (
            "drift detected: exchangeability is rejected, "
            "the bound is no longer guaranteed (NOT EVALUABLE)"
        )
    return DriftDiagnostic(
        echangeable=echangeable,
        statistique=statistique,
        threshold=_P_THRESHOLD,
        n_observations=n_obs,
        message=message,
    )


def measure_drift(predictions: np.ndarray, verites: np.ndarray, *, seed: int) -> DriftReport:
    """Mean prediction - truth gap, and trend over the arrival order.

    Parameters
    ----------
    predictions, verites : numpy.ndarray
        Already computed evaluations (surrogate and frozen oracle), same length.
    seed : int
        Kept for the reproducible signature; the regression is deterministic.

    Returns
    -------
    DriftReport
        Positive ``derive_moyenne``: the surrogate overestimates the oracle.

    Notes
    -----
    ``tendance_pvalue`` comes from an ordinary least-squares regression on the
    arrival index: it assumes **independent and homoscedastic** gaps. On a sequence
    produced by an optimizer that reuses its iterates, the gaps are autocorrelated
    and this p-value is anti-conservative. Read it as a trend indicator, never as a
    formal test.
    """
    pred = np.asarray(predictions, dtype=float).ravel()
    truth = np.asarray(verites, dtype=float).ravel()
    if pred.size != truth.size or pred.size == 0:
        raise InvariantViolation(("predictions and truths have incompatible lengths",))
    _ = int(seed)
    slacks = pred - truth
    n = int(slacks.size)
    if n >= 3:
        from scipy.stats import linregress  # lazy, see controler_derive

        trend = linregress(np.arange(n, dtype=float), slacks)
        slope = float(trend.slope)
        p_value = float(trend.pvalue)
    else:
        slope, p_value = 0.0, 1.0
    return DriftReport(
        derive_moyenne=float(slacks.mean()),
        tendance_pente=slope,
        tendance_pvalue=p_value,
        n_echantillons=n,
    )


__getattr__ = lazy_aliases(
    __name__,
    {
        "DiagnosticDerive": Alias(DriftDiagnostic, "archlux.uq.drift.DriftDiagnostic"),
        "RapportDerive": Alias(DriftReport, "archlux.uq.drift.DriftReport"),
        "controler_derive": Alias(check_drift, "archlux.uq.drift.check_drift"),
        "mesurer_derive": Alias(measure_drift, "archlux.uq.drift.measure_drift"),
    },
)
