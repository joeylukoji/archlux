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
from archlux.geom.graphe import deduire_ordre
from archlux.geom.polytope import construire_polytope, vectoriser
from archlux.geom.rectilineaire import PieceRectilineaire, decomposer, etendre_fusions
from archlux.types import Contexte, Mur, Piece, Plan, Structure
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
