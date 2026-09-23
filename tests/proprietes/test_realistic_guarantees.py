"""Exact guarantees under a context that actually constrains the plan (PLAN.md 0.8).

The output of ``legalize`` is checked by the **independent** checker of ``tests/checkers.py``, never
by ``certify``: re-checking the proof with itself is precisely the blind spot that let a
tautological load-bearing check through (AUDIT.md §3 n°1).

Since PLAN.md batch 1.3 no known failure is left here. A future one must be a strict
xfail naming the exception it expects, so that an unrelated breakage cannot hide behind
it.
"""

from __future__ import annotations

from hypothesis import given, settings

import archlux
from archlux.erreurs import ArchluxError
from archlux.geom.graphe import deduire_ordre
from archlux.geom.polytope import construire_polytope, devectoriser
from archlux.light.analytique import SubstitutAnalytique
from archlux.light.objectif import Daylight
from archlux.types import Contexte, Plan
from tests import checkers
from tests.proprietes.strategies import realistic_scenarios

# One failure per test, so that ``xfail(raises=...)`` sees a plain exception rather than
# an ExceptionGroup of several distinct bugs.
_SETTINGS = settings(max_examples=60, deadline=None, derandomize=True, report_multiple_bugs=False)


def _independent_violations(result: Plan, ctx: Contexte) -> list[str]:
    """Details of the violations found by the shared independent checker."""
    return [violation.detail for violation in checkers.violations(result, ctx)]


@_SETTINGS
@given(scenario=realistic_scenarios())
def test_the_input_is_valid_under_its_own_context(scenario: tuple[Plan, Contexte]) -> None:
    """Sanity check of the strategy itself: any later violation comes from legalize."""
    plan, ctx = scenario
    assert ctx.structure.murs_porteurs, "every scenario must contain a load-bearing wall"
    assert ctx.referentiel.aires_min, "every scenario must declare minimum areas"
    assert _independent_violations(plan, ctx) == []


@_SETTINGS
@given(scenario=realistic_scenarios())
def test_classic_legalization_keeps_every_guarantee(scenario: tuple[Plan, Contexte]) -> None:
    plan, ctx = scenario
    result = archlux.legalize(plan, ctx)
    assert _independent_violations(result, ctx) == []


@_SETTINGS
@given(scenario=realistic_scenarios())
def test_legalize_never_certifies_a_broken_guarantee(scenario: tuple[Plan, Contexte]) -> None:
    """The central promise: either an honest, typed refusal or a plan that keeps every
    exact guarantee. Never a certificate that lies (PLAN.md phase 1 exit criterion)."""
    plan, ctx = scenario
    for objective in (None, SubstitutAnalytique()):
        try:
            result = archlux.legalize(plan, ctx, objective=objective)
        except ArchluxError:
            continue  # refusing is allowed; lying is not
        assert _independent_violations(result, ctx) == []


@_SETTINGS
@given(scenario=realistic_scenarios())
def test_performance_legalization_keeps_every_guarantee(
    scenario: tuple[Plan, Contexte],
) -> None:
    plan, ctx = scenario
    result = archlux.legalize(plan, ctx, objective=SubstitutAnalytique())
    assert _independent_violations(result, ctx) == []


@_SETTINGS
@given(scenario=realistic_scenarios())
def test_every_frank_wolfe_iterate_keeps_every_guarantee(
    scenario: tuple[Plan, Contexte],
) -> None:
    """Not only the output: every intermediate plan of Frank-Wolfe is valid (PLAN.md 1.2).

    This is what makes an interrupted run usable, a claim of the README."""
    plan, ctx = scenario
    result = archlux.legalize(plan, ctx, objective=SubstitutAnalytique(), trace=True)
    assert result.trace is not None
    index = construire_polytope(deduire_ordre(plan, structure=ctx.structure), ctx).index
    for step, x in enumerate(result.trace.iteres):
        iterate = devectoriser(x, result, index)
        assert _independent_violations(iterate, ctx) == [], f"iterate {step}"


@_SETTINGS
@given(scenario=realistic_scenarios())
def test_daylight_objective_is_accepted_by_legalize(scenario: tuple[Plan, Contexte]) -> None:
    plan, ctx = scenario
    objective = Daylight(SubstitutAnalytique(), q_chapeau=1.0)
    result = archlux.legalize(plan, ctx, objective=objective)
    assert _independent_violations(result, ctx) == []


def test_the_checker_detects_each_kind_of_violation() -> None:
    """Guard against a checker that silently accepts everything."""
    from archlux.types import Mur, Orientation, Piece, Referentiel, Structure

    outline = ((0.0, 0.0), (4.0, 0.0), (4.0, 2.0), (0.0, 2.0))
    wall = Mur(id="w", a=(2.0, 0.0), b=(2.0, 2.0), porteur=True)
    ctx = Contexte(
        structure=Structure(murs_porteurs=(wall,)),
        orientation=Orientation(deg=0.0),
        contour=outline,
        referentiel=Referentiel(aires_min=(("bedroom", 5.0),), largeur_min=0.5),
    )

    def plan(*rooms: Piece) -> Plan:
        return Plan(pieces=rooms, murs=(wall,), ouvertures=(), contour=outline)

    valid = plan(
        Piece(id="a", type="bedroom", x=0.0, y=0.0, w=2.0, h=2.0),
        Piece(id="b", type="other", x=2.0, y=0.0, w=2.0, h=2.0),
    )
    assert _independent_violations(valid, ctx) == ["a: area 4.000000 < 5.000000"]
    crossing = plan(
        Piece(id="a", type="other", x=0.0, y=0.0, w=3.0, h=2.0),
        Piece(id="b", type="other", x=3.0, y=0.0, w=1.0, h=2.0),
    )
    assert _independent_violations(crossing, ctx) == ["a crosses load-bearing wall w"]
    gap = plan(Piece(id="a", type="other", x=0.0, y=0.0, w=2.0, h=2.0))
    assert _independent_violations(gap, ctx) == ["rooms cover 4.000000 m² of a 8.000000 m² outline"]
    overlap = plan(
        Piece(id="a", type="other", x=0.0, y=0.0, w=2.5, h=2.0),
        Piece(id="b", type="other", x=2.0, y=0.0, w=2.0, h=2.0),
    )
    assert "a overlaps b" in _independent_violations(overlap, ctx)
