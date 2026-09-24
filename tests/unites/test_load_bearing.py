"""Load-bearing walls are constrained by the solver and verified by the proof (PLAN.md 1.1).

Before this batch the proof compared each load-bearing wall with itself (walls are not
decision variables), so a room could cross one while the certificate read
"structure preserved: yes" (AUDIT.md §3 n°1).
"""

from __future__ import annotations

import numpy as np
import pytest

import archlux
from archlux.certify.proof import verify_exactly
from archlux.erreurs import UnsupportedInput
from archlux.geom.graphe import WallSide, deduire_ordre
from archlux.geom.polytope import construire_polytope, vectoriser
from archlux.light.analytique import SubstitutAnalytique
from archlux.light.protocole import Substitut
from archlux.types import Contexte, Mur, Orientation, Piece, Plan, Referentiel, Structure
from tests import checkers

_OUTLINE = ((0.0, 0.0), (10.0, 0.0), (10.0, 6.0), (0.0, 6.0))
_FULL = Mur(id="w", a=(6.0, 0.0), b=(6.0, 6.0), porteur=True)
_PARTIAL = Mur(id="p", a=(6.0, 0.0), b=(6.0, 3.0), porteur=True)


def _ctx(*walls: Mur, areas: tuple[tuple[str, float], ...] = ()) -> Contexte:
    return Contexte(
        structure=Structure(murs_porteurs=walls),
        orientation=Orientation(deg=30.0),
        contour=_OUTLINE,
        referentiel=Referentiel(aires_min=areas, largeur_min=1.0),
    )


def _plan(*rooms: Piece, walls: tuple[Mur, ...] = ()) -> Plan:
    return Plan(pieces=rooms, murs=walls, ouvertures=(), contour=_OUTLINE)


def _room(rid: str, x: float, y: float, w: float, h: float) -> Piece:
    return Piece(id=rid, type="chambre", x=x, y=y, w=w, h=h)


# --- Order: which side of each wall every room stays on -------------------------------


def test_rooms_on_each_side_of_a_full_wall() -> None:
    plan = _plan(_room("a", 0, 0, 6, 6), _room("b", 6, 0, 4, 6))
    sides = deduire_ordre(plan, structure=Structure((_FULL,))).wall_sides
    assert set(sides) == {
        WallSide(room="a", wall="w", side="left", bound=6.0),
        WallSide(room="b", wall="w", side="right", bound=6.0),
    }


def test_a_room_crossing_the_wall_is_sent_to_the_side_of_its_centre() -> None:
    plan = _plan(_room("a", 0, 0, 7, 6), _room("b", 7, 0, 3, 6))  # a crosses x = 6
    sides = {s.room: s.side for s in deduire_ordre(plan, structure=Structure((_FULL,))).wall_sides}
    assert sides == {"a": "left", "b": "right"}


def test_a_room_beyond_the_end_of_a_partial_wall_stays_beyond_it() -> None:
    plan = _plan(_room("low", 0, 0, 6, 3), _room("high", 0, 3, 10, 3), _room("r", 6, 0, 4, 3))
    sides = {
        s.room: (s.side, s.bound) for s in deduire_ordre(plan, Structure((_PARTIAL,))).wall_sides
    }
    assert sides["high"] == ("above", 3.0)
    assert sides["low"] == ("left", 6.0)
    assert sides["r"] == ("right", 6.0)


def test_a_room_overflowing_the_end_of_a_partial_wall_is_moved_past_the_end() -> None:
    """Review M1: 1 cm over the end of a partial wall must not send a 10 m room across it."""
    plan = _plan(
        _room("low", 0, 0, 6, 2.99), _room("high", 0, 2.99, 10, 3.01), _room("r", 6, 0, 4, 2.99)
    )
    sides = {
        s.room: (s.side, s.bound) for s in deduire_ordre(plan, Structure((_PARTIAL,))).wall_sides
    }
    assert sides["high"] == ("above", 3.0)


def test_a_wide_room_across_a_full_wall_is_never_sent_beyond_the_outline() -> None:
    """A full wall ends on the outline: going 'below' or 'above' it is impossible."""
    plan = _plan(_room("wide", 0, 0, 10, 2), _room("top", 0, 2, 10, 4))
    sides = {s.room: s.side for s in deduire_ordre(plan, Structure((_FULL,))).wall_sides}
    assert sides["wide"] in ("left", "right")


def test_legalize_repairs_a_room_overflowing_a_partial_wall_end() -> None:
    ctx = _ctx(_PARTIAL)
    plan = _plan(
        _room("low", 0, 0, 6, 2.99), _room("high", 0, 2.99, 10, 3.01), _room("r", 6, 0, 4, 2.99)
    )
    result = archlux.legalize(plan, ctx, pavage=True)
    assert checkers.violations(result, ctx) == []
    assert np.isclose({r.id: r for r in result.pieces}["high"].y, 3.0)


def test_without_structure_the_order_has_no_wall_sides() -> None:
    assert deduire_ordre(_plan(_room("a", 0, 0, 10, 6))).wall_sides == ()


def test_an_oblique_load_bearing_wall_is_refused_not_ignored() -> None:
    oblique = Mur(id="o", a=(0.0, 0.0), b=(10.0, 6.0), porteur=True)
    with pytest.raises(UnsupportedInput, match="axis-aligned"):
        deduire_ordre(_plan(_room("a", 0, 0, 10, 6)), structure=Structure((oblique,)))


# --- Polytope: one row per (room, wall), satisfied by a valid plan --------------------


def test_the_polytope_carries_one_row_per_room_and_wall() -> None:
    plan = _plan(_room("a", 0, 0, 6, 6), _room("b", 6, 0, 4, 6))
    ctx = _ctx(_FULL)
    poly = construire_polytope(deduire_ordre(plan, structure=ctx.structure), ctx)
    rows = [o for o in poly.origines if o.startswith("load-bearing")]
    assert sorted(rows) == ["load-bearing w: a left of 6", "load-bearing w: b right of 6"]
    assert poly.contient(vectoriser(plan, poly.index))


def test_the_polytope_excludes_a_plan_crossing_the_wall() -> None:
    valid = _plan(_room("a", 0, 0, 6, 6), _room("b", 6, 0, 4, 6))
    ctx = _ctx(_FULL)
    poly = construire_polytope(deduire_ordre(valid, structure=ctx.structure), ctx)
    crossing = _plan(_room("a", 0, 0, 7, 6), _room("b", 7, 0, 3, 6))
    assert not poly.contient(vectoriser(crossing, poly.index))


# --- Proof: a crossing is a violation, whatever the wall's direction ------------------


def test_the_proof_rejects_a_room_crossing_a_load_bearing_wall() -> None:
    ctx = _ctx(_FULL)
    crossing = _plan(_room("a", 0, 0, 7, 6), _room("b", 7, 0, 3, 6), walls=(_FULL,))
    proof = verify_exactly(crossing, ctx)
    assert not proof.structure_preservee and not proof.valide
    assert any("a" in v and "w" in v and "crosses" in v for v in proof.violations)


def test_the_proof_accepts_rooms_bounded_by_the_wall() -> None:
    ctx = _ctx(_FULL)
    plan = _plan(_room("a", 0, 0, 6, 6), _room("b", 6, 0, 4, 6), walls=(_FULL,))
    assert verify_exactly(plan, ctx).structure_preservee


@pytest.mark.parametrize(("overlap", "accepted"), [(5e-8, True), (1e-3, False)])
def test_the_proof_tolerates_solver_noise_but_not_a_real_crossing(
    overlap: float, accepted: bool
) -> None:
    """Review minor 4: an LP output a hair past the wall line (< WALL_M) is not a false
    refusal; a millimetre is a crossing."""
    plan = _plan(_room("a", 0, 0, 6 + overlap, 6), _room("b", 6 + overlap, 0, 4 - overlap, 6))
    assert verify_exactly(plan, _ctx(_FULL)).structure_preservee is accepted


def test_the_proof_checks_oblique_walls_too() -> None:
    oblique = Mur(id="o", a=(0.0, 0.0), b=(10.0, 6.0), porteur=True)
    plan = _plan(_room("a", 0, 0, 10, 6), walls=(oblique,))
    assert not verify_exactly(plan, _ctx(oblique)).structure_preservee


def test_the_proof_no_longer_requires_the_plan_to_repeat_the_structure() -> None:
    """Walls are context: a plan without ``murs`` is judged on crossings only."""
    plan = _plan(_room("a", 0, 0, 6, 6), _room("b", 6, 0, 4, 6))
    assert verify_exactly(plan, _ctx(_FULL)).structure_preservee


# --- End to end: both modes keep the wall ----------------------------------------------


@pytest.mark.parametrize("objective", [None, SubstitutAnalytique()], ids=["classic", "performance"])
def test_legalize_never_crosses_a_load_bearing_wall(objective: Substitut | None) -> None:
    ctx = _ctx(_FULL)
    plan = _plan(_room("a", 0, 0, 6, 3), _room("c", 0, 3, 6, 3), _room("b", 6, 0, 4, 6))
    result = archlux.legalize(plan, ctx, objective=objective)
    assert [v for v in checkers.violations(result, ctx) if v.kind == "wall"] == []
    assert result.certificat is not None and result.certificat.geometrie.structure_preservee


def test_legalize_moves_a_crossing_room_back_behind_the_wall() -> None:
    ctx = _ctx(_FULL)
    plan = _plan(_room("a", 0, 0, 6.4, 6), _room("b", 6.4, 0, 3.6, 6))
    result = archlux.legalize(plan, ctx, pavage=True)  # tiling closes the gap left at 6.4
    rooms = {r.id: r for r in result.pieces}
    assert np.isclose(rooms["a"].x + rooms["a"].w, 6.0)
    assert np.isclose(rooms["b"].x, 6.0)


def test_the_audit_grid_keeps_its_load_bearing_wall_in_performance_mode() -> None:
    """AUDIT.md §5.3, measured: on a 5 x 3 grid with a load-bearing wall at x = 6,
    Frank-Wolfe used to place partitions at 3.796 and 11.204 and certify it."""
    outline = ((0.0, 0.0), (15.0, 0.0), (15.0, 9.0), (0.0, 9.0))
    wall = Mur(id="x6", a=(6.0, 0.0), b=(6.0, 9.0), porteur=True)
    ctx = Contexte(
        structure=Structure(murs_porteurs=(wall,)),
        orientation=Orientation(deg=20.0),
        contour=outline,
        referentiel=Referentiel(aires_min=(), largeur_min=1.0),
    )
    rooms = tuple(
        Piece(id=f"c{i}{j}", type="chambre", x=3.0 * i, y=3.0 * j, w=3.0, h=3.0)
        for i in range(5)
        for j in range(3)
    )
    plan = Plan(pieces=rooms, murs=(), ouvertures=(), contour=outline)
    result = archlux.legalize(plan, ctx, objective=SubstitutAnalytique())
    assert checkers.violations(result, ctx) == []
