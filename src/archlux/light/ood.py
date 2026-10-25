"""Out-of-distribution detection: is this plan like the plans the surrogate learned from.

The optimizer does not sample plans at random: it walks towards the plans the surrogate
scores highest, and a surrogate's largest errors sit precisely where it has seen no
data. A plan far from the training distribution therefore gets its prediction flagged
``uncertain``, whatever the surrogate's own ``sigma`` says.

The test is a Mahalanobis distance in the space of
:func:`~archlux.light.base.descriptors` (a fixed-dimension summary of the plan, its
orientation and its glazing), with a ridge on the covariance: the synthetic corpus has
far fewer degrees of freedom than descriptors, so the plain covariance is singular. The
threshold is the finite-sample conformal quantile of the distances of a **calibration**
set, ``ceil((n + 1)(1 - alpha))``-th smallest (``ARCHITECTURE.md`` §10). Calibrating on
the training set itself is allowed but optimistic, and the envelope records it.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from archlux.errors import InvalidInput
from archlux.light.base import descriptors
from archlux.light.protocol import point_prediction

if TYPE_CHECKING:
    from archlux.arrays import FloatVector
    from archlux.light.protocol import Glazing, Surrogate
    from archlux.types import Orientation

__all__ = [
    "FeatureEnvelope",
    "FlaggedPrediction",
    "OODVerdict",
    "fit_envelope",
    "flagged_prediction",
]

_TINY = 1e-12


@dataclass(frozen=True, slots=True)
class OODVerdict:
    """Distance of a plan to the training distribution, and the decision.

    Attributes
    ----------
    distance : float
        Mahalanobis distance in descriptor space.
    threshold : float
        Calibrated threshold; ``inf`` when the calibration set was too small.
    uncertain : bool
        ``True`` when ``distance > threshold`` **or** the threshold is not calibrated.
    reason : str
        Plain-language reason.
    """

    distance: float
    threshold: float
    uncertain: bool
    reason: str


@dataclass(frozen=True, slots=True)
class FeatureEnvelope:
    """Training distribution of a surrogate, summarized in descriptor space.

    Attributes
    ----------
    mean : numpy.ndarray
        Mean of the training descriptors.
    scale : numpy.ndarray
        Standard deviation of each descriptor (floored), used to standardize.
    precision : numpy.ndarray
        Inverse of the ridge-regularized covariance of the standardized descriptors.
    threshold : float
        Conformal threshold on the distance.
    alpha : float
        Miscoverage level of the threshold.
    n_train, n_calibration : int
        Sizes of the fitting and calibration sets.
    calibrated_on_training : bool
        ``True`` when no separate calibration set was given (optimistic threshold).
    fingerprint : str
        SHA-256 of the training descriptors, to tie the envelope to its data.
    """

    mean: np.ndarray
    scale: np.ndarray
    precision: np.ndarray
    threshold: float
    alpha: float
    n_train: int
    n_calibration: int
    calibrated_on_training: bool
    fingerprint: str

    def distance(
        self, x: FloatVector, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> float:
        """Mahalanobis distance of a plan to the training mean.

        Parameters
        ----------
        x
            Decision vector.
        orientation
            Azimuth.
        glazing
            Openings, or ``None``.

        Returns
        -------
        float
            The distance.
        """
        z = (descriptors(np.asarray(x, dtype=float), orientation, glazing) - self.mean) / self.scale
        return float(math.sqrt(max(float(z @ self.precision @ z), 0.0)))

    def check(
        self, x: FloatVector, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> OODVerdict:
        """Decide whether a plan is out of the training distribution.

        Parameters
        ----------
        x
            Decision vector.
        orientation
            Azimuth.
        glazing
            Openings, or ``None``.

        Returns
        -------
        OODVerdict
            Distance, threshold and decision.
        """
        d = self.distance(x, orientation, glazing=glazing)
        if not math.isfinite(self.threshold):
            return OODVerdict(d, self.threshold, True, "threshold not calibrated: set too small")
        if d > self.threshold:
            return OODVerdict(
                d, self.threshold, True, "outside the training distribution: prediction uncertain"
            )
        return OODVerdict(d, self.threshold, False, "within the training distribution")


def _features(
    xs: Sequence[FloatVector],
    orientations: Sequence[Orientation],
    glazing: Sequence[Glazing | None] | None,
) -> np.ndarray:
    """Descriptor matrix, one row per plan.

    Parameters
    ----------
    xs : sequence of numpy.ndarray
        Decision vectors.
    orientations : sequence of Orientation
        Azimuths.
    glazing : sequence of Glazing or None, or None
        Openings per plan.

    Returns
    -------
    numpy.ndarray
        Shape ``(n, d)``.

    Raises
    ------
    InvalidInput
        On mismatched lengths or an empty set.
    """
    panes = list(glazing) if glazing is not None else [None] * len(xs)
    if not xs or len(xs) != len(orientations) or len(panes) != len(xs):
        raise InvalidInput("xs", "needs as many orientations and glazings as plans, and one plan")
    return np.stack(
        [
            descriptors(np.asarray(x, dtype=float), o, g)
            for x, o, g in zip(xs, orientations, panes, strict=True)
        ]
    )


def _conformal_threshold(distances: np.ndarray, alpha: float) -> float:
    """``ceil((n + 1)(1 - alpha))``-th smallest distance, ``inf`` if it does not exist.

    Parameters
    ----------
    distances : numpy.ndarray
        Calibration distances.
    alpha : float
        Miscoverage level.

    Returns
    -------
    float
        The threshold.
    """
    n = distances.size
    k = math.ceil((n + 1) * (1.0 - alpha))
    return float(np.sort(distances)[k - 1]) if k <= n else float("inf")


def fit_envelope(
    xs: Sequence[FloatVector],
    orientations: Sequence[Orientation],
    *,
    glazing: Sequence[Glazing | None] | None = None,
    calibration: tuple[Sequence[FloatVector], Sequence[Orientation]] | None = None,
    alpha: float = 0.05,
    ridge: float = 1e-2,
) -> FeatureEnvelope:
    """Fit the training envelope of a surrogate.

    Parameters
    ----------
    xs : sequence of numpy.ndarray
        Decision vectors of the **training** plans.
    orientations : sequence of Orientation
        Their azimuths.
    glazing : sequence of Glazing or None, optional
        Their openings.
    calibration : tuple, optional
        ``(xs, orientations)`` of held-out plans of the same distribution, used to set
        the threshold. ``None``: the training plans themselves (optimistic, recorded).
    alpha : float, optional
        Share of in-distribution plans allowed above the threshold.
    ridge : float, optional
        Added to the diagonal of the standardized covariance.

    Returns
    -------
    FeatureEnvelope
        The fitted envelope.
    """
    train = _features(xs, orientations, glazing)
    mean = train.mean(axis=0)
    scale = np.maximum(train.std(axis=0), 1e-6)
    z = (train - mean) / scale
    cov = np.atleast_2d(np.cov(z, rowvar=False)) if train.shape[0] > 1 else np.zeros((1, 1))
    if cov.shape[0] != z.shape[1]:
        cov = np.zeros((z.shape[1], z.shape[1]))
    precision = np.linalg.inv(cov + ridge * np.eye(z.shape[1]))
    held = train if calibration is None else _features(calibration[0], calibration[1], None)
    hz = (held - mean) / scale
    distances = np.sqrt(np.maximum(np.einsum("ij,jk,ik->i", hz, precision, hz), 0.0))
    return FeatureEnvelope(
        mean=mean,
        scale=scale,
        precision=precision,
        threshold=_conformal_threshold(distances, alpha),
        alpha=alpha,
        n_train=int(train.shape[0]),
        n_calibration=int(held.shape[0]),
        calibrated_on_training=calibration is None,
        fingerprint=hashlib.sha256(np.ascontiguousarray(train).tobytes()).hexdigest(),
    )


@dataclass(frozen=True, slots=True)
class FlaggedPrediction:
    """A point prediction with its out-of-distribution verdict attached.

    Attributes
    ----------
    mu, sigma : float
        Point prediction and predictive standard deviation of the surrogate.
    ood : OODVerdict
        Whether the plan is like the training plans.
    """

    mu: float
    sigma: float
    ood: OODVerdict

    @property
    def uncertain(self) -> bool:
        """Shortcut for ``ood.uncertain``.

        Returns
        -------
        bool
            ``True`` when the prediction must be reported as uncertain.
        """
        return self.ood.uncertain


def flagged_prediction(
    surrogate: Surrogate,
    envelope: FeatureEnvelope,
    x: FloatVector,
    orientation: Orientation,
    *,
    glazing: Glazing | None = None,
) -> FlaggedPrediction:
    """Predict, and say whether the prediction is out of distribution.

    Parameters
    ----------
    surrogate : Surrogate
        Model, possibly wrapped by an objective.
    envelope : FeatureEnvelope
        Training envelope of that model.
    x
        Decision vector.
    orientation
        Azimuth.
    glazing
        Openings, or ``None``.

    Returns
    -------
    FlaggedPrediction
        ``mu``, ``sigma`` and the verdict.
    """
    mu, sigma = point_prediction(surrogate, x, orientation, glazing=glazing)
    return FlaggedPrediction(mu, sigma, envelope.check(x, orientation, glazing=glazing))
