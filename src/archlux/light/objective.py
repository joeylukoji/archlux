"""Daylight objective: the conformal bound, not the point prediction.

``J = μ̂ − q̂ · σ̂`` (sDA). Where the surrogate does not know, ``σ̂`` is large, the margin
widens, the objective drops, and the optimizer is discouraged from going there. The
safeguard is not bolted on: it follows from the uncertainty.

``q_hat`` is an already calibrated **float**. This module does not import ``uq``
(`ARCHITECTURE.md` §5: ``light`` ← ``types``, ``errors``, ``orient``).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from archlux._deprecation import renamed_attributes
from archlux.errors import InvariantViolation
from archlux.light.protocol import Glazing, Surrogate
from archlux.types import Indicator, Orientation

__all__ = ["Daylight"]

_EPS_SIGMA = 1e-5


@renamed_attributes({"q_chapeau": "q_hat", "pessimiste": "pessimistic"})
@dataclass(frozen=True, slots=True)
class Daylight:
    """Surrogate whose :meth:`evaluate` returns the pessimistic bound ``μ − q σ``.

    Implements :class:`~archlux.light.protocol.Surrogate`: Frank-Wolfe need not know that
    the objective is a bound rather than a prediction.
    """

    surrogate: Surrogate
    q_hat: float
    pessimistic: bool = True

    def __post_init__(self) -> None:
        """Refuse a negative quantile: the conformal margin does not reverse the sense."""
        if self.q_hat < 0.0:
            raise InvariantViolation(("q_hat must be ≥ 0",))

    @property
    def indicator(self) -> Indicator:
        """Name of the modelled indicator, delegated to the wrapped surrogate."""
        return self.surrogate.indicator

    def evaluate(
        self, x: np.ndarray, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> float:
        """Return ``μ̂ − q̂ σ̂`` if ``pessimistic``, otherwise ``μ̂`` alone.

        Parameters
        ----------
        x : numpy.ndarray
            Decision vector.
        orientation : Orientation
            Azimuth.
        glazing : Glazing or None, optional
            Glazing, forwarded unchanged to the wrapped surrogate.

        Returns
        -------
        float
            Objective to maximize. **Probabilistic**: a bound, not a proof.

        Notes
        -----
        For ASE, the surrogate must already return a **negative** value (contract of
        ``AnalyticSurrogate`` / ``SplitFluxOracle``). Then ``μ − qσ`` keeps the right
        sense under maximization: uncertainty worsens the objective. Do not wrap a raw
        positive ASE.
        """
        mu = float(self.surrogate.evaluate(x, orientation, glazing=glazing))
        if not self.pessimistic:
            return mu
        sigma = float(self.surrogate.uncertainty(x, orientation, glazing=glazing))
        return mu - self.q_hat * sigma

    def gradient(
        self, x: np.ndarray, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> np.ndarray:
        """``∇μ − q̂ ∇σ``. ``∇σ`` by centred finite differences (Nocedal §8.1)."""
        grad_mu = np.asarray(self.surrogate.gradient(x, orientation, glazing=glazing), dtype=float)
        if not self.pessimistic:
            return grad_mu
        return grad_mu - self.q_hat * self._uncertainty_gradient(x, orientation, glazing)

    def uncertainty(
        self, x: np.ndarray, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> float:
        """Standard deviation of the wrapped surrogate, unchanged."""
        return float(self.surrogate.uncertainty(x, orientation, glazing=glazing))

    def __call__(
        self, x: np.ndarray, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> tuple[float, np.ndarray]:
        """Return ``(J, ∇J)`` at once, same convention as :meth:`evaluate`."""
        return self.evaluate(x, orientation, glazing=glazing), self.gradient(
            x, orientation, glazing=glazing
        )

    def _uncertainty_gradient(
        self, x: np.ndarray, orientation: Orientation, glazing: Glazing | None
    ) -> np.ndarray:
        x0 = np.asarray(x, dtype=float).ravel()
        grad = np.empty_like(x0)
        for i in range(x0.size):
            plus = x0.copy()
            minus = x0.copy()
            plus[i] += _EPS_SIGMA
            minus[i] -= _EPS_SIGMA
            high = float(self.surrogate.uncertainty(plus, orientation, glazing=glazing))
            low = float(self.surrogate.uncertainty(minus, orientation, glazing=glazing))
            grad[i] = (high - low) / (2.0 * _EPS_SIGMA)
        return grad
