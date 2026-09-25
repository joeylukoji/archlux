"""Milestone 2 criterion replayed as written, then with load-bearing walls (phase 2, J2).

``MILESTONE-2.md`` §0 draws ``plans_quelconques()`` and ``contextes()``: any plan, any
context. The test that closed the milestone (``test_acceptation_jalon2.py``) drew
``plans_valides()`` under one fixed context, inputs that are already valid, so it could
not see a wrong output. Replayed as written, ``legalize`` refuses most arbitrary plans
(a gap cannot be filled without ``pavage``): the criterion "every output is valid"
holds for every plan it **returns**, and every refusal is typed. That reading is what
is asserted here; the review (``docs/revues/j2.md``) records the refusal rates.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

import archlux
from archlux.data.corruption import corrompre
from archlux.erreurs import ArchluxError
from archlux.types import Contexte, Plan
from tests import checkers
from tests.proprietes.strategies import (
    GATE_EXAMPLES,
    contextes,
    plans_quelconques,
    realistic_scenarios,
)


def _returned_plans_are_valid(plan: Plan, ctx: Contexte, *, pavage: bool) -> None:
    try:
        result = archlux.legalize(plan, ctx, pavage=pavage)
    except ArchluxError:
        return  # a typed refusal is allowed; any other exception fails the test
    assert result.certificat is not None and result.certificat.geometrie.valide
    assert checkers.violations(result, ctx) == []


@given(plan=plans_quelconques(), ctx=contextes())
@settings(max_examples=500, deadline=None, derandomize=True)
def test_every_returned_plan_is_valid_on_arbitrary_inputs(plan: Plan, ctx: Contexte) -> None:
    """The criterion as written: arbitrary plans and contexts, 500 examples."""
    _returned_plans_are_valid(plan, ctx, pavage=False)


@given(
    scenario=realistic_scenarios(),
    seed=st.integers(min_value=0, max_value=2**31 - 1),
    amplitude=st.sampled_from((0.1, 0.25, 0.5)),
    pavage=st.booleans(),
)
@settings(max_examples=GATE_EXAMPLES, deadline=None, derandomize=True)
def test_every_returned_plan_is_valid_with_walls_and_one_fault(
    scenario: tuple[Plan, Contexte], seed: int, amplitude: float, pavage: bool
) -> None:
    """PLAN.md phase 2: replayed with load-bearing walls, minimum areas and one fault."""
    plan, ctx = scenario
    faulty, _ = corrompre(plan, seed=seed, amplitude=amplitude)
    _returned_plans_are_valid(faulty, ctx, pavage=pavage)
