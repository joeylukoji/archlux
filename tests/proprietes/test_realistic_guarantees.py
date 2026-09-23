"""Exact guarantees under a context that actually constrains the plan (PLAN.md 0.8).

The output of ``legalize`` is checked by an **independent** checker written here, never
by ``certify``: re-checking the proof with itself is precisely the blind spot that let a
tautological load-bearing check through (AUDIT.md §3 n°1).

Known failures are strict xfails that name the exception they expect, so that an
unrelated breakage can never hide behind them.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings

import archlux
from archlux.erreurs import InvariantViole
from archlux.light.analytique import SubstitutAnalytique
from archlux.light.objectif import Daylight
from archlux.types import Contexte, Plan
from tests.proprietes.strategies import realistic_scenarios

_TOL = 1e-6
# One failure per test, so that ``xfail(raises=...)`` sees a plain exception rather than
# an ExceptionGroup of several distinct bugs.
_SETTINGS = settings(max_examples=60, deadline=None, derandomize=True, report_multiple_bugs=False)


def _outline_area(ctx: Contexte) -> float:
    xs = [x for x, _ in ctx.contour]
    ys = [y for _, y in ctx.contour]
    return (max(xs) - min(xs)) * (max(ys) - min(ys))


def _independent_violations(result: Plan, ctx: Contexte) -> list[str]:
    """Tiling, minimum areas and load-bearing walls, checked from coordinates only.

    The outline is the axis-aligned rectangle of the test context; rooms are rectangles.
    Pairwise disjoint rooms whose areas add up to the outline area tile it exactly.
    """
    violations: list[str] = []
    rooms = result.pieces

    for i, a in enumerate(rooms):
        for b in rooms[i + 1 :]:
            dx = min(a.x + a.w, b.x + b.w) - max(a.x, b.x)
            dy = min(a.y + a.h, b.y + b.h) - max(a.y, b.y)
            if dx > _TOL and dy > _TOL:
                violations.append(f"{a.id} overlaps {b.id}")
    total = sum(room.w * room.h for room in rooms)
    if abs(total - _outline_area(ctx)) > _TOL:
        violations.append(f"rooms cover {total:.6f} m² of a {_outline_area(ctx):.6f} m² outline")

    for room in rooms:
        minimum = ctx.referentiel.a_min(room.type)
        if room.w * room.h < minimum - _TOL:
            violations.append(f"{room.id}: area {room.w * room.h:.6f} < {minimum:.6f}")

    for wall in ctx.structure.murs_porteurs:
        (xa, ya), (xb, yb) = wall.a, wall.b
        vertical, horizontal = abs(xa - xb) < _TOL, abs(ya - yb) < _TOL
        assert vertical or horizontal, f"checker only handles axis-aligned walls: {wall}"
        for room in rooms:
            x0, x1, y0, y1 = room.x, room.x + room.w, room.y, room.y + room.h
            if vertical:
                crosses = x0 + _TOL < xa < x1 - _TOL
                overlap = min(y1, max(ya, yb)) - max(y0, min(ya, yb))
            else:
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
    assert ctx.structure.murs_porteurs, "every scenario must contain a load-bearing wall"
    assert ctx.referentiel.aires_min, "every scenario must declare minimum areas"
    assert _independent_violations(plan, ctx) == []


@_SETTINGS
@given(scenario=realistic_scenarios())
def test_classic_legalization_keeps_every_guarantee(scenario: tuple[Plan, Contexte]) -> None:
    plan, ctx = scenario
    result = archlux.legalize(plan, ctx)
    assert _independent_violations(result, ctx) == []


@pytest.mark.xfail(
    strict=True,
    raises=(AssertionError, InvariantViole),
    reason=(
        "Frank-Wolfe goes below minimum areas (InvariantViole) and crosses load-bearing "
        "walls unnoticed — AUDIT.md §3 n°1 and n°6; fixed in PLAN.md 1.1, 1.2 and 1.5"
    ),
)
@_SETTINGS
@given(scenario=realistic_scenarios())
def test_performance_legalization_keeps_every_guarantee(
    scenario: tuple[Plan, Contexte],
) -> None:
    plan, ctx = scenario
    result = archlux.legalize(plan, ctx, objective=SubstitutAnalytique())
    assert _independent_violations(result, ctx) == []


@pytest.mark.xfail(
    strict=True,
    raises=TypeError,
    reason="Daylight lacks the 'baies' keyword of Substitut — AUDIT.md §3 n°3, PLAN.md 1.3",
)
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
