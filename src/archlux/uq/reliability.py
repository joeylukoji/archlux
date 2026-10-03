"""Reliability diagrams and CRPS score — with no matplotlib figure whatsoever.

The diagnostic is an array ``(nominal, empirique)``. Plotting it is the job of the
experiment notebook, not of the core.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from archlux._deprecation import Alias, lazy_aliases
from archlux.errors import InvariantViolation
from archlux.types import Regime
from archlux.uq.conformal import ConformalCalibrator, conformal_quantile

__all__ = [
    "CoverageReport",
    "crps",
    "measure_coverage",
    "reliability_diagram",
    "stratify_by_orientation",
]

_SIGMA_MIN = 1e-12
_N_SECTEURS = 8


def crps(predictions: np.ndarray, verites: np.ndarray, incertitudes: np.ndarray) -> float:
    """Mean Gaussian CRPS (Gneiting & Raftery), in the unit of the indicator.

    Parameters
    ----------
    predictions, verites, incertitudes : numpy.ndarray
        ``mu``, ``y``, ``sigma`` point by point.

    Returns
    -------
    float
        Smaller is better. A ``sigma`` too wide or too narrow degrades the score.
    """
    mu = np.asarray(predictions, dtype=float).ravel()
    y = np.asarray(verites, dtype=float).ravel()
    sigma = np.maximum(np.asarray(incertitudes, dtype=float).ravel(), _SIGMA_MIN)
    if mu.size != y.size or mu.size != sigma.size or mu.size == 0:
        raise InvariantViolation(("CRPS arrays have incompatible lengths",))
    from scipy.special import erf  # lazy: scipy.special costs 0.8 s at import

    z = (y - mu) / sigma
    pdf = np.exp(-0.5 * z * z) / math.sqrt(2.0 * math.pi)
    cdf = 0.5 * (1.0 + erf(z / math.sqrt(2.0)))
    termes = sigma * (z * (2.0 * cdf - 1.0) + 2.0 * pdf - 1.0 / math.sqrt(math.pi))
    return float(np.mean(termes))


def _check_diagram_inputs(cibles: np.ndarray, reference: np.ndarray) -> None:
    """Raise on caller errors, so that ``nan`` only ever means "n too small"."""
    if not bool(np.all((cibles > 0.0) & (cibles < 1.0))):
        raise InvariantViolation(("nominal levels outside ]0, 1[",))
    if reference.size == 0 or not bool(np.all(np.isfinite(reference))):
        raise InvariantViolation(("reference scores empty or non-finite",))


def reliability_diagram(
    predictions: np.ndarray,
    verites: np.ndarray,
    incertitudes: np.ndarray,
    niveaux: np.ndarray | None = None,
    *,
    scores_calibration: np.ndarray | None = None,
) -> np.ndarray:
    """Empirical coverage as a function of the nominal coverage.

    Parameters
    ----------
    predictions, verites, incertitudes : numpy.ndarray
        Same convention as :func:`crps`. These are the **evaluated** points.
    niveaux : numpy.ndarray or None, optional
        Nominal levels in ``(0, 1)``. Default: 20 points from 0.50 to 0.99.
    scores_calibration : numpy.ndarray or None, optional
        Non-conformity scores from a **disjoint** calibration set. If given, the
        conformal quantiles are drawn from it and coverage is measured out of
        sample: the diagram becomes informative. If absent (default), the historical
        behavior is kept — see the notes.

    Returns
    -------
    numpy.ndarray
        Shape ``(n_niveaux, 2)``: column 0 = nominal, column 1 = empirical. Levels too
        demanding for ``n`` receive ``nan``.

    Raises
    ------
    InvariantViolation
        If the arrays have incompatible lengths, a level lies outside ``]0, 1[``, or
        the reference scores are empty or non-finite (e.g. a ``nan`` truth).

    Notes
    -----
    **Without ``scores_calibration``, the empirical column is a tautology.** The
    quantile ``q_hat`` is then computed on the very scores whose coverage is being
    measured; by construction, ``mean(scores <= q_hat) = ceil((n + 1)(1 - alpha)) / n``,
    regardless of the quality of ``sigma_hat``. A constant, aberrant, or randomly
    drawn ``sigma_hat`` gives exactly the same curve. This mode is therefore only
    useful to check the quantile arithmetic, never to validate calibration: any
    published figure must pass a disjoint calibration set.
    """
    pred = np.asarray(predictions, dtype=float).ravel()
    verite = np.asarray(verites, dtype=float).ravel()
    sigma = np.maximum(np.asarray(incertitudes, dtype=float).ravel(), _SIGMA_MIN)
    if pred.size != verite.size or pred.size != sigma.size or pred.size == 0:
        raise InvariantViolation(("diagram arrays have incompatible lengths",))
    if niveaux is None:
        cibles = np.linspace(0.50, 0.99, 20)
    else:
        cibles = np.asarray(niveaux, dtype=float).ravel()
    scores = np.abs(verite - pred) / sigma
    reference = (
        scores
        if scores_calibration is None
        else np.asarray(scores_calibration, dtype=float).ravel()
    )
    _check_diagram_inputs(cibles, reference)
    n_reference = int(reference.size)
    lignes: list[list[float]] = []
    for gamma in cibles:
        alpha = 1.0 - float(gamma)
        if math.ceil((n_reference + 1) * (1.0 - alpha)) > n_reference:
            lignes.append([float(gamma), float("nan")])  # documented: n too small
            continue
        q_chapeau = conformal_quantile(reference, alpha)
        empirique = float(np.mean(scores <= q_chapeau))
        lignes.append([float(gamma), empirique])
    return np.asarray(lignes, dtype=float)


def stratify_by_orientation(
    degres: np.ndarray, *, n_secteurs: int = _N_SECTEURS
) -> dict[int, np.ndarray]:
    """Indices per azimuth sector, for stratified coverage.

    Parameters
    ----------
    degres : numpy.ndarray
        Azimuths in degrees.
    n_secteurs : int, optional
        Number of sectors (default 8).

    Returns
    -------
    dict of int to numpy.ndarray
        Sector -> indices. Sector ``k`` covers ``[k*360/n, (k+1)*360/n[``.

    Notes
    -----
    Sectors are **edge-aligned**, not centered: sector 0 is ``[0deg, 45deg[`` and not
    the "N" compass rose ``[-22.5deg, 22.5deg[``. Two azimuths close to north (1deg
    and 359deg) therefore fall in different sectors.
    :func:`archlux.orient.circular.stratify` centers its sectors instead and names
    them ``N, NE, ...``: the two partitions are **not** interchangeable. Here only the
    partition matters (coverage by stratum), not the sector's name.
    """
    if n_secteurs < 2:
        raise InvariantViolation(("n_secteurs must be >= 2",))
    angles = np.asarray(degres, dtype=float).ravel() % 360.0
    largeur = 360.0 / float(n_secteurs)
    bacs = np.floor(angles / largeur).astype(int)
    bacs = np.clip(bacs, 0, n_secteurs - 1)
    return {k: np.flatnonzero(bacs == k) for k in range(n_secteurs)}


@dataclass(frozen=True, slots=True)
class CoverageReport:
    """Empirical coverage of conformal intervals on a sample, and how wide they are.

    Attributes
    ----------
    n : int
        Sample size.
    coverage : float
        Share of truths inside ``[borne_inf, borne_sup]``.
    mean_width : float
        Mean interval width, in the unit of the indicator.
    target_std : float
        Standard deviation of the truths (``ddof=1``): an interval wider than this says
        less than "somewhere in the usual range" (PLAN.md phase 2, J5).
    coverage_low, coverage_high : float
        Clopper-Pearson 95 % interval of ``coverage`` (``ARCHITECTURE.md`` §7: a metric
        is never a bare scalar). It is about this sample only, given the calibration.
    """

    n: int
    coverage: float
    mean_width: float
    target_std: float
    coverage_low: float
    coverage_high: float

    @property
    def width_over_std(self) -> float:
        """Mean width in units of the target spread; ``inf`` for a constant target."""
        return self.mean_width / self.target_std if self.target_std > 0.0 else math.inf


def measure_coverage(
    calibrator: ConformalCalibrator,
    predictions: np.ndarray,
    truths: np.ndarray,
    uncertainties: np.ndarray,
    *,
    regime: Regime,
) -> CoverageReport:
    """Bound every prediction and count the truths inside (AUDIT.md M12).

    Parameters
    ----------
    calibrator : ConformalCalibrator
        Fitted calibrator.
    predictions, truths, uncertainties : numpy.ndarray
        ``mu``, the oracle value and ``sigma``, point by point (the order of
        :meth:`ConformalCalibrator.fit`), on a sample **never used for calibration**.
    regime : {"exchangeable", "selected"}
        Regime of the sample: ``"selected"`` when an optimizer chose the plans.

    Returns
    -------
    CoverageReport

    Raises
    ------
    InvariantViolation
        Arrays of different lengths, fewer than two points, a non-finite value, or an
        uncertainty that is not strictly positive (``borne`` would refuse it midway).
    """
    mu, sigma, y = (
        np.asarray(a, dtype=float).ravel() for a in (predictions, uncertainties, truths)
    )
    if not mu.size == sigma.size == y.size or mu.size < 2:
        raise InvariantViolation(
            (f"need >= 2 aligned points, got {mu.size}, {sigma.size}, {y.size}",)
        )
    if not (np.isfinite(mu).all() and np.isfinite(y).all() and np.isfinite(sigma).all()):
        raise InvariantViolation(("predictions, truths and uncertainties must be finite",))
    if (sigma <= 0.0).any():
        raise InvariantViolation(("every uncertainty must be strictly positive",))
    bounds = [
        calibrator.borne(float(m), float(s), regime=regime) for m, s in zip(mu, sigma, strict=True)
    ]
    inside = [b.lower <= t <= b.upper for b, t in zip(bounds, y, strict=True)]
    from scipy.stats import beta  # lazy: scipy.stats costs 1.3 s at import

    k, n = int(np.sum(inside)), int(mu.size)
    return CoverageReport(
        n=n,
        coverage=k / n,
        mean_width=float(np.mean([b.upper - b.lower for b in bounds])),
        target_std=float(np.std(y, ddof=1)),
        coverage_low=float(beta.ppf(0.025, k, n - k + 1)) if k > 0 else 0.0,
        coverage_high=float(beta.ppf(0.975, k + 1, n - k)) if k < n else 1.0,
    )


__getattr__ = lazy_aliases(
    __name__,
    {
        "diagramme_fiabilite": Alias(
            reliability_diagram, "archlux.uq.reliability.reliability_diagram"
        ),
        "stratifier_par_orientation": Alias(
            stratify_by_orientation, "archlux.uq.reliability.stratify_by_orientation"
        ),
    },
)
