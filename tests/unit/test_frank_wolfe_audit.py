"""Frank-Wolfe audit (article revision, spec 1.2): what the solver checks and records.

- the start point must belong to the domain;
- every oracle vertex is checked against the domain and against optimality before use;
- a stagnating run can stop with its own status;
- the trace records the parameters of the run and which bounds are active at the end;
- an optional displacement penalty and a budget centred on the proposed plan.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from itertools import pairwise

import numpy as np
import pytest

from archlux.errors import InvariantViolation
from archlux.lmo import solver
from archlux.lmo.solver import solve
from archlux.solve import frank_wolfe as fw_module
from archlux.solve.frank_wolfe import frank_wolfe
from archlux.types import Orientation
from tests.unit.test_frank_wolfe import NORTH, POLY, LinearObjective, _feasible_start


@dataclass(frozen=True, slots=True)
class _Flat:
    """Gradient towards an interior point, flat value: every step is accepted, none gains.

    The oracle vertex keeps changing with ``x``, so the gap stays positive.
    """

    target: np.ndarray
    indicator: str = "sDA"

    def evaluate(self, x: np.ndarray, orientation: Orientation, *, glazing: object = None) -> float:
        return 0.0

    def gradient(
        self, x: np.ndarray, orientation: Orientation, *, glazing: object = None
    ) -> np.ndarray:
        return self.target - x

    def uncertainty(
        self, x: np.ndarray, orientation: Orientation, *, glazing: object = None
    ) -> float:
        return 0.1


_INTERIOR = np.array([3.0, 2.0, 3.0, 3.0])


def _objective() -> LinearObjective:
    return LinearObjective(c=np.array([0.0, 0.0, 1.0, 0.5]))


# --- Point 1: feasible start -----------------------------------------------------------


def test_a_start_outside_the_domain_is_refused_and_named() -> None:
    start = _feasible_start()
    start[POLY.index["A.w"]] = 0.5  # below the 1.5 m minimum width
    with pytest.raises(InvariantViolation) as error:
        frank_wolfe(POLY, _objective(), NORTH, start)
    assert "start" in str(error.value)


def test_a_start_within_the_lp_tolerance_is_accepted() -> None:
    start = _feasible_start()
    start[POLY.index["A.x"]] = -1e-8  # LP noise on a saturated bound
    result = frank_wolfe(POLY, _objective(), NORTH, start)
    assert result.status == "converged"


# --- Point 2: the oracle is checked, not trusted ---------------------------------------


def test_an_infeasible_oracle_vertex_is_reported_and_not_used(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def outside(*args: object, **kwargs: object) -> solver.LPSolution:
        solution = solve(*args, **kwargs)  # type: ignore[arg-type]
        return replace(solution, x=solution.x + 5.0)  # out of the outline

    monkeypatch.setattr(fw_module, "solve", outside)
    start = _feasible_start()
    result = frank_wolfe(POLY, _objective(), NORTH, start)
    assert result.status == "oracle_inconsistent"
    assert not result.converged
    assert POLY.contains(result.x)
    np.testing.assert_allclose(result.x, start)
    assert result.gap == float("inf")


def test_a_non_optimal_oracle_vertex_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    """A vertex worse than x itself means the LP was not minimised: a negative gap."""
    start = _feasible_start()
    worse = solve(POLY, _objective().c).x  # the *minimiser* of the surrogate

    def wrong_direction(*args: object, **kwargs: object) -> solver.LPSolution:
        solution = solve(*args, **kwargs)  # type: ignore[arg-type]
        return replace(solution, x=worse.copy())

    monkeypatch.setattr(fw_module, "solve", wrong_direction)
    result = frank_wolfe(POLY, _objective(), NORTH, start)
    assert result.status == "oracle_inconsistent"
    np.testing.assert_allclose(result.x, start)


# --- Point 4: stopping rules -------------------------------------------------------------


def test_a_stagnating_run_stops_as_stalled_when_asked() -> None:
    result = frank_wolfe(POLY, _Flat(_INTERIOR), NORTH, _feasible_start(), stall_window=3)
    assert result.status == "stalled"
    assert result.iterations == 3
    assert not result.converged


def test_a_stalled_run_reports_the_gap_at_the_returned_point() -> None:
    """The last step moved x after its LP: the gap must be recomputed, as on max_iter."""
    objective = _Flat(_INTERIOR)
    result = frank_wolfe(POLY, objective, NORTH, _feasible_start(), stall_window=3)
    gradient = objective.gradient(result.x, NORTH)
    vertex = solve(POLY, -gradient).x
    assert result.gap == pytest.approx(float(gradient @ (vertex - result.x)), abs=1e-9)


def test_stagnation_detection_is_off_by_default() -> None:
    result = frank_wolfe(POLY, _Flat(_INTERIOR), NORTH, _feasible_start(), max_iter=7)
    assert result.status == "max_iter"


def test_invalid_run_parameters_are_refused() -> None:
    for kwargs in ({"max_iter": -1}, {"tol": -1.0}, {"stall_window": 0}, {"penalty": -1.0}):
        with pytest.raises(InvariantViolation):
            frank_wolfe(POLY, _objective(), NORTH, _feasible_start(), **kwargs)  # type: ignore[arg-type]


def test_only_a_converged_run_reads_as_converged() -> None:
    assert frank_wolfe(POLY, _objective(), NORTH, _feasible_start()).converged
    assert not frank_wolfe(POLY, _objective(), NORTH, _feasible_start(), max_iter=1).converged


# --- Point 8: reproducibility -------------------------------------------------------------


def test_the_trace_records_the_parameters_of_the_run() -> None:
    result = frank_wolfe(POLY, _objective(), NORTH, _feasible_start(), max_iter=7, budget=2.0)
    parameters = dict(result.trace.parameters)
    assert parameters["max_iter"] == "7"
    assert parameters["tol"] == "0.0001"
    assert parameters["budget"] == "2"
    assert parameters["away_steps"] == "True"
    assert parameters["strategy"] == "AwayStepStrategy(enabled=True)"
    assert parameters["line_search"] == "2/(k+2), halved at most 12 times"
    assert parameters["penalty"] == "0"
    assert parameters["stall_window"] == "None"
    assert [key for key, _ in result.trace.parameters] == sorted(parameters)


def test_two_identical_runs_give_identical_traces() -> None:
    first = frank_wolfe(POLY, _objective(), NORTH, _feasible_start(), max_iter=5)
    second = frank_wolfe(POLY, _objective(), NORTH, _feasible_start(), max_iter=5)
    assert first.trace.values == second.trace.values
    assert first.trace.gaps == second.trace.gaps
    assert first.trace.parameters == second.trace.parameters
    for a, b in zip(first.trace.iterates, second.trace.iterates, strict=True):
        np.testing.assert_array_equal(a, b)


# --- Displacement budget and which bound stops the run (spec 1.6) ---------------------------


def test_the_budget_box_is_centred_on_the_reference_and_its_saturation_is_named() -> None:
    reference = _feasible_start()
    result = frank_wolfe(
        POLY, _objective(), NORTH, reference.copy(), budget=0.5, reference=reference
    )
    assert float(np.max(np.abs(result.x - reference))) <= 0.5 + 1e-9
    assert "A.w" in result.trace.budget_active
    assert "A.h" in result.trace.budget_active
    assert result.trace.displacements[-1] == pytest.approx(0.5)


def test_without_a_budget_nothing_is_reported_as_budget_bound() -> None:
    result = frank_wolfe(POLY, _objective(), NORTH, _feasible_start())
    assert result.trace.budget_active == ()


def test_the_trace_names_the_bounds_active_at_the_returned_point() -> None:
    result = frank_wolfe(POLY, _objective(), NORTH, _feasible_start())
    # The linear optimum grows the room to the outline: w and h at their upper bounds.
    assert "A.w:upper" in result.trace.active_bounds
    assert "A.h:upper" in result.trace.active_bounds


def test_the_trace_records_the_displacement_of_every_iterate() -> None:
    start = _feasible_start()
    result = frank_wolfe(POLY, _objective(), NORTH, start, max_iter=5)
    assert result.trace.displacements[0] == 0.0
    for point, moved in zip(result.trace.iterates, result.trace.displacements, strict=True):
        assert moved == pytest.approx(float(np.max(np.abs(point - start))))


# --- Displacement penalty (spec 1.6) ------------------------------------------------------


def test_a_penalty_keeps_the_plan_closer_to_the_reference() -> None:
    start = _feasible_start()
    free = frank_wolfe(POLY, _objective(), NORTH, start, max_iter=200)
    penalised = frank_wolfe(POLY, _objective(), NORTH, start, max_iter=200, penalty=1.0)
    move_free = float(np.max(np.abs(free.x - start)))
    move_penalised = float(np.max(np.abs(penalised.x - start)))
    assert move_penalised < move_free - 0.5
    assert penalised.value < free.value  # the surrogate pays for the smaller move


def test_with_a_penalty_value_is_the_surrogate_and_objective_the_penalised_one() -> None:
    start = _feasible_start()
    objective = _objective()
    result = frank_wolfe(POLY, objective, NORTH, start, max_iter=30, penalty=0.4)
    surrogate_value = objective.evaluate(result.x, NORTH)
    assert result.value == pytest.approx(surrogate_value)
    expected = surrogate_value - 0.2 * float(np.sum((result.x - start) ** 2))
    assert result.objective == pytest.approx(expected)


def test_the_penalised_objective_never_decreases() -> None:
    result = frank_wolfe(POLY, _objective(), NORTH, _feasible_start(), max_iter=30, penalty=0.4)
    objectives = result.trace.objectives
    assert all(after >= before - 1e-9 for before, after in pairwise(objectives))


def test_without_a_penalty_objective_and_value_coincide() -> None:
    result = frank_wolfe(POLY, _objective(), NORTH, _feasible_start())
    assert result.objective == result.value
    assert result.trace.objectives == result.trace.values
