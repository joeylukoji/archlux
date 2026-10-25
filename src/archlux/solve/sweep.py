"""Run Frank-Wolfe over a grid of budgets: what each budget buys, and what it costs.

A single setting (50 iterations, one displacement budget) says nothing about whether
the result depends on it. :func:`sweep` reruns the same start over every combination
of iteration budget, displacement budget and displacement penalty, and reports per run
its status, surrogate gain, displacement, whether the budget was binding, and time.

Time is wall-clock (``time.perf_counter``) and therefore not reproducible; every other
column is (same inputs, same output).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from itertools import product
from typing import TYPE_CHECKING

import numpy as np

from archlux.solve.frank_wolfe import frank_wolfe

if TYPE_CHECKING:
    from collections.abc import Sequence

    from archlux.arrays import FloatVector
    from archlux.geom.polytope import Polytope
    from archlux.light.protocol import Glazing, Surrogate
    from archlux.solve.trace import StopStatus
    from archlux.types import Orientation

__all__ = ["SweepRow", "success_rate", "sweep"]


@dataclass(frozen=True, slots=True)
class SweepRow:
    """One Frank-Wolfe run of a sweep.

    Attributes
    ----------
    max_iter : int
        Iteration budget of the run.
    budget : float or None
        Displacement budget, in metres, around the reference.
    penalty : float
        Displacement penalty weight.
    status : StopStatus
        Why the run stopped.
    iterations : int
        Iterations run.
    value : float
        Surrogate value at the returned point.
    gain : float
        ``value`` minus the surrogate value at the start.
    gap : float
        Frank-Wolfe gap at the returned point (``inf`` when unknown).
    displacement : float
        ``max |x - reference|``, in metres.
    budget_bound : bool
        Whether at least one variable ended on the budget box.
    time_ms : float
        Wall-clock time of the run, in milliseconds (not reproducible).
    """

    max_iter: int
    budget: float | None
    penalty: float
    status: StopStatus
    iterations: int
    value: float
    gain: float
    gap: float
    displacement: float
    budget_bound: bool
    time_ms: float


def sweep(
    poly: Polytope,
    surrogate: Surrogate,
    orientation: Orientation,
    start: FloatVector,
    *,
    max_iters: Sequence[int] = (5, 10, 25, 50, 100),
    budgets: Sequence[float | None] = (None,),
    penalties: Sequence[float] = (0.0,),
    reference: FloatVector | None = None,
    glazing: Glazing | None = None,
) -> tuple[SweepRow, ...]:
    """Run :func:`frank_wolfe` from ``start`` over every combination of the grid.

    Parameters
    ----------
    poly : Polytope
        Domain, **without** a budget box (the sweep adds each budget itself).
    surrogate : Surrogate
        Objective.
    orientation : Orientation
        Azimuth of the plan.
    start : numpy.ndarray
        Start point, in ``poly``.
    max_iters : sequence of int, optional
        Iteration budgets.
    budgets : sequence of float or None, optional
        Displacement budgets, in metres (``None``: no budget).
    penalties : sequence of float, optional
        Displacement penalty weights.
    reference : numpy.ndarray or None, optional
        Proposed plan, centre of the budgets and penalties; ``start`` by default.
    glazing : Glazing or None, optional
        Glazing passed to the surrogate.

    Returns
    -------
    tuple of SweepRow
        One row per ``(max_iter, budget, penalty)``, in grid order.

    Raises
    ------
    Infeasible
        A budget too small for the bounds of ``poly`` around ``reference``.
    InvariantViolation
        ``start`` outside ``poly`` or outside a budget box.

    Complexity
    ----------
    ``len(max_iters) * len(budgets) * len(penalties)`` runs of at most ``max_iter + 1``
    warm LPs each.
    """
    center = np.asarray(start if reference is None else reference, dtype=float)
    initial = float(
        surrogate.evaluate(np.asarray(start, dtype=float), orientation, glazing=glazing)
    )
    rows: list[SweepRow] = []
    for max_iter, budget, penalty in product(max_iters, budgets, penalties):
        clock = time.perf_counter()
        result = frank_wolfe(
            poly,
            surrogate,
            orientation,
            start,
            max_iter=max_iter,
            budget=budget,
            glazing=glazing,
            reference=center,
            penalty=penalty,
        )
        elapsed = 1000.0 * (time.perf_counter() - clock)
        rows.append(
            SweepRow(
                max_iter=max_iter,
                budget=budget,
                penalty=penalty,
                status=result.status,
                iterations=result.iterations,
                value=result.value,
                gain=result.value - initial,
                gap=result.gap,
                displacement=float(np.max(np.abs(result.x - center), initial=0.0)),
                budget_bound=bool(result.trace.budget_active),
                time_ms=elapsed,
            )
        )
    return tuple(rows)


def success_rate(rows: Sequence[SweepRow]) -> tuple[int, int]:
    """Converged runs over all runs, as a count pair (never a bare ratio).

    Parameters
    ----------
    rows : sequence of SweepRow
        Runs of a sweep.

    Returns
    -------
    tuple of int
        ``(converged, total)``. Pass it to a Wilson interval
        (:func:`archlux.export.wilson.wilson_interval`) to report a rate with its uncertainty.
    """
    return sum(row.status == "converged" for row in rows), len(rows)
