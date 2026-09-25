"""Final review of phase 1 (PLAN.md): the fixes committed without their tests.

- C1: a refusal proves the domain **with** the restrictions ``legalize`` added (tiling
  grid, budget, load-bearing sides...), not the relative order alone; ``Infaisable``
  names them and says which one, dropped, would admit a plan.
- M1: ``verify_exactly`` on a plan with a non-finite or non-positive dimension
  establishes nothing and says so, instead of reporting predicates as holding.
- Fused rooms and load-bearing walls: members of an L keep their own side of a wall
  unless two take opposite sides; forcing the side of the bounding box on every member
  moved a foot that did not touch the wall.
"""

from __future__ import annotations

import math
from dataclasses import replace

import pytest
from shapely.geometry import Polygon

import archlux
from archlux.certify.proof import verify_exactly
from archlux.erreurs import Infaisable
from archlux.geom.graphe import deduire_ordre
from archlux.geom.rectilineaire import decomposer
from archlux.types import Contexte, Mur, Piece, Plan, Referentiel, Structure
from tests import checkers
from tests.proprietes.strategies import CONTEXTE_DEFAUT

# --- C1: the scope of an infeasibility certificate ---------------------------------------


def test_the_message_names_the_scope_and_the_relaxable_restrictions() -> None:
    error = Infaisable(
        None,
        ("frozen contact a|b",),
        verified=True,
        scope=("load-bearing sides", "budget 0.1 m"),
        relaxable=("budget 0.1 m",),
    )
    message = str(error)
    assert message.startswith(
        "infeasible for this relative order with load-bearing sides, budget 0.1 m:"
    )
    assert "[certificate verified exactly]" in message
    assert message.endswith("Without budget 0.1 m, this order admits a plan")
    assert error.scope == ("load-bearing sides", "budget 0.1 m")
    assert error.relaxable == ("budget 0.1 m",)


def test_the_message_without_scope_is_about_the_order_alone() -> None:
    message = str(Infaisable(None, ()))
    assert message == "infeasible for this relative order: no constraint identified"


def _overlapping_pair() -> tuple[Plan, Contexte]:
    """Two rooms overlapping by 1 m: repairing them moves an edge by at least 0.5 m."""
    ctx = CONTEXTE_DEFAUT
    plan = Plan(
        pieces=(
            Piece(id="a", type="sejour", x=0.0, y=0.0, w=7.0, h=9.0),
            Piece(id="b", type="sejour", x=6.0, y=0.0, w=6.0, h=9.0),
        ),
        murs=(),
        ouvertures=(),
        contour=ctx.contour,
    )
    return plan, ctx


def test_a_budget_too_small_is_named_as_the_cause() -> None:
    plan, ctx = _overlapping_pair()
    with pytest.raises(Infaisable) as capture:
        archlux.legalize(plan, ctx, budget=0.1)
    assert capture.value.scope == ("budget 0.1 m",)
    assert capture.value.relaxable == ("budget 0.1 m",)
    assert "Without budget 0.1 m, this order admits a plan" in str(capture.value)


def test_the_same_plan_without_budget_is_repaired() -> None:
    """The counterpart of the test above: ``relaxable`` did not lie."""
    plan, ctx = _overlapping_pair()
    result = archlux.legalize(plan, ctx)
    assert not checkers.violations(result, ctx)


def test_an_infeasible_order_is_not_blamed_on_a_restriction() -> None:
    """Two rooms side by side, each at least 7 m wide, in 12 m: the order is the cause."""
    plan, ctx = _overlapping_pair()
    ctx = replace(ctx, referentiel=Referentiel(aires_min=(), largeur_min=7.0))
    with pytest.raises(Infaisable) as capture:
        archlux.legalize(plan, ctx, budget=1.0)
    assert capture.value.scope == ("budget 1 m",)
    assert capture.value.relaxable == ()
    assert "Without" not in str(capture.value)


# --- M1: a malformed plan proves nothing ---------------------------------------------------


@pytest.mark.parametrize(
    ("field", "value"),
    [("w", 0.0), ("h", -1.0), ("x", math.nan), ("w", math.inf)],
)
def test_a_malformed_room_establishes_no_predicate(field: str, value: float) -> None:
    plan, ctx = _overlapping_pair()
    bad = replace(plan.pieces[1], **{field: value})
    proof = verify_exactly(replace(plan, pieces=(plan.pieces[0], bad)), ctx)
    assert not proof.valide
    assert proof.chevauchement and proof.jours  # "no overlap / no gap" not established
    assert not proof.surfaces_ok and not proof.structure_preservee
    assert proof.violations == (
        f"room b: dimensions must be finite and positive "
        f"(x={bad.x}, y={bad.y}, w={bad.w}, h={bad.h})",
    )


def test_a_malformed_room_has_an_unbounded_displacement_when_not_finite() -> None:
    plan, ctx = _overlapping_pair()
    bad = replace(plan.pieces[1], y=math.nan)
    proof = verify_exactly(replace(plan, pieces=(plan.pieces[0], bad)), ctx, reference=plan)
    assert proof.deplacement_max == math.inf


# --- Fused rooms keep their own side of a wall when no seam can land on it -----------------


def _l_beside_a_partial_wall() -> tuple[Plan, Contexte, tuple[str, str]]:
    """A kitchen L (bar [0,2]x[0,4], foot [2,4]x[0,2]) under a wall x = 3, y in [2, 4].

    The bar is left of the wall, the foot below its lower end: the plan is valid. The
    bounding box of the L, [0,4]x[0,4], crosses the wall; its cheapest side is ``left``,
    which would pull the foot back to x + w <= 3.
    """
    wall = Mur(id="w", a=(3.0, 2.0), b=(3.0, 4.0), porteur=True)
    ctx = replace(
        CONTEXTE_DEFAUT,
        structure=Structure(murs_porteurs=(wall,)),
        referentiel=Referentiel(aires_min=(("kitchen", 10.0),), largeur_min=1.0),
    )
    room = decomposer(
        Polygon([(0, 0), (4, 0), (4, 2), (2, 2), (2, 4), (0, 4)]), id="l", type_piece="kitchen"
    )
    rest = (
        Piece(id="r1", type="living", x=4.0, y=0.0, w=8.0, h=2.0),
        Piece(id="r2a", type="living", x=2.0, y=2.0, w=1.0, h=2.0),
        Piece(id="r2b", type="living", x=3.0, y=2.0, w=9.0, h=2.0),
        Piece(id="r3", type="living", x=0.0, y=4.0, w=12.0, h=5.0),
    )
    plan = Plan(pieces=room.rectangles + rest, murs=(), ouvertures=(), contour=ctx.contour)
    bar, foot = sorted(room.rectangles, key=lambda r: r.x)
    assert (bar.x, bar.w, foot.x, foot.w) == (0.0, 2.0, 2.0, 2.0), "decomposition changed"
    return plan, ctx, (bar.id, foot.id)


def test_each_member_of_an_l_keeps_its_own_side_when_none_are_opposite() -> None:
    plan, ctx, (bar, foot) = _l_beside_a_partial_wall()
    ordre = deduire_ordre(plan, ctx.structure, groups=((bar, foot),))
    sides = {ws.room: ws.side for ws in ordre.wall_sides}
    assert sides[bar] == "left"
    assert sides[foot] == "below"


def test_legalize_leaves_a_valid_l_beside_a_partial_wall_in_place() -> None:
    plan, ctx, _ = _l_beside_a_partial_wall()
    room = decomposer(
        Polygon([(0, 0), (4, 0), (4, 2), (2, 2), (2, 4), (0, 4)]), id="l", type_piece="kitchen"
    )
    assert not checkers.violations(plan, ctx, fusions=(room,)), "the input must be valid"
    result = archlux.legalize(plan, ctx, fusions=(room,))
    assert result.certificat is not None and result.certificat.geometrie.valide
    assert result.certificat.geometrie.deplacement_max == pytest.approx(0.0, abs=1e-6)
    assert not checkers.violations(result, ctx, fusions=(room,))


# --- Phase 1 gate at 2000 examples: an L may close its step, never change order -----------


def test_frank_wolfe_may_close_the_step_of_an_l() -> None:
    """Bar [0,1]x[1,2] under a foot [0,1.01]x[2,9]: a 1 cm step on the high ends.

    Frank-Wolfe meets the ends (the L degenerates into a rectangle): the non-strict order
    of ``overlap_constraints`` allows it, and every exact guarantee holds."""
    from archlux.geom.rectilineaire import PieceRectilineaire
    from archlux.light.analytique import SubstitutAnalytique

    wall = Mur(id="lb0", a=(1.0, 0.0), b=(1.0, 1.0), porteur=True)
    bar = Piece(id="f__0", type="sejour", x=0.0, y=1.0, w=1.0, h=1.0)
    foot = Piece(id="f__1", type="sejour", x=0.0, y=2.0, w=1.01, h=7.0)
    ctx = replace(
        CONTEXTE_DEFAUT,
        structure=Structure(murs_porteurs=(wall,)),
        referentiel=Referentiel(aires_min=(("chambre", 76.93), ("sejour", 1.0)), largeur_min=1.0),
    )
    rest = (
        Piece(id="p0", type="sejour", x=0.0, y=0.0, w=1.0, h=1.0),
        Piece(id="p2", type="sejour", x=1.0, y=0.0, w=1.0, h=2.0),
        Piece(id="p3", type="sejour", x=2.0, y=0.0, w=10.0, h=2.0),
        Piece(id="p5", type="chambre", x=1.01, y=2.0, w=10.99, h=7.0),
    )
    plan = Plan(pieces=(bar, foot, *rest), murs=(wall,), ouvertures=(), contour=ctx.contour)
    room = PieceRectilineaire(
        id="f", rectangles=(bar, foot), fusions=((0, 1, "partage_bord_haut"),)
    )
    result = archlux.legalize(plan, ctx, fusions=(room,), objective=SubstitutAnalytique())
    assert not checkers.violations(result, ctx, fusions=(room,))
    by_id = {r.id: r for r in result.pieces}
    low = (by_id["f__0"].x, by_id["f__1"].x)
    high = (by_id["f__0"].x + by_id["f__0"].w, by_id["f__1"].x + by_id["f__1"].w)
    assert low[0] == pytest.approx(low[1])  # aligned ends stay aligned
    assert high[0] <= high[1] + 1e-9  # the step keeps its order, or closes
