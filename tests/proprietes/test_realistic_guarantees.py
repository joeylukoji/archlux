"""Exact guarantees under a context that actually constrains the plan (PLAN.md 0.8).

The output of ``legalize`` is checked by an **independent** checker written here, never
by ``certify``: re-checking the proof with itself is precisely the blind spot that let a
tautological load-bearing check through (AUDIT.md §3 n°1).
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings

import archlux
from archlux.light.analytique import SubstitutAnalytique
from archlux.light.objectif import Daylight
from archlux.types import Contexte, Plan
from tests.proprietes.strategies import realistic_scenarios

_TOL = 1e-6
_SETTINGS = settings(max_examples=60, deadline=None, derandomize=True)


def _independent_violations(result: Plan, ctx: Contexte) -> list[str]:
    """Minimum areas and load-bearing walls, checked from coordinates only."""
    violations: list[str] = []
    for room in result.pieces:
        minimum = ctx.referentiel.a_min(room.type)
        if room.w * room.h < minimum - _TOL:
            violations.append(f"{room.id}: area {room.w * room.h:.3f} < {minimum:.3f}")
    for wall in ctx.structure.murs_porteurs:
        (xa, ya), (xb, yb) = wall.a, wall.b
        for room in result.pieces:
            x0, x1, y0, y1 = room.x, room.x + room.w, room.y, room.y + room.h
            if abs(xa - xb) < _TOL:  # vertical wall at x = xa
                crosses = x0 + _TOL < xa < x1 - _TOL
                overlap = min(y1, max(ya, yb)) - max(y0, min(ya, yb))
            else:  # horizontal wall at y = ya
                crosses = y0 + _TOL < ya < y1 - _TOL
                overlap = min(x1, max(xa, xb)) - max(x0, min(xa, xb))
            if crosses and overlap > _TOL:
                violations.append(f"{room.id} crosses load-bearing wall {wall.id}")
    return violations


@_SETTINGS
@given(scenario=realistic_scenarios())
def test_the_input_is_valid_under_its_own_context(scenario: tuple[Plan, Contexte]) -> None:
    """Sanity check of the strategy itself: any later violation comes from legalize."""
    plan, ctx = scenario
    assert _independent_violations(plan, ctx) == []


@_SETTINGS
@given(scenario=realistic_scenarios())
def test_classic_legalization_keeps_areas_and_walls(scenario: tuple[Plan, Contexte]) -> None:
    plan, ctx = scenario
    result = archlux.legalize(plan, ctx)
    assert _independent_violations(result, ctx) == []


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Frank-Wolfe goes below minimum areas (InvariantViole) and crosses load-bearing "
        "walls unnoticed — AUDIT.md §3 n°1 and n°6; fixed in PLAN.md 1.1 and 1.2"
    ),
)
@_SETTINGS
@given(scenario=realistic_scenarios())
def test_performance_legalization_keeps_areas_and_walls(scenario: tuple[Plan, Contexte]) -> None:
    plan, ctx = scenario
    result = archlux.legalize(plan, ctx, objective=SubstitutAnalytique())
    assert _independent_violations(result, ctx) == []


@pytest.mark.xfail(
    strict=True,
    reason="Daylight lacks the 'baies' keyword of Substitut — AUDIT.md §3 n°3, PLAN.md 1.3",
)
@_SETTINGS
@given(scenario=realistic_scenarios())
def test_daylight_objective_is_accepted_by_legalize(scenario: tuple[Plan, Contexte]) -> None:
    plan, ctx = scenario
    objective = Daylight(SubstitutAnalytique(), q_chapeau=1.0)
    result = archlux.legalize(plan, ctx, objective=objective)
    assert _independent_violations(result, ctx) == []
