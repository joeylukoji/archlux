"""Frank-Wolfe: maximize a surrogate over the polytope, never leaving the valid set.

The algorithm is chosen for a structural reason, not for convenience: its linear oracle
**is** the legalization solver. Each iteration solves exactly the LP of a classic
legalization, with another cost vector. There is therefore a single solver in the whole
project, and every iterate is a valid plan: no projection, no illegal intermediate step.

Dependencies: ``types``, ``geom``, ``lmo``, and the **protocol** ``light.protocole``.
Never a concrete surrogate implementation.

Formulas: ``docs/formules/frank-wolfe.md``.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Protocol

import numpy as np

from archlux.arrays import VecteurF
from archlux.errors import Infeasible, InvariantViolation
from archlux.geom.polytope import Polytope
from archlux.lmo.solveur import solve
from archlux.solve.trace import Iteration, StopStatus, Trace

if TYPE_CHECKING:
    from archlux.light.protocole import Glazing, Surrogate
    from archlux.lmo.solveur import LPSolution
    from archlux.types import Orientation

__all__ = [
    "AwayStepStrategy",
    "FrankWolfeResult",
    "StepStrategy",
    "frank_wolfe",
    "restrict_to_budget",
]

_MIN_WEIGHT = 1e-12


@dataclass(frozen=True, slots=True)
class FrankWolfeResult:
    """Final iterate, optimality diagnostics and trace.

    Attributes
    ----------
    gap : float
        Frank-Wolfe gap ``<grad f(x), s - x>`` **at the returned x**, ``inf`` if no LP
        succeeded. It is a first-order **stationarity** measure. It bounds the distance
        to the optimum only for a concave surrogate, and none of the shipped surrogates
        is concave (AUDIT.md §5.1): never read it as an optimality certificate.
    status : StopStatus
        Why the run stopped (see :data:`archlux.solve.trace.StopStatus`).
    iterations : int
        Number of Frank-Wolfe iterations run (the initial entry ``k = -1`` of the trace
        is not counted).
    duals : numpy.ndarray or None
        Dual prices of the last LP, aligned with the rows of ``poly.A``. Equalities made
        by :func:`archlux.geom.polytope.freeze_contacts` are not included, so the dual
        diagnosis of a performance run is often empty.
    """

    x: VecteurF
    value: float
    gap: float
    status: StopStatus
    iterations: int
    trace: Trace
    duals: VecteurF | None = None


def restrict_to_budget(
    poly: Polytope, centre: VecteurF, radius: float, *, keep: VecteurF | None = None
) -> Polytope:
    """Intersection of the polytope with the box ``‖x − centre‖_∞ ≤ radius``.

    ``centre`` must be the **proposed** plan, so that the budget is spent once over the
    whole legalization, not once per pass.

    ``keep`` is a point the box must contain even if it exceeds the radius by a solver
    tolerance: the result of a previous pass, which met the same budget only up to the
    LP tolerance (a saturated budget). Without it, that point could fall outside the box
    and make the domain empty for no real reason.

    Raises
    ------
    Infeasible
        The box does not intersect the bounds of some variable: the budget is too small
        for this plan. An input problem, not an internal error.
    """
    names = {column: name for name, column in poly.index.items()}
    bounds: list[tuple[float, float]] = []
    for i, (lo, hi) in enumerate(poly.bounds):
        low = max(lo, float(centre[i]) - radius)
        high = min(hi, float(centre[i]) + radius)
        if keep is not None:
            low, high = min(low, float(keep[i])), max(high, float(keep[i]))
        if low > high + 1e-12:
            label = names.get(i, f"column {i}")
            raise Infeasible(
                farkas_certificate=None,
                origins=(f"budget {radius} m cannot reach the bounds of {label}",),
            )
        bounds.append((low, high))
    return replace(poly, bounds=tuple(bounds))


def _vertex_index(vertices: list[VecteurF], candidate: VecteurF) -> int | None:
    """Index of an already stored vertex, up to tolerance."""
    for rank, vertex in enumerate(vertices):
        if np.allclose(vertex, candidate, atol=1e-9, rtol=0.0):
            return rank
    return None


def _normalize(weights: list[float]) -> None:
    """Scale the weights so that they sum to 1, in place.

    Numerically null masses are filtered **before** the call, by the caller, which alone
    can drop the matching vertex at the same time: pruning weights here would
    desynchronize the two lists.
    """
    total = sum(weights)
    if total <= 0.0:
        return
    for rank, mass in enumerate(weights):
        weights[rank] = mass / total


class StepStrategy(Protocol):
    """The direction and its maximum step, computed once per iteration.

    Injectable so a new step rule (e.g. pairwise Frank-Wolfe) does not require editing
    :func:`frank_wolfe` itself, only a new class satisfying this protocol.
    """

    def propose(
        self,
        gradient: VecteurF,
        x: VecteurF,
        fw_vertex: VecteurF,
        vertices: list[VecteurF],
        weights: list[float],
    ) -> tuple[VecteurF, float, bool, int | None]:
        """Direction, its ``gamma_max``, whether it is an away step, and the away index."""
        ...


def _step_away(
    gradient: VecteurF,
    x: VecteurF,
    fw_direction: VecteurF,
    vertices: list[VecteurF],
    weights: list[float],
) -> tuple[VecteurF, float, bool, int | None]:
    """Away-step direction (Lacoste-Julien & Jaggi 2015), or the plain one.

    Away is taken when it improves on the plain Frank-Wolfe direction and the worst
    active vertex still has mass to give up.
    """
    if len(vertices) <= 1:
        return fw_direction, 1.0, False, None
    scores = [float(gradient @ vertex) for vertex in vertices]
    away_index = int(np.argmin(scores))
    away_direction = x - vertices[away_index]
    if (
        float(gradient @ away_direction) > float(gradient @ fw_direction)
        and weights[away_index] < 1.0 - _MIN_WEIGHT
    ):
        gamma_max = weights[away_index] / (1.0 - weights[away_index])
        return away_direction, gamma_max, True, away_index
    return fw_direction, 1.0, False, None


@dataclass(frozen=True, slots=True)
class AwayStepStrategy:
    """The built-in strategy: away steps when ``enabled``, plain Frank-Wolfe otherwise."""

    enabled: bool = True

    def propose(
        self,
        gradient: VecteurF,
        x: VecteurF,
        fw_vertex: VecteurF,
        vertices: list[VecteurF],
        weights: list[float],
    ) -> tuple[VecteurF, float, bool, int | None]:
        """See :class:`StepStrategy`."""
        fw_direction = fw_vertex - x
        if not self.enabled:
            return fw_direction, 1.0, False, None
        return _step_away(gradient, x, fw_direction, vertices, weights)


def _final_diagnostics(
    surrogate: Surrogate,
    orientation: Orientation,
    domain: Polytope,
    x: VecteurF,
    status: StopStatus,
    last_oracle: LPSolution | None,
    gap: float,
    *,
    glazing: Glazing | None,
) -> tuple[float, VecteurF | None]:
    """The gap and duals at the returned ``x``: one extra, warm LP.

    On ``max_iter``, the last step moved ``x`` after its LP, so that LP's gap and duals
    describe the *previous* point: an extra solve is needed here. On any other stop, the
    last LP already describes ``x``, and only its duals (not yet requested) are missing.
    """
    if status == "max_iter" and last_oracle is not None:
        gradient = np.asarray(surrogate.gradient(x, orientation, glazing=glazing), dtype=float)
        final = solve(domain, -gradient, start=x, duals=True)
        if final.status != "optimal":
            return float("inf"), None  # the previous gap describes the previous point
        return float(gradient @ (final.x - x)), final.duals
    if last_oracle is not None and last_oracle.status == "optimal":
        gradient = np.asarray(surrogate.gradient(x, orientation, glazing=glazing), dtype=float)
        extra = solve(domain, -gradient, start=x, duals=True)
        return gap, (extra.duals if extra.status == "optimal" else None)
    return gap, None


def _line_search(
    surrogate: Surrogate,
    orientation: Orientation,
    x: VecteurF,
    value: float,
    direction: VecteurF,
    gamma_max: float,
    k: int,
    *,
    glazing: Glazing | None,
) -> tuple[VecteurF, float, float] | None:
    """Backtrack from ``2/(k+2)`` (halved while the surrogate would decrease).

    Returns ``(candidate, new_value, gamma)``, or ``None`` if no step in 12 tries
    improved the surrogate (``status = "line_search_failed"`` for the caller).
    """
    gamma = min(2.0 / (k + 2), gamma_max)
    for _ in range(12):
        candidate = x + gamma * direction
        new_value = float(surrogate.evaluate(candidate, orientation, glazing=glazing))
        if new_value >= value - 1e-12:
            return candidate, new_value, gamma
        gamma *= 0.5
    return None


def _update_weights(
    vertices: list[VecteurF],
    weights: list[float],
    fw_vertex: VecteurF,
    gamma: float,
    *,
    away: bool,
    away_index: int | None,
) -> tuple[list[VecteurF], list[float]]:
    """Move ``gamma`` of mass onto ``fw_vertex`` (or off ``away_index``).

    Also drops the vertices left with near-zero weight, and renormalizes.
    """
    if away and away_index is not None:
        for rank in range(len(weights)):
            weights[rank] *= 1.0 + gamma
        weights[away_index] -= gamma
    else:
        for rank in range(len(weights)):
            weights[rank] *= 1.0 - gamma
        existing = _vertex_index(vertices, fw_vertex)
        if existing is None:
            vertices.append(fw_vertex.copy())
            weights.append(gamma)
        else:
            weights[existing] += gamma

    kept_vertices: list[VecteurF] = []
    kept_weights: list[float] = []
    for vertex, mass in zip(vertices, weights, strict=True):
        if mass > _MIN_WEIGHT:
            kept_vertices.append(vertex)
            kept_weights.append(mass)
    _normalize(kept_weights)
    return kept_vertices, kept_weights


def frank_wolfe(
    poly: Polytope,
    surrogate: Surrogate,
    orientation: Orientation,
    start: VecteurF,
    *,
    max_iter: int = 50,
    tol: float = 1e-4,
    budget: float | None = None,
    away_steps: bool = True,
    strategy: StepStrategy | None = None,
    glazing: Glazing | None = None,
) -> FrankWolfeResult:
    """Maximize ``surrogate`` over the polytope, starting from ``start``.

    Parameters
    ----------
    poly : Polytope
        Admissible domain; every iterate stays in it.
    surrogate : Substitut
        Objective. The solver does not know whether it is analytic, learned or simulated.
    orientation : Orientation
        Azimuth of the plan.
    start : numpy.ndarray
        Initial iterate, typically the result of the classic legalization.
    max_iter : int, optional
        Maximum number of iterations.
    tol : float, optional
        Stop when the Frank-Wolfe gap falls below this threshold.
    budget : float or None, optional
        Maximum displacement allowed, in metres, relative to ``start``. When ``start``
        is not the proposed plan, restrict ``poly`` with :func:`restrict_to_budget`
        around the proposal instead, as :func:`archlux.api.legalize` does.
    away_steps : bool, optional
        Away steps: speed up convergence when the optimum lies on a face. Ignored when
        ``strategy`` is given.
    strategy : StepStrategy or None, optional
        How the direction and its maximum step are computed each iteration. ``None``
        uses the built-in :class:`AwayStepStrategy` (``away_steps`` above). Inject a
        different one to try a new step rule without editing this function.
    glazing : Baies or None, optional
        Windows, constant during optimization; passed to the surrogate as ``baies``.

    Returns
    -------
    FrankWolfeResult
        Final iterate and gap.

    Guarantees
    ----------
    - Geometric: **exact** at every iteration with respect to ``poly``: every iterate is
      a convex combination of ``start`` and vertices of the polytope, hence without
      overlap or gap.
    - Optimization: ``gap`` is a stationarity measure at the returned point; it bounds
      the distance to the optimum of the surrogate only if the surrogate is concave,
      which no shipped surrogate is. ``status`` says why the run stopped.
    - Daylight performance: **none here**. It is produced by :mod:`archlux.uq` and is
      only probabilistic.

    Warnings
    --------
    Minimum areas are guaranteed **only if** ``poly`` already contains an inner
    approximation of them (:func:`archlux.lmo.coupes.inner_area_constraints`), which is
    what :func:`archlux.api.legalize` passes: every point of such a domain keeps every
    minimum area, hence every iterate does.

    Complexity
    ----------
    At most ``max_iter + 1`` LP calls (one per iteration, plus one at the returned point
    for its gap and duals), **all warm** via ``depart=``. Omitting it costs a factor 3
    to 5. Budget: < 500 ms for 15 rooms and 50 iterations.
    """
    domain = poly if budget is None else restrict_to_budget(poly, start, budget)
    x = np.asarray(start, dtype=float).copy()
    if x.shape != (len(domain.index),):
        raise InvariantViolation((f"start of shape {x.shape}, expected ({len(domain.index)},)",))
    step_strategy = strategy if strategy is not None else AwayStepStrategy(enabled=away_steps)

    vertices = [x.copy()]
    weights = [1.0]
    gap = float("inf")  # no LP has succeeded yet: nothing is known
    status: StopStatus = "max_iter"
    value = float(surrogate.evaluate(x, orientation, glazing=glazing))
    history: list[Iteration] = [
        Iteration(
            k=-1,
            value=value,
            gap=float("inf"),
            step=0.0,
            away_step=False,
            lp_ms=0.0,
            n_cuts=0,
            x=x.copy(),
        )
    ]
    last_oracle = None

    for k in range(max_iter):
        gradient = np.asarray(surrogate.gradient(x, orientation, glazing=glazing), dtype=float)
        oracle = solve(
            domain,
            -gradient,
            start=x,
            duals=False,  # duals are computed once, at the returned point
        )
        last_oracle = oracle
        if oracle.status != "optimal":
            status = "lp_not_optimal"
            if k > 0:
                gap = float("inf")  # x moved since the last successful LP: unknown
            break
        fw_vertex = oracle.x
        gap = float(gradient @ (fw_vertex - x))
        if gap <= tol:
            status = "converged"
            history.append(
                Iteration(
                    k=k,
                    value=value,
                    gap=gap,
                    step=0.0,
                    away_step=False,
                    lp_ms=oracle.time_ms,
                    n_cuts=0,
                    x=x.copy(),
                )
            )
            break

        direction, gamma_max, away, away_index = step_strategy.propose(
            gradient, x, fw_vertex, vertices, weights
        )

        stepped = _line_search(
            surrogate, orientation, x, value, direction, gamma_max, k, glazing=glazing
        )
        if stepped is None:
            status = "line_search_failed"
            history.append(
                Iteration(
                    k=k,
                    value=value,
                    gap=gap,
                    step=0.0,
                    away_step=away,
                    lp_ms=oracle.time_ms,
                    n_cuts=0,
                    x=x.copy(),
                )
            )
            break
        x, value, gamma = stepped

        vertices, weights = _update_weights(
            vertices, weights, fw_vertex, gamma, away=away, away_index=away_index
        )

        history.append(
            Iteration(
                k=k,
                value=value,
                gap=gap,
                step=gamma,
                away_step=away,
                lp_ms=oracle.time_ms,
                n_cuts=0,
                x=x.copy(),
            )
        )

    gap, duals = _final_diagnostics(
        surrogate, orientation, domain, x, status, last_oracle, gap, glazing=glazing
    )

    return FrankWolfeResult(
        x=x,
        value=value,
        gap=gap,
        status=status,
        iterations=len(history) - 1,
        trace=Trace(iterations=tuple(history), status=status, final_gap=gap),
        duals=duals,
    )
