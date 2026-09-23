"""Trace d'exécution de Frank-Wolfe : une ligne par itération, gelée.

La trace n'est pas du journal : c'est une donnée de sortie. Elle alimente les figures de
convergence de l'article et permet de rejouer un diagnostic sans relancer le solveur.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np

__all__ = ["Iteration", "Trace"]


@dataclass(frozen=True, slots=True)
class Iteration:
    """État du solveur à une itération."""

    k: int
    valeur: float
    gap: float
    pas: float
    away_step: bool
    temps_lp_ms: float
    n_coupes: int
    x: np.ndarray


@dataclass(frozen=True, slots=True)
class Trace:
    """Suite d'itérations, avec le total de temps passé dans l'oracle."""

    iterations: tuple[Iteration, ...]

    @property
    def temps_lp_total_ms(self) -> float:
        """Temps cumulé dans le solveur LP.

        Sépare le coût de l'oracle de celui du substitut : c'est la mesure qui dit
        laquelle des deux couches limite le budget de 500 ms.
        """
        return sum(i.temps_lp_ms for i in self.iterations)

    @property
    def iteres(self) -> tuple[np.ndarray, ...]:
        """Vecteurs visités, dans l'ordre. Tous appartiennent au polytope."""
        return tuple(etape.x for etape in self.iterations)

    @property
    def ecarts(self) -> tuple[float, ...]:
        """Gaps de dualité, dans l'ordre. Le premier peut être infini (départ)."""
        return tuple(etape.gap for etape in self.iterations)

    @property
    def objectif(self) -> tuple[float, ...]:
        """Valeurs du substitut, dans l'ordre."""
        return tuple(etape.valeur for etape in self.iterations)
