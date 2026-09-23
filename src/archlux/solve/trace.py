"""Frank-Wolfe execution trace: one frozen row per iteration.

The trace is not a log: it is an output. It feeds the convergence figures of the article
and lets a diagnosis be replayed without running the solver again.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np

__all__ = ["Iteration", "Trace"]


@dataclass(frozen=True, slots=True)
class Iteration:
    """State of the solver at one iteration."""

    k: int
    value: float
    gap: float
    step: float
    away_step: bool
    lp_ms: float
    n_cuts: int
    x: np.ndarray


def _deprecated(old: str, new: str) -> None:
    warnings.warn(
        f"Trace.{old} is deprecated, use Trace.{new} (ADR 0001)",
        DeprecationWarning,
        stacklevel=3,
    )


@dataclass(frozen=True, slots=True)
class Trace:
    """Sequence of iterations, with the total time spent in the oracle."""

    iterations: tuple[Iteration, ...]

    @property
    def total_lp_ms(self) -> float:
        """Cumulated time in the LP solver.

        Separates the cost of the oracle from that of the surrogate: this is the measure
        that tells which of the two layers limits the 500 ms budget.
        """
        return sum(i.lp_ms for i in self.iterations)

    @property
    def iterates(self) -> tuple[np.ndarray, ...]:
        """Visited vectors, in order. All belong to the polytope."""
        return tuple(step.x for step in self.iterations)

    @property
    def gaps(self) -> tuple[float, ...]:
        """Frank-Wolfe gaps, in order. The first may be infinite (start)."""
        return tuple(step.gap for step in self.iterations)

    @property
    def values(self) -> tuple[float, ...]:
        """Surrogate values, in order."""
        return tuple(step.value for step in self.iterations)

    # --- French names, deprecated until 1.0.0 (ADR 0001) ---------------------------

    @property
    def iteres(self) -> tuple[np.ndarray, ...]:
        """Deprecated alias of :attr:`iterates`."""
        _deprecated("iteres", "iterates")
        return self.iterates

    @property
    def ecarts(self) -> tuple[float, ...]:
        """Deprecated alias of :attr:`gaps`."""
        _deprecated("ecarts", "gaps")
        return self.gaps

    @property
    def objectif(self) -> tuple[float, ...]:
        """Deprecated alias of :attr:`values`."""
        _deprecated("objectif", "values")
        return self.values

    @property
    def temps_lp_total_ms(self) -> float:
        """Deprecated alias of :attr:`total_lp_ms`."""
        _deprecated("temps_lp_total_ms", "total_lp_ms")
        return self.total_lp_ms
