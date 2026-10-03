"""Objectif lumineux : la borne conforme, pas la prédiction ponctuelle.

``J = μ̂ − q̂ · σ̂`` (sDA). Là où le substitut ne sait pas, ``σ̂`` est grand, la
marge s'ouvre, l'objectif chute, et l'optimiseur est dissuadé d'y aller. Le garde-fou
n'est pas ajouté : il découle de l'incertitude.

``q_chapeau`` est un **flottant** déjà calibré. Ce module n'importe pas ``uq``
(`ARCHITECTURE.md` §5 : ``light`` ← ``types``, ``errors``, ``orient``).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from archlux.errors import InvariantViolation
from archlux.light.protocol import Glazing, Surrogate
from archlux.types import Indicator, Orientation

__all__ = ["Daylight"]

_EPS_SIGMA = 1e-5


@dataclass(frozen=True, slots=True)
class Daylight:
    """Substitut dont :meth:`evaluate` rend la borne pessimiste ``μ − q σ``.

    Implémente :class:`~archlux.light.protocol.Surrogate` : Frank-Wolfe n'a pas à
    savoir que l'objectif est une borne plutôt qu'une prédiction.
    """

    surrogate: Surrogate
    q_chapeau: float
    pessimiste: bool = True

    def __post_init__(self) -> None:
        """Refuser un quantile négatif : la marge conforme n'inverse pas le sens."""
        if self.q_chapeau < 0.0:
            raise InvariantViolation(("q_chapeau doit être ≥ 0",))

    @property
    def indicator(self) -> Indicator:
        """Nom de l'indicateur modélisé, délégué au substitut enveloppé."""
        return self.surrogate.indicator

    def evaluate(
        self, x: np.ndarray, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> float:
        """Rendre ``μ̂ − q̂ σ̂`` si ``pessimiste``, sinon ``μ̂`` seul.

        Parameters
        ----------
        x : numpy.ndarray
            Vecteur de décision.
        orientation : Orientation
            Azimut.
        glazing : Baies or None, optional
            Glazing, forwarded unchanged to the wrapped surrogate.

        Returns
        -------
        float
            Objectif à maximiser. **Probabiliste** : c'est une borne, pas une preuve.

        Notes
        -----
        Pour ASE, le substitut doit déjà renvoyer une valeur **négative**
        (contrat ``AnalyticSurrogate`` / ``SplitFluxOracle``). Alors
        ``μ − qσ`` reste le bon sens sous maximisation : l'incertitude
        détériore l'objectif. Ne pas envelopper un ASE positif brut.
        """
        mu = float(self.surrogate.evaluate(x, orientation, glazing=glazing))
        if not self.pessimiste:
            return mu
        sigma = float(self.surrogate.uncertainty(x, orientation, glazing=glazing))
        return mu - self.q_chapeau * sigma

    def gradient(
        self, x: np.ndarray, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> np.ndarray:
        """``∇μ − q̂ ∇σ``. ``∇σ`` par différences finies centrées (Nocedal §8.1)."""
        grad_mu = np.asarray(self.surrogate.gradient(x, orientation, glazing=glazing), dtype=float)
        if not self.pessimiste:
            return grad_mu
        return grad_mu - self.q_chapeau * self._uncertainty_gradient(x, orientation, glazing)

    def uncertainty(
        self, x: np.ndarray, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> float:
        """Écart-type du substitut enveloppé, inchangé."""
        return float(self.surrogate.uncertainty(x, orientation, glazing=glazing))

    def __call__(
        self, x: np.ndarray, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> tuple[float, np.ndarray]:
        """Rendre ``(J, ∇J)`` d'un coup, même convention que :meth:`evaluate`."""
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
