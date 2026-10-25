"""Frank-Wolfe: maximize a surrogate over the polytope, never leaving the valid set.

The algorithm is chosen for a structural reason, not for convenience: its linear oracle
**is** the legalization solver. Each iteration solves exactly the LP of a classic
legalization, with another cost vector. There is therefore a single solver in the whole
project, and every iterate is a valid plan: no projection, no illegal intermediate step.

Dependencies: ``types``, ``geom``, ``lmo``, and the **protocol** ``light.protocol``.
Never a concrete surrogate implementation.

Formulas: ``docs/formulas/frank-wolfe.md``.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Protocol

import numpy as np

from archlux._deprecation import renamed_parameters
from archlux._log import event
from archlux.arrays import FloatVector
from archlux.errors import Infeasible, InvariantViolation
from archlux.geom.polytope import Polytope
from archlux.lmo.solver import solve
from archlux.solve.trace import Iteration, StopStatus, Trace
from archlux.tolerances import FW_FEASIBILITY_M

if TYPE_CHECKING:
    from archlux.light.protocol import Glazing, Surrogate
    from archlux.lmo.solver import LPSolution
    from archlux.types import Indicator, Orientation

__all__ = [
    "AwayStepStrategy",
    "FrankWolfeResult",
    "StepStrategy",
    "budget_saturation",
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
    value : float
        Surrogate value at ``x``, without the displacement penalty.
    penalised : float or None
        Penalised objective at ``x`` when ``penalty > 0``, ``None`` otherwise; read it
        through :attr:`objective`.
    """

    x: FloatVector
    value: float
    gap: float
    status: StopStatus
    iterations: int
    trace: Trace
    duals: FloatVector | None = None
    penalised: float | None = None

    @property
    def objective(self) -> float:
        """The objective Frank-Wolfe maximised at ``x``: ``value`` minus the penalty.

        Returns
        -------
        float
            Equal to :attr:`value` without a penalty.
        """
        return self.value if self.penalised is None else self.penalised

    @property
    def converged(self) -> bool:
        """Whether the run reached its gap tolerance (``status == "converged"``).

        Any other status still returns a point of the domain, but makes no
        stationarity claim: a caller must not report it as an optimised plan.

        Returns
        -------
        bool
            ``True`` only for ``converged``.
        """
        return self.status == "converged"


@renamed_parameters({"centre": "center"})
def restrict_to_budget(
    poly: Polytope, center: FloatVector, radius: float, *, keep: FloatVector | None = None
) -> Polytope:
    """Intersection of the polytope with the box ``‖x − center‖_∞ ≤ radius``.

    ``center`` must be the **proposed** plan, so that the budget is spent once over the
    whole legalization, not once per pass.

    ``keep`` is a point the box must contain even if it exceeds the radius by a solver
    tolerance: the result of a previous pass, which met the same budget only up to the
    LP tolerance (a saturated budget). Without it, that point could fall outside the box
    and make the domain empty for no real reason.

    Parameters
    ----------
    poly
        Polytope to restrict.
    center
        Proposed plan, center of the box.
    radius
        Budget, in metres.
    keep
        Point the box must contain, or ``None``.

    Returns
    -------
    Polytope
        The polytope with its bounds intersected with the box.

    Raises
    ------
    Infeasible
        The box does not intersect the bounds of some variable: the budget is too small
        for this plan. An input problem, not an internal error.
    """
    names = {column: name for name, column in poly.index.items()}
    bounds: list[tuple[float, float]] = []
    for i, (lo, hi) in enumerate(poly.bounds):
        low = max(lo, float(center[i]) - radius)
        high = min(hi, float(center[i]) + radius)
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


def _vertex_index(vertices: list[FloatVector], candidate: FloatVector) -> int | None:
    """Index of an already stored vertex, up to tolerance.

    Parameters
    ----------
    vertices
        Stored vertices.
    candidate
        Vertex to look up.

    Returns
    -------
    int or None
        Index of the matching vertex, or ``None``.
    """
    for rank, vertex in enumerate(vertices):
        if np.allclose(vertex, candidate, atol=1e-9, rtol=0.0):
            return rank
    return None


def _normalize(weights: list[float]) -> None:
    """Scale the weights so that they sum to 1, in place.

    Numerically null masses are filtered **before** the call, by the caller, which alone
    can drop the matching vertex at the same time: pruning weights here would
    desynchronize the two lists.

    Parameters
    ----------
    weights
        Weights, rescaled in place.
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
        gradient: FloatVector,
        x: FloatVector,
        fw_vertex: FloatVector,
        vertices: list[FloatVector],
        weights: list[float],
    ) -> tuple[FloatVector, float, bool, int | None]:
        """Direction, its ``gamma_max``, whether it is an away step, and the away index.

        Parameters
        ----------
        gradient
            Gradient of the surrogate at ``x``.
        x
            Current iterate.
        fw_vertex
            Vertex returned by the linear oracle.
        vertices
            Active vertices.
        weights
            Weight of each active vertex.
        """
        ...


def _step_away(
    gradient: FloatVector,
    x: FloatVector,
    fw_direction: FloatVector,
    vertices: list[FloatVector],
    weights: list[float],
) -> tuple[FloatVector, float, bool, int | None]:
    """Away-step direction (Lacoste-Julien & Jaggi 2015), or the plain one.

    Away is taken when it improves on the plain Frank-Wolfe direction and the worst
    active vertex still has mass to give up.

    Parameters
    ----------
    gradient
        Gradient of the surrogate at ``x``.
    x
        Current iterate.
    fw_direction
        Plain Frank-Wolfe direction.
    vertices
        Active vertices.
    weights
        Weight of each active vertex.

    Returns
    -------
    tuple
        ``(direction, gamma_max, away, away_index)``.
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
        gradient: FloatVector,
        x: FloatVector,
        fw_vertex: FloatVector,
        vertices: list[FloatVector],
        weights: list[float],
    ) -> tuple[FloatVector, float, bool, int | None]:
        """See :class:`StepStrategy`.

        Parameters
        ----------
        gradient
            Gradient of the surrogate at ``x``.
        x
            Current iterate.
        fw_vertex
            Vertex returned by the linear oracle.
        vertices
            Active vertices.
        weights
            Weight of each active vertex.

        Returns
        -------
        tuple
            ``(direction, gamma_max, away, away_index)``.
        """
        fw_direction = fw_vertex - x
        if not self.enabled:
            return fw_direction, 1.0, False, None
        return _step_away(gradient, x, fw_direction, vertices, weights)


def _resolve_strategy(strategy: StepStrategy | None, *, away_steps: bool) -> StepStrategy:
    """The injected strategy, or the built-in one; warns if ``away_steps=False`` is lost.

    Parameters
    ----------
    strategy
        Injected strategy, or ``None``.
    away_steps
        Whether the built-in strategy takes away steps.

    Returns
    -------
    StepStrategy
        The strategy to use.
    """
    if strategy is None:
        return AwayStepStrategy(enabled=away_steps)
    if not away_steps:
        warnings.warn(
            "frank_wolfe: away_steps=False is ignored because strategy= is given; "
            "pass AwayStepStrategy(enabled=False) instead",
            UserWarning,
            stacklevel=3,
        )
    return strategy


def _final_diagnostics(
    surrogate: Surrogate,
    orientation: Orientation,
    domain: Polytope,
    x: FloatVector,
    status: StopStatus,
    last_oracle: LPSolution | None,
    gap: float,
    *,
    glazing: Glazing | None,
) -> tuple[float, FloatVector | None]:
    """The gap and duals at the returned ``x``: one extra, warm LP.

    On ``max_iter`` and ``stalled``, the last step moved ``x`` after its LP, so that LP's
    gap and duals describe the *previous* point: an extra solve is needed here. On any
    other stop, the last LP already describes ``x``, and only its duals (not yet
    requested) are missing.

    Parameters
    ----------
    surrogate
        Objective.
    orientation
        Azimuth of the plan.
    domain
        Polytope of the run.
    x
        Returned iterate.
    status
        Why the run stopped.
    last_oracle
        Last LP solution, or ``None``.
    gap
        Gap of the last LP.
    glazing
        Glazing, or ``None``.

    Returns
    -------
    tuple of float and ndarray or None
        The gap and the duals at ``x``.
    """
    if status in ("max_iter", "stalled") and last_oracle is not None:
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
    x: FloatVector,
    value: float,
    direction: FloatVector,
    gamma_max: float,
    k: int,
    *,
    glazing: Glazing | None,
) -> tuple[FloatVector, float, float] | None:
    """Backtrack from ``2/(k+2)`` (halved while the surrogate would decrease).

    Returns ``(candidate, new_value, gamma)``, or ``None`` if no step in 12 tries
    improved the surrogate (``status = "line_search_failed"`` for the caller).

    Parameters
    ----------
    surrogate
        Objective.
    orientation
        Azimuth of the plan.
    x
        Current iterate.
    value
        Objective at ``x``.
    direction
        Step direction.
    gamma_max
        Largest admissible step.
    k
        Iteration number.
    glazing
        Glazing, or ``None``.

    Returns
    -------
    tuple or None
        ``(candidate, new_value, gamma)``, or ``None`` if no step improved.
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
    vertices: list[FloatVector],
    weights: list[float],
    fw_vertex: FloatVector,
    gamma: float,
    *,
    away: bool,
    away_index: int | None,
) -> tuple[list[FloatVector], list[float]]:
    """Move ``gamma`` of mass onto ``fw_vertex`` (or off ``away_index``).

    Also drops the vertices left with near-zero weight, and renormalizes.

    Parameters
    ----------
    vertices
        Active vertices.
    weights
        Weight of each active vertex.
    fw_vertex
        Vertex returned by the linear oracle.
    gamma
        Step taken.
    away
        Whether the step was an away step.
    away_index
        Index of the away vertex, or ``None``.

    Returns
    -------
    tuple of list
        The kept vertices and their renormalized weights.
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

    kept_vertices: list[FloatVector] = []
    kept_weights: list[float] = []
    for vertex, mass in zip(vertices, weights, strict=True):
        if mass > _MIN_WEIGHT:
            kept_vertices.append(vertex)
            kept_weights.append(mass)
    _normalize(kept_weights)
    return kept_vertices, kept_weights


_LINE_SEARCH = "2/(k+2), halved at most 12 times"
"""The step rule of :func:`_line_search`, recorded verbatim in ``Trace.parameters``."""


@dataclass(frozen=True, slots=True)
class _Objective:
    """The function Frank-Wolfe maximises: the surrogate minus a displacement penalty.

    ``f(x) - penalty / 2 * ||x - reference||_2^2``. It quacks like a surrogate
    (``evaluate``, ``gradient``), so the line search and the final diagnostics run on
    it unchanged. With ``penalty == 0`` it is the surrogate itself.
    """

    surrogate: Surrogate
    reference: FloatVector
    penalty: float

    @property
    def indicator(self) -> Indicator:
        """The indicator of the wrapped surrogate.

        Returns
        -------
        Indicator
            Same as the surrogate's.
        """
        return self.surrogate.indicator

    def uncertainty(
        self, x: FloatVector, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> float:
        """The surrogate's uncertainty: the penalty is exact and adds none.

        Parameters
        ----------
        x
            Decision vector.
        orientation
            Azimuth of the plan.
        glazing
            Glazing, or ``None``.

        Returns
        -------
        float
            The surrogate's predictive standard deviation.
        """
        return float(self.surrogate.uncertainty(x, orientation, glazing=glazing))

    def evaluate(
        self, x: FloatVector, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> float:
        """Penalised value at ``x``.

        Parameters
        ----------
        x
            Decision vector.
        orientation
            Azimuth of the plan.
        glazing
            Glazing, or ``None``.

        Returns
        -------
        float
            The surrogate minus the penalty.
        """
        value = float(self.surrogate.evaluate(x, orientation, glazing=glazing))
        return value - self.cost(x)

    def gradient(
        self, x: FloatVector, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> FloatVector:
        """Gradient of the penalised value at ``x``.

        Parameters
        ----------
        x
            Decision vector.
        orientation
            Azimuth of the plan.
        glazing
            Glazing, or ``None``.

        Returns
        -------
        numpy.ndarray
            The surrogate gradient minus ``penalty * (x - reference)``.
        """
        gradient = np.asarray(self.surrogate.gradient(x, orientation, glazing=glazing), dtype=float)
        if self.penalty == 0.0:
            return gradient
        return gradient - self.penalty * (x - self.reference)

    def cost(self, x: FloatVector) -> float:
        """The penalty paid at ``x``.

        Parameters
        ----------
        x
            Decision vector.

        Returns
        -------
        float
            ``penalty / 2 * ||x - reference||^2``, 0 without a penalty.
        """
        if self.penalty == 0.0:
            return 0.0
        return 0.5 * self.penalty * float(np.sum((x - self.reference) ** 2))


def _check_parameters(
    max_iter: int, tol: float, penalty: float, stall_window: int | None, budget: float | None
) -> None:
    """Refuse settings that cannot describe a run.

    Parameters
    ----------
    max_iter
        Iteration budget, ``>= 0``.
    tol
        Gap tolerance, ``>= 0``.
    penalty
        Displacement penalty, ``>= 0``.
    stall_window
        Stagnation window, ``None`` or ``>= 1``.
    budget
        Displacement budget, ``None`` or ``>= 0``.

    Raises
    ------
    InvariantViolation
        A setting out of its range.
    """
    problems = [
        f"{name} = {value!r} must be >= {low}"
        for name, value, low in (
            ("max_iter", max_iter, 0),
            ("tol", tol, 0),
            ("penalty", penalty, 0),
            ("stall_window", stall_window, 1),
            ("budget", budget, 0),
        )
        if value is not None and not value >= low
    ]
    if problems:
        raise InvariantViolation(tuple(problems))


def _worst_violation(domain: Polytope, x: FloatVector) -> tuple[float, str]:
    """The largest violation of the domain at ``x``, and the constraint that carries it.

    Parameters
    ----------
    domain
        Polytope.
    x
        Point to check.

    Returns
    -------
    tuple of float and str
        The violation in the unit of the row (metres here), and its label.
    """
    names = {column: name for name, column in domain.index.items()}
    worst = (0.0, "")
    if domain.A.shape[0]:
        excess = domain.A @ x - domain.b
        row = int(np.argmax(excess))
        worst = max(worst, (float(excess[row]), domain.origins[row]))
    if domain.A_eq.shape[0]:
        residual = np.abs(domain.A_eq @ x - domain.b_eq)
        row = int(np.argmax(residual))
        worst = max(worst, (float(residual[row]), domain.eq_labels()[row]))
    for column, (low, high) in enumerate(domain.bounds):
        label = names.get(column, f"column {column}")
        worst = max(worst, (low - float(x[column]), f"{label} lower bound"))
        worst = max(worst, (float(x[column]) - high, f"{label} upper bound"))
    return worst


def _check_start(domain: Polytope, x: FloatVector) -> None:
    """Refuse a start outside the domain: every guarantee of the run would be void.

    Parameters
    ----------
    domain
        Polytope of the run.
    x
        Start point.

    Raises
    ------
    InvariantViolation
        ``x`` violates a constraint by more than ``tolerances.FW_FEASIBILITY_M``.
    """
    if domain.contains(x, tol=FW_FEASIBILITY_M):
        return
    excess, label = _worst_violation(domain, x)
    raise InvariantViolation((f"Frank-Wolfe start outside its domain: {label} by {excess:.3g}",))


def _oracle_consistent(
    domain: Polytope, vertex: FloatVector, gradient: FloatVector, x: FloatVector
) -> bool:
    """Whether an "optimal" oracle vertex is in the domain and at least as good as ``x``.

    ``x`` is a point of the domain, so the true minimiser of ``<-gradient, s>`` has a
    gap ``<gradient, s - x> >= 0``. A gap below ``-FW_FEASIBILITY_M * ||gradient||_1``
    cannot come from LP noise: the oracle was not minimised.

    Parameters
    ----------
    domain
        Polytope of the run.
    vertex
        Vertex returned by the oracle.
    gradient
        Gradient the oracle was given (negated).
    x
        Current iterate.

    Returns
    -------
    bool
        ``True`` if the vertex can be used.
    """
    if not domain.contains(vertex, tol=FW_FEASIBILITY_M):
        return False
    slack = FW_FEASIBILITY_M * max(float(np.abs(gradient).sum()), 1.0)
    return float(gradient @ (vertex - x)) >= -slack


def _active_bounds(domain: Polytope, x: FloatVector) -> tuple[str, ...]:
    """Constraints tight at ``x``: bounds as ``<column>:lower|upper``, rows as ``row:``.

    Parameters
    ----------
    domain
        Polytope of the run.
    x
        Returned point.

    Returns
    -------
    tuple of str
        Labels, bounds by column order then rows by row order.
    """
    names = {column: name for name, column in domain.index.items()}
    active: list[str] = []
    for column, (low, high) in enumerate(domain.bounds):
        label = names.get(column, f"column {column}")
        if float(x[column]) <= low + FW_FEASIBILITY_M:
            active.append(f"{label}:lower")
        if float(x[column]) >= high - FW_FEASIBILITY_M:
            active.append(f"{label}:upper")
    if domain.A.shape[0]:
        slack = domain.b - domain.A @ x
        tight = np.flatnonzero(slack <= FW_FEASIBILITY_M)
        active.extend(f"row:{domain.origins[row]}" for row in tight)
    return tuple(active)


def budget_saturation(
    x: FloatVector, center: FloatVector, radius: float, index: dict[str, int]
) -> tuple[str, ...]:
    """Columns of ``x`` that sit on the budget box ``||x - center||_inf <= radius``.

    A column listed here was stopped by the budget, not by the geometry: the surrogate
    would have moved it further. See ``docs/formulas/frank-wolfe.md``, "Why the budget
    saturates".

    Parameters
    ----------
    x
        Point to inspect.
    center
        Centre of the box (the proposed plan).
    radius
        Budget, in metres.
    index
        Column index of the polytope.

    Returns
    -------
    tuple of str
        Column names, in column order.
    """
    names = sorted(index, key=index.__getitem__)
    moved = np.abs(np.asarray(x, dtype=float) - np.asarray(center, dtype=float))
    return tuple(names[i] for i in np.flatnonzero(moved >= radius - FW_FEASIBILITY_M))


def _parameters(
    *,
    max_iter: int,
    tol: float,
    budget: float | None,
    away_steps: bool,
    strategy: StepStrategy,
    penalty: float,
    stall_window: int | None,
    stall_tol: float,
    reference_given: bool,
) -> tuple[tuple[str, str], ...]:
    """Every setting of the run, as sorted ``(name, text)`` pairs.

    Parameters
    ----------
    max_iter, tol, budget, away_steps, strategy, penalty, stall_window, stall_tol
        As :func:`frank_wolfe`.
    reference_given
        Whether a ``reference`` was passed (otherwise the start is the reference).

    Returns
    -------
    tuple of (str, str)
        Sorted by name.
    """
    settings = {
        "max_iter": str(max_iter),
        "tol": f"{tol:g}",
        "budget": "None" if budget is None else f"{budget:g}",
        "away_steps": str(away_steps),
        "strategy": repr(strategy),
        "penalty": f"{penalty:g}",
        "stall_window": str(stall_window),
        "stall_tol": f"{stall_tol:g}",
        "reference": "given" if reference_given else "start",
        "line_search": _LINE_SEARCH,
        "feasibility_tol": f"{FW_FEASIBILITY_M:g}",
    }
    return tuple(sorted(settings.items()))


@dataclass(slots=True)
class _Run:
    """Mutable state of one Frank-Wolfe run; :func:`frank_wolfe` owns it, nobody else."""

    domain: Polytope
    objective: _Objective
    orientation: Orientation
    glazing: Glazing | None
    x: FloatVector
    value: float
    penalised: float
    vertices: list[FloatVector]
    weights: list[float]
    history: list[Iteration]
    gains: list[float]
    gap: float = float("inf")
    last_oracle: LPSolution | None = None

    def record(self, k: int, *, step: float, away: bool, lp_ms: float) -> None:
        """Append the current state to the history.

        Parameters
        ----------
        k
            Iteration number (``-1`` for the start).
        step
            Step taken.
        away
            Whether it was an away step.
        lp_ms
            Time of the oracle.
        """
        moved = np.abs(self.x - self.objective.reference)
        self.history.append(
            Iteration(
                k=k,
                value=self.value,
                gap=self.gap if k >= 0 else float("inf"),
                step=step,
                away_step=away,
                lp_ms=lp_ms,
                n_cuts=0,
                x=self.x.copy(),
                displacement=float(np.max(moved, initial=0.0)),
                objective=None if self.objective.penalty == 0.0 else self.penalised,
            )
        )

    def move(self, candidate: FloatVector, penalised: float) -> None:
        """Accept ``candidate`` as the new iterate.

        Parameters
        ----------
        candidate
            New iterate.
        penalised
            Objective at ``candidate``.

        Raises
        ------
        InvariantViolation
            ``candidate`` left the domain: a step strategy returned a direction or a
            ``gamma_max`` that is not admissible. A bug, never a result.
        """
        if not self.domain.contains(candidate, tol=FW_FEASIBILITY_M):
            excess, label = _worst_violation(self.domain, candidate)
            raise InvariantViolation(
                (f"Frank-Wolfe iterate left its domain: {label} by {excess:.3g}",)
            )
        self.gains.append(penalised - self.penalised)
        self.x = candidate
        self.penalised = penalised
        surrogate = self.objective.surrogate
        self.value = float(surrogate.evaluate(candidate, self.orientation, glazing=self.glazing))


def _stalled(gains: list[float], window: int | None, stall_tol: float) -> bool:
    """Whether the last ``window`` steps each gained less than ``stall_tol``.

    Parameters
    ----------
    gains
        Objective gain of every step so far.
    window
        Number of steps, or ``None`` (never stalled).
    stall_tol
        Gain under which a step counts as stagnant.

    Returns
    -------
    bool
        ``True`` if the run stagnates.
    """
    if window is None or len(gains) < window:
        return False
    return all(gain < stall_tol for gain in gains[-window:])


def _iterate(run: _Run, k: int, tol: float, strategy: StepStrategy) -> StopStatus | None:
    """One Frank-Wolfe iteration; the stop status, or ``None`` to continue.

    Parameters
    ----------
    run
        State of the run, updated in place.
    k
        Iteration number.
    tol
        Gap tolerance.
    strategy
        Step strategy.

    Returns
    -------
    StopStatus or None
        Why the run stops now, or ``None``.
    """
    gradient = run.objective.gradient(run.x, run.orientation, glazing=run.glazing)
    # duals are computed once, at the returned point
    oracle = solve(run.domain, -gradient, start=run.x, duals=False)
    run.last_oracle = oracle
    if oracle.status != "optimal":
        if k > 0:
            run.gap = float("inf")  # x moved since the last successful LP: unknown
        return "lp_not_optimal"
    if not _oracle_consistent(run.domain, oracle.x, gradient, run.x):
        run.gap = float("inf")  # the only gap at hand comes from an unusable vertex
        event("archlux.solve", "frank_wolfe.oracle_inconsistent", k=k)
        return "oracle_inconsistent"
    fw_vertex = oracle.x
    run.gap = float(gradient @ (fw_vertex - run.x))
    if run.gap <= tol:
        run.record(k, step=0.0, away=False, lp_ms=oracle.time_ms)
        return "converged"
    direction, gamma_max, away, away_index = strategy.propose(
        gradient, run.x, fw_vertex, run.vertices, run.weights
    )
    stepped = _line_search(
        run.objective,
        run.orientation,
        run.x,
        run.penalised,
        direction,
        gamma_max,
        k,
        glazing=run.glazing,
    )
    if stepped is None:
        run.record(k, step=0.0, away=away, lp_ms=oracle.time_ms)
        return "line_search_failed"
    candidate, penalised, gamma = stepped
    run.move(candidate, penalised)
    run.vertices, run.weights = _update_weights(
        run.vertices, run.weights, fw_vertex, gamma, away=away, away_index=away_index
    )
    run.record(k, step=gamma, away=away, lp_ms=oracle.time_ms)
    event(
        "archlux.solve",
        "frank_wolfe.iteration",
        k=k,
        value=run.value,
        gap=run.gap,
        step=gamma,
        away_step=away,
        lp_ms=oracle.time_ms,
    )
    return None


def frank_wolfe(
    poly: Polytope,
    surrogate: Surrogate,
    orientation: Orientation,
    start: FloatVector,
    *,
    max_iter: int = 50,
    tol: float = 1e-4,
    budget: float | None = None,
    away_steps: bool = True,
    strategy: StepStrategy | None = None,
    glazing: Glazing | None = None,
    reference: FloatVector | None = None,
    penalty: float = 0.0,
    stall_window: int | None = None,
    stall_tol: float = 1e-9,
) -> FrankWolfeResult:
    """Maximize ``surrogate`` over the polytope, starting from ``start``.

    Parameters
    ----------
    poly : Polytope
        Admissible domain; every iterate stays in it.
    surrogate : Surrogate
        Objective. The solver does not know whether it is analytic, learned or simulated.
    orientation : Orientation
        Azimuth of the plan.
    start : numpy.ndarray
        Initial iterate, typically the result of the classic legalization. It must lie
        in ``poly`` (and in the budget box) up to ``tolerances.FW_FEASIBILITY_M``.
    max_iter : int, optional
        Maximum number of iterations (one LP each).
    tol : float, optional
        Stop when the Frank-Wolfe gap falls below this threshold.
    budget : float or None, optional
        Maximum L-infinity displacement allowed, in metres, relative to ``reference``
        (``start`` by default). Pass the proposed plan as ``reference`` so that the
        budget is spent once over the whole legalization; restricting ``poly`` with
        :func:`restrict_to_budget` beforehand is equivalent but loses the
        ``Trace.budget_active`` diagnosis.
    away_steps : bool, optional
        Away steps: speed up convergence when the optimum lies on a face. Ignored when
        ``strategy`` is given; passing ``False`` together with ``strategy`` emits a
        ``UserWarning``.
    strategy : StepStrategy or None, optional
        How the direction and its maximum step are computed each iteration. ``None``
        uses the built-in :class:`AwayStepStrategy` (``away_steps`` above). Inject a
        different one to try a new step rule without editing this function.
    glazing : Glazing or None, optional
        Windows, constant during optimization; passed to the surrogate as ``baies``.
    reference : numpy.ndarray or None, optional
        The proposed plan: centre of the budget box, of the displacement penalty and of
        the recorded displacements. ``None`` uses ``start``.
    penalty : float, optional
        Weight ``lambda`` of an explicit displacement penalty: Frank-Wolfe maximises
        ``f(x) - lambda / 2 * ||x - reference||_2^2`` (indicator units per m²). ``0``,
        the default, optimises the surrogate alone, whose maximiser then lies on the
        boundary and usually on the budget box. ``value`` always reports the surrogate,
        ``objective`` the penalised value.
    stall_window : int or None, optional
        Stop with ``status = "stalled"`` once this many consecutive steps each gained
        less than ``stall_tol`` on the objective. ``None`` (default) disables it: the
        run then stops on the gap, a failed line search or ``max_iter``.
    stall_tol : float, optional
        Gain under which a step counts as stagnant.

    Returns
    -------
    FrankWolfeResult
        Final iterate, gap, status and trace (with the parameters of the run).

    Raises
    ------
    InvariantViolation
        A setting out of range, a start outside the domain, or an iterate that left it
        (a faulty injected ``strategy``). An oracle vertex outside the domain is *not*
        raised: the run stops with ``status = "oracle_inconsistent"`` on its last valid
        point.
    Infeasible
        The budget box does not meet the bounds of ``poly``.

    Guarantees
    ----------
    - Geometric: **exact** at every iteration with respect to ``poly``: every iterate is
      a convex combination of ``start`` and vertices of the polytope, each checked
      against ``poly`` before use, hence without overlap or gap.
    - Optimization: ``gap`` is a stationarity measure at the returned point; it bounds
      the distance to the optimum of the surrogate only if the surrogate is concave,
      which no shipped surrogate is. No status, ``converged`` included, means "global
      optimum". ``status`` says why the run stopped.
    - Daylight performance: **none here**. It is produced by :mod:`archlux.uq` and is
      only probabilistic.

    Warnings
    --------
    Minimum areas are guaranteed **only if** ``poly`` already contains an inner
    approximation of them (:func:`archlux.lmo.coupes.inner_area_constraints`), which is
    what :func:`archlux.api.legalize` passes: every point of such a domain keeps every
    minimum area, hence every iterate does. The original constraint ``w h >= a`` is
    checked again by :func:`archlux.certify.proof.verify_exactly` on the decoded plan.

    Complexity
    ----------
    At most ``max_iter + 1`` LP calls (one per iteration, plus one at the returned point
    for its gap and duals), **all warm** via ``depart=``. Omitting it costs a factor 3
    to 5. Budget: < 500 ms for 15 rooms and 50 iterations.
    """
    _check_parameters(max_iter, tol, penalty, stall_window, budget)
    x = np.asarray(start, dtype=float).copy()
    if x.shape != (len(poly.index),):
        raise InvariantViolation((f"start of shape {x.shape}, expected ({len(poly.index)},)",))
    center = x.copy() if reference is None else np.asarray(reference, dtype=float).copy()
    domain = poly if budget is None else restrict_to_budget(poly, center, budget, keep=x)
    _check_start(domain, x)
    step_strategy = _resolve_strategy(strategy, away_steps=away_steps)
    objective = _Objective(surrogate=surrogate, reference=center, penalty=float(penalty))
    parameters = _parameters(
        max_iter=max_iter,
        tol=tol,
        budget=budget,
        away_steps=away_steps,
        strategy=step_strategy,
        penalty=float(penalty),
        stall_window=stall_window,
        stall_tol=stall_tol,
        reference_given=reference is not None,
    )

    value = float(surrogate.evaluate(x, orientation, glazing=glazing))
    run = _Run(
        domain=domain,
        objective=objective,
        orientation=orientation,
        glazing=glazing,
        x=x,
        value=value,
        penalised=value - objective.cost(x),
        vertices=[x.copy()],
        weights=[1.0],
        history=[],
        gains=[],
    )
    run.record(-1, step=0.0, away=False, lp_ms=0.0)
    status: StopStatus = "max_iter"
    for k in range(max_iter):
        stop = _iterate(run, k, tol, step_strategy)
        if stop is None and _stalled(run.gains, stall_window, stall_tol):
            stop = "stalled"
        if stop is not None:
            status = stop
            break
    if status != "oracle_inconsistent" and _gradient_refused(surrogate):
        status = "untrusted_gradient"
    return _result(run, status, budget=budget, parameters=parameters)


def _gradient_refused(surrogate: Surrogate) -> bool:
    """Whether the objective refused its last gradient (optional ``refused`` member).

    ``solve`` may not import :mod:`archlux.light.trust`; a guarded objective says so
    through this attribute instead, which ordinary surrogates do not have.

    Parameters
    ----------
    surrogate
        Objective of the run.

    Returns
    -------
    bool
        ``True`` iff ``surrogate.refused`` exists and is true.
    """
    return bool(getattr(surrogate, "refused", False))


def _result(
    run: _Run,
    status: StopStatus,
    *,
    budget: float | None,
    parameters: tuple[tuple[str, str], ...],
) -> FrankWolfeResult:
    """Final diagnostics, trace and result of a finished run.

    Parameters
    ----------
    run
        The finished run.
    status
        Why it stopped.
    budget
        Displacement budget of the run, or ``None``.
    parameters
        Settings of the run, for the trace.

    Returns
    -------
    FrankWolfeResult
        The result, with its trace.
    """
    gap, duals = float("inf"), None
    if status != "oracle_inconsistent":
        gap, duals = _final_diagnostics(
            run.objective,
            run.orientation,
            run.domain,
            run.x,
            status,
            run.last_oracle,
            run.gap,
            glazing=run.glazing,
        )
    event(
        "archlux.solve",
        "frank_wolfe.stop",
        status=status,
        iterations=len(run.history) - 1,
        value=run.value,
        gap=gap,
    )
    center = run.objective.reference
    trace = Trace(
        iterations=tuple(run.history),
        status=status,
        final_gap=gap,
        parameters=parameters,
        active_bounds=_active_bounds(run.domain, run.x),
        budget_active=()
        if budget is None
        else budget_saturation(run.x, center, budget, run.domain.index),
    )
    return FrankWolfeResult(
        x=run.x,
        value=run.value,
        gap=gap,
        status=status,
        iterations=len(run.history) - 1,
        trace=trace,
        duals=duals,
        penalised=None if run.objective.penalty == 0.0 else run.penalised,
    )
