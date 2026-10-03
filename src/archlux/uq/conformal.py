"""Conformal prediction: turn a point estimate into an interval with guaranteed coverage.

**The quantile is not ``numpy.quantile``.** Finite-sample coverage requires the index
``ceil((n + 1)(1 - alpha))`` on the sorted scores. Using the ordinary empirical
quantile gives intervals that are too narrow, hence coverage lower than announced —
and nothing signals it (`ARCHITECTURE.md` §10).
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field

import numpy as np

from archlux._deprecation import Alias, lazy_aliases, renamed_attributes, renamed_parameters
from archlux.errors import InvariantViolation
from archlux.types import INDICATOR_SENSE, REGIMES, Indicator, PerformanceBound, Regime

__all__ = [
    "Calibration",
    "ConformalCalibrator",
    "bound",
    "conformal_quantile",
    "dataset_fingerprint",
    "minimal_n_conformal",
]

_SIGMA_MIN = 1e-12


@renamed_attributes({"empreinte_jeu": "data_fingerprint"})
@dataclass(frozen=True, slots=True)
class Calibration:
    """Non-conformity scores from the calibration set, and nothing else.

    Attributes
    ----------
    empreinte_jeu : str
        ``sha256`` of the calibration **data set** (predictions, ground truths and
        uncertainties), not of the scores: two data sets can give the same scores, and
        only the data set can be checked or tested for leakage (PLAN.md batch 1.6).
        Published with the model: a conformal bound whose calibration set cannot be
        published is an unverifiable guarantee.
    """

    scores: np.ndarray
    alpha: float
    indicator: str
    data_fingerprint: str

    @property
    def n(self) -> int:
        """Size of the calibration set."""
        return int(self.scores.size)


def minimal_n_conformal(alpha: float) -> int:
    r"""Smallest calibration size that allows a finite bound at level ``alpha``.

    The conformal quantile takes rank ``k = ceil((n + 1)(1 - alpha))``. We need
    ``k <= n``, otherwise the requested rank falls outside the sample and the bound
    would be infinite. Since ``n`` is an integer, ``ceil(x) <= n`` is equivalent to
    ``x <= n``, hence

    .. math::

        (n + 1)(1 - \alpha) \le n
        \iff n \ge \frac{1}{\alpha} - 1 .

    At 90 % coverage we thus need ``n >= 9``, and at 95 % ``n >= 19``. A smaller
    calibration set does not make the guarantee false: it makes it **impossible**,
    and :func:`conformal_quantile` raises rather than publish an infinite bound.

    Parameters
    ----------
    alpha : float
        Target level, in ``]0, 1[``. Guaranteed coverage is ``>= 1 - alpha``.

    Returns
    -------
    int
        The smallest admissible ``n``.

    Raises
    ------
    InvariantViolation
        If ``alpha`` falls outside ``]0, 1[``.

    Examples
    --------
    >>> from archlux.uq.conformal import minimal_n_conformal
    >>> minimal_n_conformal(0.10), minimal_n_conformal(0.05)
    (9, 19)
    """
    if not 0.0 < alpha < 1.0:
        raise InvariantViolation((f"alpha outside ]0, 1[: {alpha}",))
    # Integer search rather than ceil(1/alpha - 1): in floating point, 1/0.1 is
    # 10.000000000000002 and rounding would give 10 instead of 9.
    n = max(1, int(1.0 / alpha) - 2)
    while math.ceil((n + 1) * (1.0 - alpha)) > n:
        n += 1
    return n


def conformal_quantile(scores: np.ndarray, alpha: float) -> float:
    """Conformal quantile, corrected for the finite sample.

    Parameters
    ----------
    scores : numpy.ndarray
        Non-conformity scores, one per calibration point.
    alpha : float
        Target level; guaranteed coverage is ``>= 1 - alpha``.

    Returns
    -------
    float
        The score of rank ``ceil((n + 1)(1 - alpha))`` in increasing order.

    Raises
    ------
    InvariantViolation
        If ``ceil((n + 1)(1 - alpha)) > n``: the calibration set is too small for the
        requested level. Explicit failure rather than a silent infinite bound.

    Notes
    -----
    The guarantee is **two-sided** under exchangeability and continuous scores:
    ``1 - alpha <= P(score <= q_hat) <= 1 - alpha + 1/(n + 1)``. It is therefore
    *marginal* (averaged over the draw of the calibration set), never conditional on
    the plan.

    **Ties** break nothing: the rank is taken on the increasing order, so a block of
    equal scores can only push ``q_hat`` up. Coverage stays ``>= 1 - alpha``; only the
    upper bound ``+ 1/(n + 1)`` stops holding, and the interval becomes conservative.
    No random tie-breaking is applied.
    """
    vector = np.asarray(scores, dtype=float).ravel()
    n = int(vector.size)
    if n == 0:
        raise InvariantViolation(("empty calibration set",))
    if not bool(np.all(np.isfinite(vector))):
        raise InvariantViolation(("non-finite calibration scores",))
    if not 0.0 < alpha < 1.0:
        raise InvariantViolation((f"alpha outside ]0, 1[: {alpha}",))
    rank = math.ceil((n + 1) * (1.0 - alpha))
    if rank > n:
        raise InvariantViolation((f"n={n} too small for alpha={alpha} (rank {rank} > n)",))
    order = np.sort(vector)
    return float(order[rank - 1])


def _indicator(indicator_name: str) -> Indicator:
    if indicator_name not in INDICATOR_SENSE:
        raise InvariantViolation((f"unknown indicator: {indicator_name!r}",))
    return indicator_name  # type: ignore[return-value]


def dataset_fingerprint(
    predictions: np.ndarray, truths: np.ndarray, uncertainties: np.ndarray
) -> str:
    """SHA-256 of a calibration data set, stable across platforms.

    Each column is hashed as little-endian float64 behind its name and length, so that
    swapping two columns or moving a value from one to the other changes the digest.
    """
    digest = hashlib.sha256(b"archlux-calibration-v1")
    for name, column in (
        ("predictions", predictions),
        ("truths", truths),
        ("uncertainties", uncertainties),
    ):
        values = np.ascontiguousarray(np.asarray(column, dtype="<f8").ravel())
        digest.update(f"{name}:{values.size};".encode())
        digest.update(values.tobytes())
    return digest.hexdigest()


def _regime(regime: str) -> Regime:
    # Matching by equality types the result on every mypy version, without an ignore.
    for known in REGIMES:
        if regime == known:
            return known
    raise InvariantViolation((f"unknown regime {regime!r}, expected {REGIMES}",))


def _scale(uncertainty: float) -> float:
    """Validate ``sigma_hat`` before turning it into a conformal margin.

    Scores are normalized (``|y - y_hat| / sigma``): the published margin only makes
    sense if ``sigma_hat`` is finite and **strictly positive**. Without this check,
    ``sigma_hat = 0`` publishes a zero-width interval while announcing coverage of
    ``1 - alpha``, and ``sigma_hat < 0`` publishes an inverted interval
    (``lower > upper``) — two false guarantees that nothing would flag.

    Raises
    ------
    InvariantViolation
        If ``uncertainty`` is not finite or is not ``> 0``.
    """
    scale = float(uncertainty)
    if not math.isfinite(scale):
        raise InvariantViolation((f"non-finite uncertainty: {uncertainty}",))
    if scale <= 0.0:
        raise InvariantViolation(
            (f"uncertainty must be > 0 to publish a conformal margin: {scale}",)
        )
    return max(scale, _SIGMA_MIN)


def _interval(
    prediction: float,
    margin: float,
    *,
    indicator: Indicator,
    coverage: float,
    n_calibration: int,
    regime: str,
) -> PerformanceBound:
    """Two-sided interval ``prediction +/- margin``; business sense picks the side published."""
    return PerformanceBound(
        indicator=indicator,
        value=float(prediction),
        lower=float(prediction) - margin,
        upper=float(prediction) + margin,
        coverage=coverage,
        n_calibration=n_calibration,
        regime=_regime(regime),
    )


@renamed_parameters({"valeur": "value", "incertitude": "uncertainty"})
def bound(
    value: float, calibration: Calibration, *, uncertainty: float, regime: Regime
) -> PerformanceBound:
    """Attach a conformal interval to a point estimate.

    Parameters
    ----------
    value : float
        Point estimate (same unit as the indicator).
    calibration : Calibration
        Non-conformity scores. If already normalized by ``sigma``, pass ``uncertainty``
        equal to ``sigma`` of the point to bound.
    uncertainty : float
        Local scale, **strictly positive**, and mandatory: the former default of 1 was
        only right for scores that are not normalized, while
        :meth:`ConformalCalibrator.fit` divides them by ``σ``; the default then
        published a margin at the wrong scale without warning. Pass ``σ̂`` of the point
        for normalized scores, ``1.0`` for raw ones.
    regime : {"exchangeable", "selected"}
        Whether the plan is exchangeable with the calibration set or was selected by
        the optimizer (:data:`archlux.types.Regime`). Mandatory: only the caller knows.

    Raises
    ------
    InvariantViolation
        If ``uncertainty`` is not finite or is not ``> 0``.

    Guarantees
    ----------
    - Performance: **probabilistic**, coverage ``>= 1 - alpha`` under the
      exchangeability assumption with the calibration set. ``PerformanceBound.coverage``
      carries the **nominal** level ``1 - alpha``, never a measured coverage. This
      assumption is **weakened** when the plan was selected by the optimizer to
      maximize the prediction; the project measures and publishes the actual
      coverage under selection.
    """
    q_hat = conformal_quantile(calibration.scores, calibration.alpha)
    margin = q_hat * _scale(uncertainty)
    return _interval(
        value,
        margin,
        indicator=_indicator(calibration.indicator),
        coverage=1.0 - calibration.alpha,
        n_calibration=calibration.n,
        regime=regime,
    )


@renamed_attributes({"empreinte_jeu": "data_fingerprint", "borne": "bound"})
@dataclass(slots=True)
class ConformalCalibrator:
    """One calibrator per indicator: sDA and ASE errors are not on the same scale.

    ``fit`` reads the calibration set **after** the model is frozen. ``q``, ``n`` and
    ``alpha`` are serialized with the weights.
    """

    indicator: Indicator = "sDA"
    q: float = 0.0
    n: int = 0
    alpha: float = 0.10
    data_fingerprint: str = ""
    scores: np.ndarray | None = field(default=None, repr=False, compare=False)

    @renamed_parameters({"verites": "truths", "incertitudes": "uncertainties"})
    def fit(
        self,
        predictions: np.ndarray,
        truths: np.ndarray,
        uncertainties: np.ndarray,
        *,
        alpha: float = 0.10,
    ) -> None:
        """Fit the quantile on normalized scores ``|y - y_hat| / sigma``.

        Parameters
        ----------
        predictions, verites, incertitudes : numpy.ndarray
            One scalar per plan, same length.
        alpha : float, optional
            Target level (default 0.10 -> 90 % coverage).
        """
        pred = np.asarray(predictions, dtype=float).ravel()
        truth = np.asarray(truths, dtype=float).ravel()
        raw = np.asarray(uncertainties, dtype=float).ravel()
        if pred.size != truth.size or pred.size != raw.size:
            raise InvariantViolation(
                ("predictions, truths and uncertainties have different lengths",)
            )
        if pred.size == 0:
            raise InvariantViolation(("empty calibration set",))
        if not bool(np.all(np.isfinite(raw))) or bool(np.any(raw < 0.0)):
            raise InvariantViolation(("uncertainties must be finite and non-negative",))
        sigma = np.maximum(raw, _SIGMA_MIN)
        scores = np.abs(truth - pred) / sigma
        self.q = conformal_quantile(scores, alpha)
        self.n = int(scores.size)
        self.alpha = float(alpha)
        # The data set as given, before the floor on sigma: anyone can recompute it.
        self.data_fingerprint = dataset_fingerprint(pred, truth, raw)
        self.scores = np.array(scores, dtype=float, copy=True)

    @renamed_parameters({"sens": "sense"})
    def bound(
        self,
        prediction: float,
        uncertainty: float,
        sense: str | None = None,
        *,
        regime: Regime,
    ) -> PerformanceBound:
        """Publish the conformal interval around ``prediction``.

        Parameters
        ----------
        prediction : float
            Point estimate.
        uncertainty : float
            ``sigma_hat`` at the same point, **strictly positive**: the fitted scores
            are normalized, so ``sigma_hat = 0`` would publish a zero-width interval
            announced at ``1 - alpha``, and ``sigma_hat < 0`` an inverted interval.
        sens : {">=", "<=", None}
            Must match the indicator (``"<="`` for ASE, ``">="`` otherwise).
            Default: inferred from ``indicator``. The published interval stays
            two-sided ``prediction +/- margin``; the report picks the side via
            ``indicator``. ``sens`` does not change the bounds — it only refuses
            inconsistency.
        regime : {"exchangeable", "selected"}
            See :func:`bound`.
        """
        if self.n < 1:
            raise InvariantViolation(("calibrator not fitted",))
        expected = INDICATOR_SENSE[self.indicator]
        if sense is None:
            sense = expected
        if sense not in (">=", "<="):
            raise InvariantViolation((f"unknown sens: {sense!r}",))
        if sense != expected:
            raise InvariantViolation(
                (f"sens {sense!r} incompatible with indicator {self.indicator}",)
            )
        margin = self.q * _scale(uncertainty)
        return _interval(
            prediction,
            margin,
            indicator=self.indicator,
            coverage=1.0 - self.alpha,
            n_calibration=self.n,
            regime=regime,
        )

    def snapshot(self) -> Calibration:
        """Freeze the scores and ``alpha`` for ``bound`` / the certificate.

        ``bound`` recomputes the conformal quantile from the scores; the data set
        fingerprint stays logged with the calibration.
        """
        if self.n < 1 or self.scores is None:
            raise InvariantViolation(("calibrator not fitted",))
        return Calibration(
            scores=np.array(self.scores, dtype=float, copy=True),
            alpha=self.alpha,
            indicator=self.indicator,
            data_fingerprint=self.data_fingerprint,
        )


__getattr__ = lazy_aliases(
    __name__,
    {
        "CalibrateurConforme": Alias(
            ConformalCalibrator, "archlux.uq.conformal.ConformalCalibrator"
        ),
        "borner": Alias(bound, "archlux.uq.conformal.bound"),
        "n_minimal_conforme": Alias(
            minimal_n_conformal, "archlux.uq.conformal.minimal_n_conformal"
        ),
        "quantile_conforme": Alias(conformal_quantile, "archlux.uq.conformal.conformal_quantile"),
    },
)
