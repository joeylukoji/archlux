"""L-shaped rooms keep their shape and their area through legalization (PLAN.md 1.7).

An L room is decomposed into sub-rectangles tied by fusion equalities
(:mod:`archlux.geom.rectilineaire`). The equalities only glue one edge line: without
constraints on the orthogonal axis the sub-rectangles slide along it, and the L turns
into a T, a Z, or two detached pieces (AUDIT.md §5.2).
"""

from __future__ import annotations

from dataclasses import replace

import pytest
from shapely.geometry import Polygon

import archlux
from archlux.certify.proof import verify_exactly
from archlux.geom.graphe import deduire_ordre
from archlux.geom.polytope import construire_polytope, vectoriser
from archlux.geom.rectilineaire import PieceRectilineaire, decomposer, etendre_fusions
from archlux.types import Contexte, Mur, Piece, Plan, Referentiel, Structure
from tests import checkers
from tests.proprietes.strategies import CONTEXTE_DEFAUT


def _pushed_l_plan() -> tuple[Plan, Contexte, PieceRectilineaire]:
    """A 12 x 9 tiling where a load-bearing wall pushes the foot of an L upwards.

    The L is a bar ``l__0`` = [0, 2] x [1, 5.5] and a foot ``l__1`` = [2, 6] x [1, 3],
    bottoms aligned. A load-bearing wall at ``y = 1.8`` under the foot crosses it and
    room ``d`` below; room ``h`` overlaps the bar. The cheapest repair lifts the foot
    alone and shrinks ``h``, which turns the L into a T. Lifting the whole L (the bar
    shrinks under ``f``) is valid too and keeps the L.
    """
    outline = Polygon([(0, 1), (6, 1), (6, 3), (2, 3), (2, 5.5), (0, 5.5)])
    room = decomposer(outline, id="l", type_piece="kitchen")
    others = (
        Piece(id="h", type="living", x=0.0, y=0.0, w=2.0, h=2.0),
        Piece(id="d", type="living", x=2.0, y=0.0, w=4.0, h=2.0),
        Piece(id="f", type="living", x=0.0, y=5.5, w=2.0, h=3.5),
        Piece(id="e", type="living", x=2.0, y=3.8, w=4.0, h=5.2),
        Piece(id="g", type="living", x=6.0, y=0.0, w=6.0, h=9.0),
    )
    plan = Plan(
        pieces=room.rectangles + others,
        murs=(),
        ouvertures=(),
        contour=CONTEXTE_DEFAUT.contour,
    )
    wall = Mur(id="wall", a=(2.0, 1.8), b=(6.0, 1.8), porteur=True)
    ctx = replace(CONTEXTE_DEFAUT, structure=Structure(murs_porteurs=(wall,)))
    return plan, ctx, room


def _by_id(plan: Plan) -> dict[str, Piece]:
    return {room.id: room for room in plan.pieces}


def test_legalize_keeps_the_aligned_edge_of_an_l() -> None:
    plan, ctx, room = _pushed_l_plan()

    legal = archlux.legalize(plan, ctx, fusions=(room,))

    assert legal.certificat is not None and legal.certificat.geometrie.valide
    rooms = _by_id(legal)
    bar, foot = rooms["l__0"], rooms["l__1"]
    # Still an L: the bottoms stay aligned and the foot stays within the bar's side.
    assert foot.y == pytest.approx(bar.y, abs=1e-6)
    assert foot.y + foot.h <= bar.y + bar.h + 1e-6
    assert foot.x == pytest.approx(bar.x + bar.w, abs=1e-6)


@pytest.mark.parametrize(("foot_y", "shape"), [(2.5, "Z"), (4.0, "detached")])
def test_fused_polytope_excludes_a_slid_foot(foot_y: float, shape: str) -> None:
    """Bar [0, 1] x [0, 3], foot [1, 2] x [0, 1]: sliding the foot up leaves the domain."""
    outline = Polygon([(0, 0), (2, 0), (2, 1), (1, 1), (1, 3), (0, 3)])
    room = decomposer(outline, id="l", type_piece="kitchen")
    plan = Plan(pieces=room.rectangles, murs=(), ouvertures=(), contour=CONTEXTE_DEFAUT.contour)
    poly = etendre_fusions(
        construire_polytope(deduire_ordre(plan), CONTEXTE_DEFAUT), room, min_contact=0.5
    )
    assert poly.contient(vectoriser(plan, poly.index))

    bar, foot = room.rectangles
    slid = replace(plan, pieces=(bar, replace(foot, y=foot_y)))

    assert not poly.contient(vectoriser(slid, poly.index)), shape


def _small_l() -> tuple[Plan, PieceRectilineaire]:
    """Bar [0, 1] x [0, 3] (3 m²) and foot [1, 2] x [0, 1] (1 m²): 4 m² in total."""
    outline = Polygon([(0, 0), (2, 0), (2, 1), (1, 1), (1, 3), (0, 3)])
    room = decomposer(outline, id="l", type_piece="kitchen")
    plan = Plan(pieces=room.rectangles, murs=(), ouvertures=(), contour=CONTEXTE_DEFAUT.contour)
    return plan, room


def _kitchen_minimum(area: float) -> Contexte:
    return replace(
        CONTEXTE_DEFAUT, referentiel=Referentiel(aires_min=(("kitchen", area),), largeur_min=1.0)
    )


def test_proof_accepts_an_l_whose_union_meets_the_minimum_area() -> None:
    plan, room = _small_l()

    proof = verify_exactly(plan, _kitchen_minimum(3.5), fusions=(room,))

    assert proof.surfaces_ok, proof.violations


def test_proof_refuses_an_l_whose_union_misses_the_minimum_area() -> None:
    plan, room = _small_l()

    proof = verify_exactly(plan, _kitchen_minimum(4.5), fusions=(room,))

    assert not proof.surfaces_ok
    assert any(v.startswith("area l:") for v in proof.violations), proof.violations


def _tiling_with_small_l() -> tuple[Plan, PieceRectilineaire]:
    """The 4 m² L of :func:`_small_l` inside a valid 12 x 9 tiling."""
    plan, room = _small_l()
    rest = (
        Piece(id="r1", type="living", x=2.0, y=0.0, w=10.0, h=1.0),
        Piece(id="r2", type="living", x=1.0, y=1.0, w=11.0, h=2.0),
        Piece(id="r3", type="living", x=0.0, y=3.0, w=12.0, h=6.0),
    )
    return replace(plan, pieces=plan.pieces + rest), room


def test_legalize_keeps_an_l_whose_union_meets_the_minimum_area() -> None:
    """Each sub-rectangle (3 and 1 m²) is below 3.5 m², the room (4 m²) is not."""
    plan, room = _tiling_with_small_l()

    legal = archlux.legalize(plan, _kitchen_minimum(3.5), fusions=(room,))

    assert legal.certificat is not None and legal.certificat.geometrie.valide
    assert legal.certificat.geometrie.deplacement_max == pytest.approx(0.0, abs=1e-6)


def test_legalize_grows_an_l_whose_union_misses_the_minimum_area() -> None:
    plan, room = _tiling_with_small_l()
    ctx = _kitchen_minimum(4.5)

    legal = archlux.legalize(plan, ctx, fusions=(room,), pavage=True)

    assert legal.certificat is not None and legal.certificat.geometrie.valide
    assert checkers.violations(legal, ctx, fusions=(room,)) == []
    parts = [r for r in legal.pieces if r.id.startswith("l__")]
    assert sum(r.w * r.h for r in parts) >= 4.5 - 1e-6


@pytest.mark.parametrize(("minimum", "short"), [(3.5, False), (4.5, True)])
def test_checker_measures_a_fused_room_as_a_whole(minimum: float, short: bool) -> None:
    plan, room = _tiling_with_small_l()

    found = checkers.violations(plan, _kitchen_minimum(minimum), fusions=(room,))

    assert [v.detail.split(":")[0] for v in found if v.kind == "area"] == (["l"] if short else [])


def test_checker_refuses_a_detached_fused_room() -> None:
    plan, room = _small_l()
    bar, foot = plan.pieces
    detached = replace(plan, pieces=(bar, replace(foot, y=4.0)))

    found = checkers.violations(detached, _kitchen_minimum(0.0), fusions=(room,))

    assert any(v.kind == "area" and v.detail.startswith("l:") for v in found), found


# --- Review of the merged batches 1.7 and 1.8 ---------------------------------------------


def _l_in_tiling(wall_x: float | None = None) -> tuple[Plan, Contexte, PieceRectilineaire]:
    """A kitchen L (bar [0,1]x[0,3], foot [1,2]x[0,1]) tiling 12 x 9 with three rooms."""
    ctx = replace(
        CONTEXTE_DEFAUT,
        referentiel=Referentiel(aires_min=(("kitchen", 3.5),), largeur_min=1.0),
    )
    if wall_x is not None:
        wall = Mur(id="w", a=(wall_x, 0.0), b=(wall_x, 1.0), porteur=True)
        ctx = replace(ctx, structure=Structure(murs_porteurs=(wall,)))
    room = decomposer(
        Polygon([(0, 0), (2, 0), (2, 1), (1, 1), (1, 3), (0, 3)]), id="l", type_piece="kitchen"
    )
    rest = (
        Piece(id="r1", type="living", x=2.0, y=0.0, w=10.0, h=1.0),
        Piece(id="r2", type="living", x=1.0, y=1.0, w=11.0, h=2.0),
        Piece(id="r3", type="living", x=0.0, y=3.0, w=12.0, h=6.0),
    )
    plan = Plan(pieces=room.rectangles + rest, murs=(), ouvertures=(), contour=ctx.contour)
    return plan, ctx, room


def test_a_wall_on_the_seam_of_an_l_is_a_crossing() -> None:
    """Review C1: the seam is inside the room; a wall on it cuts the kitchen in two."""
    plan, ctx, room = _l_in_tiling(wall_x=1.0)
    proof = verify_exactly(plan, ctx, fusions=(room,))
    assert not proof.valide and not proof.structure_preservee
    assert any(v.kind == "wall" for v in checkers.violations(plan, ctx, fusions=(room,)))


@pytest.mark.parametrize("pavage", [False, True])
def test_legalize_never_puts_a_seam_on_a_wall(pavage: bool) -> None:
    """Review C1: the solver used to widen the bar until the seam sat on the wall."""
    plan, ctx, room = _l_in_tiling(wall_x=1.4)
    try:
        result = archlux.legalize(plan, ctx, fusions=(room,), pavage=pavage)
    except archlux.Infaisable:
        return  # an L straddling a wall has no valid plan in this order: honest refusal
    assert result.certificat is not None and result.certificat.geometrie.valide
    assert not checkers.violations(result, ctx, fusions=(room,))


def test_the_proof_checks_every_recorded_seam_with_the_minimum_width() -> None:
    """Review M1: connectivity alone accepted a neck of 5e-7 m; the checker did not."""
    plan, ctx, room = _l_in_tiling()
    rooms = _by_id(plan)
    for foot_y in (3.0 - 5e-7, 2.9):  # a hair of contact, then 0.1 m < largeur_min
        slid = replace(rooms["l__1"], y=foot_y)
        moved = replace(plan, pieces=(rooms["l__0"], slid, *plan.pieces[2:]))
        proof = verify_exactly(moved, ctx, fusions=(room,))
        assert not proof.surfaces_ok
        assert any("seam" in v for v in proof.violations)
        assert checkers.violations(moved, ctx, fusions=(room,))


def test_a_fused_room_without_area_is_an_input_limit() -> None:
    """Review m3: a user input, not an internal fault."""
    from archlux.erreurs import UnsupportedInput
    from archlux.geom.rectilineaire import minimum_area_shares

    _, ctx, room = _l_in_tiling()
    flat = tuple(replace(r, w=0.0) for r in room.rectangles)
    with pytest.raises(UnsupportedInput, match="no area"):
        minimum_area_shares(flat, (room,), ctx.referentiel)


def test_the_area_shares_keep_the_proof_tolerance_per_part() -> None:
    """Review m4: k parts each short by the solver tolerance must not miss the minimum."""
    from archlux.geom.rectilineaire import minimum_area_shares
    from archlux.tolerances import AREA_PROOF_M2

    plan, ctx, room = _l_in_tiling()
    shares = minimum_area_shares(plan.pieces, (room,), ctx.referentiel)
    assert sum(share - AREA_PROOF_M2 for share in shares.values()) >= 3.5 - 1e-12
