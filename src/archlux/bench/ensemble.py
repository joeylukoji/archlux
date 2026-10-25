"""A bootstrap ensemble of surrogates: the first ``sigma_hat`` of the bench that varies.

Every surrogate shipped with archlux reports a **constant** uncertainty
(:meth:`archlux.light.base.DenseSurrogate.uncertainty` is a scale, not a prediction). With
a constant ``sigma_hat`` the pessimistic objective ``mu - q_hat * sigma`` differs from
``mu`` by a constant: its gradient is the same, the optimizer goes to the same plan, and
the "uncertainty penalty" ablation can only come out empty. That says nothing about the
mechanism, only about its input.

:class:`EnsembleSurrogate` averages ``K`` members and reports their spread (sample
standard deviation, floored) as ``sigma_hat``, which **does** depend on the plan.
:func:`fit_dense_ensemble` trains the members on bootstrap resamples of one training
set, with distinct seeds: the classic deep-ensemble recipe (Lakshminarayanan et al.,
2017), here on the residual network of :class:`~archlux.light.base.DenseSurrogate`.

What the spread is **not**: a calibrated standard deviation. Only the conformal step turns
it into an interval with a coverage claim; it is used here as a normalising score,
``|y - y_hat| / sigma_hat``, so that the interval widens where the members disagree.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from archlux.errors import InvariantViolation
from archlux.light.base import DenseSurrogate
from archlux.light.protocol import Glazing, Surrogate
from archlux.seeds import derive
from archlux.types import Indicator, Orientation

__all__ = ["SIGMA_FLOOR", "EnsembleSurrogate", "fit_dense_ensemble"]

SIGMA_FLOOR = 1e-6
"""Smallest reported spread, so that a normalised score never divides by zero."""


@dataclass(frozen=True, slots=True)
class EnsembleSurrogate:
    """Mean of ``members`` as the prediction, their spread as ``sigma_hat``.

    Attributes
    ----------
    members : tuple of Surrogate
        At least two surrogates of the same indicator.
    """

    members: tuple[Surrogate, ...]

    def __post_init__(self) -> None:
        """Refuse fewer than two members or mixed indicators.

        Raises
        ------
        InvariantViolation
            One member (no spread), or two indicators.
        """
        if len(self.members) < 2:
            raise InvariantViolation(("an ensemble needs >= 2 members",))
        if len({m.indicator for m in self.members}) != 1:
            raise InvariantViolation(("ensemble members model different indicators",))

    @property
    def indicator(self) -> Indicator:
        """Indicator shared by the members.

        Returns
        -------
        Indicator
            ``members[0].indicator``.
        """
        return self.members[0].indicator

    def _values(
        self, x: np.ndarray, orientation: Orientation, glazing: Glazing | None
    ) -> np.ndarray:
        """Value of every member.

        Parameters
        ----------
        x : numpy.ndarray
            Decision vector.
        orientation : Orientation
            Azimuth.
        glazing : Glazing or None
            Passed through.

        Returns
        -------
        numpy.ndarray
            One value per member.
        """
        return np.array([m.evaluate(x, orientation, glazing=glazing) for m in self.members])

    def evaluate(
        self, x: np.ndarray, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> float:
        """Mean of the members.

        Parameters
        ----------
        x : numpy.ndarray
            Decision vector.
        orientation : Orientation
            Azimuth.
        glazing : Glazing or None, optional
            Passed through.

        Returns
        -------
        float
            The ensemble prediction.
        """
        return float(np.mean(self._values(x, orientation, glazing)))

    def gradient(
        self, x: np.ndarray, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> np.ndarray:
        """Mean of the members' gradients (the gradient of the mean).

        Parameters
        ----------
        x : numpy.ndarray
            Decision vector.
        orientation : Orientation
            Azimuth.
        glazing : Glazing or None, optional
            Passed through.

        Returns
        -------
        numpy.ndarray
            Same dimension as ``x``.
        """
        grads = [np.asarray(m.gradient(x, orientation, glazing=glazing)) for m in self.members]
        return np.mean(np.stack(grads), axis=0)

    def uncertainty(
        self, x: np.ndarray, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> float:
        """Sample standard deviation of the members, floored at :data:`SIGMA_FLOOR`.

        Parameters
        ----------
        x : numpy.ndarray
            Decision vector.
        orientation : Orientation
            Azimuth.
        glazing : Glazing or None, optional
            Passed through.

        Returns
        -------
        float
            The spread; it varies with ``x`` and the azimuth.
        """
        return max(float(np.std(self._values(x, orientation, glazing), ddof=1)), SIGMA_FLOOR)


def fit_dense_ensemble(
    xs: Sequence[np.ndarray],
    ys: Sequence[float],
    orientations: Sequence[Orientation],
    *,
    k: int,
    seed: int,
    epochs: int = 60,
) -> EnsembleSurrogate:
    """Train ``k`` :class:`DenseSurrogate` on bootstrap resamples of one training set.

    Parameters
    ----------
    xs : sequence of numpy.ndarray
        Training decision vectors.
    ys : sequence of float
        Their reference values.
    orientations : sequence of Orientation
        Their azimuths.
    k : int
        Number of members, ``k >= 2``.
    seed : int
        Root seed; member ``i`` resamples and initialises with ``derive(seed, f"member/{i}")``.
    epochs : int, optional
        Passes over each resample.

    Returns
    -------
    EnsembleSurrogate
        The frozen ensemble.

    Raises
    ------
    InvariantViolation
        ``k < 2``, mismatched lengths, or fewer than two training points.
    """
    if k < 2:
        raise InvariantViolation(("k must be >= 2",))
    n = len(xs)
    if n < 2 or len(ys) != n or len(orientations) != n:
        raise InvariantViolation(("need >= 2 training points of matching lengths",))
    y = np.asarray(ys, dtype=float)
    members = []
    for i in range(k):
        member_seed = derive(seed, f"member/{i}")
        draw = np.random.default_rng(member_seed).integers(0, n, size=n)
        net = DenseSurrogate()
        net.fit(
            tuple(xs[j] for j in draw),
            y[draw],
            tuple(orientations[j] for j in draw),
            seed=member_seed,
            epochs=epochs,
        )
        members.append(net)
    return EnsembleSurrogate(members=tuple(members))
