"""Frank-Wolfe says what it actually achieved (PLAN.md batch 1.4, AUDIT.md §5.1).

- the gap is infinite, not zero, when no LP succeeded;
- the gap returned is the one at the returned point;
- the stop status is explicit;
- ``iterations`` counts steps, not the initial entry;
- a displacement budget is measured from the **proposed** plan, once, and checked by
  the proof.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np
import pytest
from hypothesis import given, settings

import archlux
from archlux.certify.preuve import verifier_exactement
from archlux.data.corruption import corrompre
from archlux.light.analytique import SubstitutAnalytique
from archlux.lmo import solveur
from archlux.lmo.solveur import resoudre
from archlux.solve import frank_wolfe as fw_module
from archlux.solve.frank_wolfe import frank_wolfe
from archlux.types import Contexte, Orientation, Plan
from tests.proprietes.strategies import realistic_scenarios
from tests.unites.test_frank_wolfe import NORD, POLY, ObjectifLineaire, _depart_faisable


@dataclass(frozen=True, slots=True)
class _Misleading:
    """Gradient points up, value goes down: every line search fails."""

    c: np.ndarray
    indicateur: str = "sDA"

    def evaluer(self, x: np.ndarray, orientation: Orientation, *, baies: object = None) -> float:
        return -float(self.c @ x)

    def gradient(
        self, x: np.ndarray, orientation: Orientation, *, baies: object = None
    ) -> np.ndarray:
        return self.c

    def incertitude(
        self, x: np.ndarray, orientation: Orientation, *, baies: object = None
    ) -> float:
        return 0.1


def _objective() -> ObjectifLineaire:
    return ObjectifLineaire(c=np.array([0.0, 0.0, 1.0, 0.5]))


def test_a_converged_run_says_so() -> None:
    result = frank_wolfe(POLY, _objective(), NORD, _depart_faisable(), max_iter=50)
    assert result.status == "converged"
    assert result.gap <= 1e-4


def test_a_run_cut_short_says_so_and_reports_the_gap_at_the_returned_point() -> None:
    objective = _objective()
    result = frank_wolfe(POLY, objective, NORD, _depart_faisable(), max_iter=1)
    assert result.status == "max_iter"
    vertex = resoudre(POLY, -objective.c).x
    assert result.gap == pytest.approx(float(objective.c @ (vertex - result.x)), abs=1e-9)


def test_a_failed_line_search_is_reported() -> None:
    result = frank_wolfe(
        POLY, _Misleading(np.array([0.0, 0.0, 1.0, 0.5])), NORD, _depart_faisable()
    )
    assert result.status == "line_search_failed"


def test_no_successful_lp_gives_an_infinite_gap(monkeypatch: pytest.MonkeyPatch) -> None:
    """A gap of 0 would read as 'optimum reached' (AUDIT.md §5.1)."""
    real = resoudre(POLY, np.zeros(4))

    def failing(*args: object, **kwargs: object) -> solveur.SolutionLP:
        return replace(real, statut="limite")

    monkeypatch.setattr(fw_module, "resoudre", failing)
    result = frank_wolfe(POLY, _objective(), NORD, _depart_faisable())
    assert result.status == "lp_not_optimal"
    assert result.gap == float("inf")


def test_iterations_count_steps_not_the_initial_entry() -> None:
    result = frank_wolfe(POLY, _objective(), NORD, _depart_faisable(), max_iter=3)
    assert result.iterations == len(result.trace.iterations) - 1


def test_the_trace_carries_the_stop_status() -> None:
    result = frank_wolfe(POLY, _objective(), NORD, _depart_faisable(), max_iter=1)
    assert result.trace.status == result.status


# --- Budget: measured once, from the proposed plan -------------------------------------


def _max_move(result: Plan, proposed: Plan) -> float:
    before = {room.id: room for room in proposed.pieces}
    return max(
        abs(getattr(room, field) - getattr(before[room.id], field))
        for room in result.pieces
        for field in ("x", "y", "w", "h")
    )


@settings(max_examples=40, deadline=None, derandomize=True)
@given(scenario=realistic_scenarios())
def test_performance_mode_never_moves_a_room_beyond_the_budget(
    scenario: tuple[Plan, Contexte],
) -> None:
    """AUDIT.md §5.8: the Frank-Wolfe box was centred on the L1 point, so the total move
    from the proposal could reach twice the budget. The input is corrupted first, so
    that the classic pass does move and consumes part of the budget."""
    plan, ctx = scenario
    proposed, _ = corrompre(plan, seed=len(plan.pieces), amplitude=0.25)
    budget = 0.3
    try:
        result = archlux.legalize(
            proposed, ctx, objective=SubstitutAnalytique(), budget=budget, pavage=True
        )
    except archlux.ArchluxError:
        return  # refusing is allowed; exceeding the budget is not
    assert _max_move(result, proposed) <= budget + 1e-6


def test_the_proof_rejects_a_plan_moved_beyond_the_budget() -> None:
    from tests.unites.test_load_bearing import _ctx, _plan, _room

    proposed = _plan(_room("a", 0, 0, 6, 6), _room("b", 6, 0, 4, 6))
    moved = _plan(_room("a", 0, 0, 7, 6), _room("b", 7, 0, 3, 6))
    ctx = _ctx()
    assert verifier_exactement(moved, ctx, reference=proposed, budget=2.0).valide
    proof = verifier_exactement(moved, ctx, reference=proposed, budget=0.5)
    assert not proof.valide
    assert any("budget" in violation for violation in proof.violations)
