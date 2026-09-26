"""Milestone 3 criteria replayed as written, then with walls and minimum areas (phase 2, J3).

``MILESTONE-3.md`` §0 draws ``plans_quelconques()`` for the first two criteria; the
tests that closed the milestone (``test_acceptation_jalon3.py``) drew already-valid
plans under a context without minimum areas, the case where Frank-Wolfe used to leave
them (AUDIT.md §3 n°6). Each criterion is replayed here on arbitrary plans and contexts,
and on plans with a load-bearing wall and minimum areas (``realistic_scenarios``).
"""

from __future__ import annotations

from dataclasses import replace
from itertools import pairwise

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import archlux
from archlux.errors import ArchluxError
from archlux.geom.graphe import deduce_order
from archlux.geom.polytope import build_polytope, devectorize, vectorize
from archlux.light.analytique import SubstitutAnalytique
from archlux.solve.trace import Trace
from archlux.types import Context, Orientation, Plan
from tests import checkers
from tests.proprietes.strategies import (
    GATE_EXAMPLES,
    contextes,
    plans_quelconques,
    realistic_scenarios,
)

ANALYTIC = SubstitutAnalytique()
_SETTINGS = settings(max_examples=GATE_EXAMPLES, deadline=None, derandomize=True)


def _trace(plan: Plan, ctx: Context) -> tuple[Plan, Trace] | None:
    try:
        result = archlux.legalize(plan, ctx, objective=ANALYTIC, trace=True)
    except ArchluxError:
        return None  # a typed refusal has no iterates
    assert isinstance(result.trace, Trace)
    return result, result.trace


def _iterates_are_valid(plan: Plan, ctx: Context) -> None:
    """Criterion 1: every iterate is a valid plan, checked independently of the solver."""
    traced = _trace(plan, ctx)
    if traced is None:
        return
    result, trace = traced
    index = build_polytope(deduce_order(plan, structure=ctx.structure), ctx).index
    for step, x in enumerate(trace.iterates):
        assert checkers.violations(devectorize(x, result, index), ctx) == [], f"iterate {step}"


def _objective_is_monotone(plan: Plan, ctx: Context) -> None:
    """Criterion 2: the objective never decreases along the iterates (tolerance 1e-9)."""
    traced = _trace(plan, ctx)
    if traced is None:
        return
    for before, after in pairwise(traced[1].values):
        assert after >= before - 1e-9


@given(plan=plans_quelconques(), ctx=contextes())
@_SETTINGS
def test_every_iterate_is_valid_on_arbitrary_inputs(plan: Plan, ctx: Context) -> None:
    _iterates_are_valid(plan, ctx)


@given(scenario=realistic_scenarios())
@_SETTINGS
def test_every_iterate_is_valid_with_walls_and_minimum_areas(
    scenario: tuple[Plan, Context],
) -> None:
    _iterates_are_valid(*scenario)


@given(plan=plans_quelconques(), ctx=contextes())
@_SETTINGS
def test_the_objective_is_monotone_on_arbitrary_inputs(plan: Plan, ctx: Context) -> None:
    _objective_is_monotone(plan, ctx)


@given(scenario=realistic_scenarios())
@_SETTINGS
def test_the_objective_is_monotone_with_walls_and_minimum_areas(
    scenario: tuple[Plan, Context],
) -> None:
    _objective_is_monotone(*scenario)


@given(scenario=realistic_scenarios(), theta=st.floats(0.0, 360.0, allow_nan=False))
@_SETTINGS
def test_the_orientation_is_circular_with_walls_and_minimum_areas(
    scenario: tuple[Plan, Context], theta: float
) -> None:
    """Criterion 3: ``theta`` and ``theta + 360`` reach the same objective value.

    Not always the same plan: with a wall and minimum areas the optimum can be a flat
    face (two rooms trading width at equal daylight), and ``sin(360°) = -2.4e-16``
    breaks the tie elsewhere. Found at 2000 examples; see ``docs/revues/j3.md``."""
    plan, ctx = scenario
    index = build_polytope(deduce_order(plan, structure=ctx.structure), ctx).index
    outcomes: list[float | type] = []
    for azimuth in (theta, theta + 360.0):
        try:
            result = archlux.legalize(
                plan, replace(ctx, orientation=Orientation(deg=azimuth)), objective=ANALYTIC
            )
        except ArchluxError as error:
            outcomes.append(type(error))
            continue
        assert checkers.violations(result, ctx) == []
        outcomes.append(ANALYTIC.evaluate(vectorize(result, index), Orientation(deg=theta)))
    first, second = outcomes
    if isinstance(first, float) and isinstance(second, float):
        assert first == pytest.approx(second, rel=1e-9, abs=1e-9)
    else:
        assert first == second, "one azimuth refused, the other did not"
