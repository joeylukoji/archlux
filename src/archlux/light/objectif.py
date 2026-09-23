"""Objectif lumineux : la borne conforme, pas la prédiction ponctuelle.

``J = μ̂ − q̂ · σ̂`` (sDA). Là où le substitut ne sait pas, ``σ̂`` est grand, la
marge s'ouvre, l'objectif chute, et l'optimiseur est dissuadé d'y aller. Le garde-fou
n'est pas ajouté : il découle de l'incertitude.

``q_chapeau`` est un **flottant** déjà calibré. Ce module n'importe pas ``uq``
(`ARCHITECTURE.md` §5 : ``light`` ← ``types``, ``erreurs``, ``orient``).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from archlux.erreurs import InvariantViole
from archlux.light.protocole import Substitut
from archlux.types import Orientation

__all__ = ["Daylight"]

_EPS_SIGMA = 1e-5


@dataclass(slots=True)
class Daylight:
    """Substitut dont :meth:`evaluer` rend la borne pessimiste ``μ − q σ``.

    Implémente :class:`~archlux.light.protocole.Substitut` : Frank-Wolfe n'a pas à
    savoir que l'objectif est une borne plutôt qu'une prédiction.
    """

    substitut: Substitut
    q_chapeau: float
    pessimiste: bool = True

    def __post_init__(self) -> None:
        """Refuser un quantile négatif : la marge conforme n'inverse pas le sens."""
        if self.q_chapeau < 0.0:
            raise InvariantViole(("q_chapeau doit être ≥ 0",))

    @property
    def indicateur(self) -> str:
        """Nom de l'indicateur modélisé, délégué au substitut enveloppé."""
        return self.substitut.indicateur

    def evaluer(self, x: np.ndarray, orientation: Orientation) -> float:
        """Rendre ``μ̂ − q̂ σ̂`` si ``pessimiste``, sinon ``μ̂`` seul.

        Parameters
        ----------
        x : numpy.ndarray
            Vecteur de décision.
        orientation : Orientation
            Azimut.

        Returns
        -------
        float
            Objectif à maximiser. **Probabiliste** : c'est une borne, pas une preuve.

        Notes
        -----
        Pour ASE, le substitut doit déjà renvoyer une valeur **négative**
        (contrat ``SubstitutAnalytique`` / ``SimulateurExact``). Alors
        ``μ − qσ`` reste le bon sens sous maximisation : l'incertitude
        détériore l'objectif. Ne pas envelopper un ASE positif brut.
        """
        mu = float(self.substitut.evaluer(x, orientation))
        if not self.pessimiste:
            return mu
        return mu - self.q_chapeau * float(self.substitut.incertitude(x, orientation))

    def gradient(self, x: np.ndarray, orientation: Orientation) -> np.ndarray:
        """``∇μ − q̂ ∇σ``. ``∇σ`` par différences finies centrées (Nocedal §8.1)."""
        grad_mu = np.asarray(self.substitut.gradient(x, orientation), dtype=float)
        if not self.pessimiste:
            return grad_mu
        return grad_mu - self.q_chapeau * self._gradient_incertitude(x, orientation)

    def incertitude(self, x: np.ndarray, orientation: Orientation) -> float:
        """Écart-type du substitut enveloppé, inchangé."""
        return float(self.substitut.incertitude(x, orientation))

    def __call__(
        self, x: np.ndarray, orientation: Orientation
    ) -> tuple[float, np.ndarray]:
        """Rendre ``(J, ∇J)`` d'un coup, même convention que :meth:`evaluer`."""
        return self.evaluer(x, orientation), self.gradient(x, orientation)

    def _gradient_incertitude(
        self, x: np.ndarray, orientation: Orientation
    ) -> np.ndarray:
        x0 = np.asarray(x, dtype=float).ravel()
        grad = np.empty_like(x0)
        for i in range(x0.size):
            plus = x0.copy()
            moins = x0.copy()
            plus[i] += _EPS_SIGMA
            moins[i] -= _EPS_SIGMA
            haut = float(self.substitut.incertitude(plus, orientation))
            bas = float(self.substitut.incertitude(moins, orientation))
            grad[i] = (haut - bas) / (2.0 * _EPS_SIGMA)
        return grad
