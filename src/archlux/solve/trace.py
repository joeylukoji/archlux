"""Frank-Wolfe execution trace: one frozen row per iteration.

The trace is not a log: it is an output. It feeds the convergence figures of the article
and lets a diagnosis be replayed without running the solver again.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from archlux.arrays import FloatVector

__all__ = ["Iteration", "StopStatus", "Trace"]

StopStatus = Literal[
    "converged",
    "line_search_failed",
    "lp_not_optimal",
    "max_iter",
    "oracle_inconsistent",
    "stalled",
]
"""Why Frank-Wolfe stopped.

- ``converged``: the gap fell below the tolerance;
- ``line_search_failed``: no step along the chosen direction improved the objective;
- ``lp_not_optimal``: the linear oracle did not return an optimum;
- ``max_iter``: the iteration budget ran out;
- ``oracle_inconsistent``: the oracle said "optimal" but its vertex is outside the
  domain, or worse than the current point (a negative gap): it was not used;
- ``stalled``: the objective gained less than ``stall_tol`` over ``stall_window``
  consecutive steps (only when ``stall_window`` is set).

Only ``converged`` means the run reached its stationarity tolerance. Every status
returns a point of the domain: the **geometric** validity never depends on the status,
the stationarity claim always does.
"""


@dataclass(frozen=True, slots=True)
class Iteration:
    """State of the solver at one iteration.

    Attributes
    ----------
    value : float
        Surrogate value at ``x``.
    displacement : float
        ``max |x - reference|`` in metres, the L-infinity distance to the reference of
        the run (the proposed plan when given, the start otherwise).
    objective : float or None
        Objective Frank-Wolfe actually maximised at ``x``: the surrogate minus the
        displacement penalty. ``None`` means no penalty, i.e. equal to ``value``.
    """

    k: int
    value: float
    gap: float
    step: float
    away_step: bool
    lp_ms: float
    n_cuts: int
    x: FloatVector
    displacement: float = 0.0
    objective: float | None = None

    # --- French names, deprecated until 1.0.0 (ADR 0001) ---------------------------

    @property
    def valeur(self) -> float:
        """Deprecated alias of :attr:`value`.

        Returns
        -------
        float
            Same as :attr:`value`.
        """
        _deprecated_iteration("valeur", "value")
        return self.value

    @property
    def pas(self) -> float:  # lang-ok: deprecated French alias
        """Deprecated alias of :attr:`step`.

        Returns
        -------
        float
            Same as :attr:`step`.
        """
        _deprecated_iteration("pas", "step")  # lang-ok: deprecated French alias
        return self.step

    @property
    def temps_lp_ms(self) -> float:
        """Deprecated alias of :attr:`lp_ms`.

        Returns
        -------
        float
            Same as :attr:`lp_ms`.
        """
        _deprecated_iteration("temps_lp_ms", "lp_ms")
        return self.lp_ms

    @property
    def n_coupes(self) -> int:
        """Deprecated alias of :attr:`n_cuts`.

        Returns
        -------
        int
            Same as :attr:`n_cuts`.
        """
        _deprecated_iteration("n_coupes", "n_cuts")
        return self.n_cuts


def _deprecated_iteration(old: str, new: str) -> None:
    warnings.warn(
        f"Iteration.{old} is deprecated, use Iteration.{new} (ADR 0001)",
        DeprecationWarning,
        stacklevel=3,
    )


def _deprecated(old: str, new: str) -> None:
    warnings.warn(
        f"Trace.{old} is deprecated, use Trace.{new} (ADR 0001)",
        DeprecationWarning,
        stacklevel=3,
    )


@dataclass(frozen=True, slots=True)
class Trace:
    """Sequence of iterations, stop status, final gap, and time spent in the oracle.

    ``final_gap`` is the Frank-Wolfe gap at the returned point; the per-iteration gaps
    describe the point *before* each step.

    Attributes
    ----------
    parameters : tuple of (str, str)
        Every setting of the run, sorted by name, as strings: with the iterates, what
        it takes to replay the run (``max_iter``, ``tol``, ``budget``, ``strategy``...).
    active_bounds : tuple of str
        Constraints tight at the returned point, up to ``tolerances.FW_FEASIBILITY_M``:
        ``"<column>:lower"`` / ``"<column>:upper"`` for variable bounds (budget box
        included) and ``"row:<origin>"`` for rows of ``A``. What stopped the run when
        the surrogate still wanted to move.
    budget_active : tuple of str
        Columns whose displacement from the reference equals the budget at the returned
        point: the budget, not the geometry, is binding there. Empty without a budget.
    """

    iterations: tuple[Iteration, ...]
    status: StopStatus
    final_gap: float
    parameters: tuple[tuple[str, str], ...] = ()
    active_bounds: tuple[str, ...] = ()
    budget_active: tuple[str, ...] = ()

    @property
    def total_lp_ms(self) -> float:
        """Cumulated time in the LP solver.

        Separates the cost of the oracle from that of the surrogate: this is the measure
        that tells which of the two layers limits the 500 ms budget.

        Returns
        -------
        float
            Sum of the LP times of every iteration, in milliseconds.
        """
        return sum(i.lp_ms for i in self.iterations)

    @property
    def iterates(self) -> tuple[FloatVector, ...]:
        """Visited vectors, in order. All belong to the polytope.

        Returns
        -------
        tuple of numpy.ndarray
            The visited vectors, in order.
        """
        return tuple(step.x for step in self.iterations)

    @property
    def gaps(self) -> tuple[float, ...]:
        """Frank-Wolfe gaps, in order. The first may be infinite (start).

        Returns
        -------
        tuple of float
            The Frank-Wolfe gap of each iteration.
        """
        return tuple(step.gap for step in self.iterations)

    @property
    def values(self) -> tuple[float, ...]:
        """Surrogate values, in order.

        Returns
        -------
        tuple of float
            The surrogate value of each iteration.
        """
        return tuple(step.value for step in self.iterations)

    @property
    def objectives(self) -> tuple[float, ...]:
        """Penalised objective, in order; equal to :attr:`values` without a penalty.

        Returns
        -------
        tuple of float
            The objective Frank-Wolfe maximised, at each iteration.
        """
        return tuple(
            step.value if step.objective is None else step.objective for step in self.iterations
        )

    @property
    def displacements(self) -> tuple[float, ...]:
        """L-infinity distance of each iterate to the reference, in metres.

        Returns
        -------
        tuple of float
            ``max |x_k - reference|`` for every iteration.
        """
        return tuple(step.displacement for step in self.iterations)

    @property
    def converged(self) -> bool:
        """Whether the run reached its stationarity tolerance (``status == "converged"``).

        Returns
        -------
        bool
            ``True`` only for ``converged``.
        """
        return self.status == "converged"

    # --- French names, deprecated until 1.0.0 (ADR 0001) ---------------------------

    @property
    def iteres(self) -> tuple[FloatVector, ...]:
        """Deprecated alias of :attr:`iterates`.

        Returns
        -------
        tuple of numpy.ndarray
            Same as :attr:`iterates`.
        """
        _deprecated("iteres", "iterates")
        return self.iterates

    @property
    def ecarts(self) -> tuple[float, ...]:
        """Deprecated alias of :attr:`gaps`.

        Returns
        -------
        tuple of float
            Same as :attr:`gaps`.
        """
        _deprecated("ecarts", "gaps")
        return self.gaps

    @property
    def objectif(self) -> tuple[float, ...]:
        """Deprecated alias of :attr:`values`.

        Returns
        -------
        tuple of float
            Same as :attr:`values`.
        """
        _deprecated("objectif", "values")
        return self.values

    @property
    def temps_lp_total_ms(self) -> float:
        """Deprecated alias of :attr:`total_lp_ms`.

        Returns
        -------
        float
            Same as :attr:`total_lp_ms`.
        """
        _deprecated("temps_lp_total_ms", "total_lp_ms")
        return self.total_lp_ms
