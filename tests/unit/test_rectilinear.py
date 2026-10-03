"""Rectilinear decomposition: `MILESTONE-6.md` §2. Convention: leftmost vertical cut."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from shapely.geometry import Polygon, box

from archlux.errors import InvariantViolation
from archlux.geom.rectilinear import (
    MAX_RECTANGLES,
    MERGE_RIGHT,
    decompose,
    recompose,
)
from archlux.types import Plan, Room
from tests.properties.strategies import DEFAULT_CONTEXT


def _L() -> Polygon:
    """Classic L: 1×3 vertical bar + 2×1 base, vertical cut at x=1."""
    return Polygon([(0.0, 0.0), (2.0, 0.0), (2.0, 1.0), (1.0, 1.0), (1.0, 3.0), (0.0, 3.0)])


def test_a_rectangle_stays_one_piece() -> None:
    poly = box(0.0, 0.0, 4.0, 3.0)
    room = decompose(poly, id="living_room", room_type="living_room")
    assert len(room.rectangles) == 1
    assert room.merges == ()
    assert recompose(room).equals(poly)


def test_an_L_is_cut_in_two_by_the_leftmost_vertical_cut() -> None:
    """Milestone 6 convention: vertical cut at the leftmost reflex vertex."""
    room = decompose(_L(), id="kitchen", room_type="kitchen")
    assert len(room.rectangles) == 2
    assert len(room.merges) >= 1
    assert recompose(room).equals(_L())
    # The cut at x=1 produces (0,0,1,3) and (1,0,1,1), in a deterministic order.
    a, b = room.rectangles
    assert {
        (round(a.x, 9), round(a.y, 9), round(a.w, 9), round(a.h, 9)),
        (round(b.x, 9), round(b.y, 9), round(b.w, 9), round(b.h, 9)),
    } == {
        (0.0, 0.0, 1.0, 3.0),
        (1.0, 0.0, 1.0, 1.0),
    }


def test_recompose_inverts_decompose() -> None:
    room = decompose(_L(), id="p", room_type="living_room")
    assert recompose(room).equals(_L())


def test_a_non_rectilinear_polygon_is_refused() -> None:
    with pytest.raises(InvariantViolation, match="rectilinear"):
        decompose(Polygon([(0.0, 0.0), (2.0, 0.0), (1.0, 1.5)]))


def test_the_decomposition_is_deterministic() -> None:
    a = decompose(_L(), id="p", room_type="living_room")
    b = decompose(_L(), id="p", room_type="living_room")
    assert a == b


def _plan_with_l(*, overlapping: bool = False) -> tuple[Plan, object]:
    """A 12×9 tiling holding a decomposed L + three complementary rectangles."""
    room = decompose(_L(), id="kitchen", room_type="kitchen")
    x_r1 = 1.5 if overlapping else 2.0
    w_r1 = 10.5 if overlapping else 10.0
    others = (
        Room(id="r1", type="living_room", x=x_r1, y=0.0, w=w_r1, h=1.0),
        Room(id="r2", type="living_room", x=1.0, y=1.0, w=11.0, h=2.0),
        Room(id="r3", type="living_room", x=0.0, y=3.0, w=12.0, h=6.0),
    )
    plan = Plan(
        rooms=room.rectangles + others,
        walls=(),
        openings=(),
        outline=DEFAULT_CONTEXT.outline,
    )
    return plan, room


def test_extend_merges_imposes_equality() -> None:
    from archlux.geom.graph import deduce_order
    from archlux.geom.polytope import build_polytope, vectorize
    from archlux.geom.rectilinear import extend_merges

    plan, room = _plan_with_l()
    poly = build_polytope(deduce_order(plan), DEFAULT_CONTEXT)
    poly = extend_merges(poly, room)
    assert poly.A_eq.shape[0] >= 1
    assert poly.contains(vectorize(plan, poly.index), tol=1e-6)


def test_legalize_preserves_validity_with_an_L() -> None:
    """`MILESTONE-6.md` §2: legalize on a tiling holding an L stays valid."""
    import archlux

    plan, room = _plan_with_l(overlapping=True)
    q = archlux.legalize(plan, DEFAULT_CONTEXT, merges=(room,))
    assert q.certificate is not None
    assert q.certificate.geometry.valid
    parts = sorted(
        (p for p in q.rooms if p.id.startswith("kitchen__")),
        key=lambda p: (p.x, p.y),
    )
    assert len(parts) == 2
    assert parts[0].x + parts[0].w == pytest.approx(parts[1].x, abs=1e-5)


@st.composite
def rectilinear_polygons(draw: st.DrawFn) -> Polygon:
    """Rectangles and Ls generated on an integer grid (reproducible)."""
    if draw(st.booleans()):
        w = draw(st.integers(1, 5))
        h = draw(st.integers(1, 5))
        x = draw(st.integers(0, 3))
        y = draw(st.integers(0, 3))
        return box(float(x), float(y), float(x + w), float(y + h))
    # L: base width 2..4, bar height 2..5, thickness 1
    w = draw(st.integers(2, 4))
    h = draw(st.integers(2, 5))
    return Polygon(
        [
            (0.0, 0.0),
            (float(w), 0.0),
            (float(w), 1.0),
            (1.0, 1.0),
            (1.0, float(h)),
            (0.0, float(h)),
        ]
    )


@given(poly=rectilinear_polygons())
@settings(max_examples=40, deadline=None)
def test_decomposition_recomposes(poly: Polygon) -> None:
    """`MILESTONE-6.md` §2: recompose(decompose(P)) = P."""
    room = decompose(poly, id="p", room_type="living_room")
    assert recompose(room).equals(poly)
    assert 1 <= len(room.rectangles) <= 4


def test_the_vertical_cut_joins_the_collinear_pieces() -> None:
    """A real L from MSD: the chord and the boundary edge come in separate pieces.

    GEOS returns the intersection of the vertical with the polygon as several collinear
    LineStrings that meet at the reflex vertex. Keeping the first one amounted to
    proposing an edge of the polygon as the cut: it separates nothing, and `decompose`
    raised "no reproducible guillotine cut". On MSD this case is 1,219 rooms out of
    4,456.
    """
    poly = Polygon(
        [
            (-1.785, -2.594),
            (-2.245, -2.594),
            (-2.245, -1.369),
            (-0.569, -1.369),
            (-0.569, -2.995),
            (-1.785, -2.995),
        ]
    )
    room = decompose(poly, id="p", room_type="living_room")
    assert len(room.rectangles) == 2
    assert room.merges == ((0, 1, MERGE_RIGHT),)
    assert recompose(room).equals(poly)


def test_horizontal_fallback_when_no_vertical_separates() -> None:
    """A U lying on its side: no vertical chord separates, the horizontal cut does.

    The vertical convention of `MILESTONE-6.md` §2 keeps priority; the fallback only
    steps in when it fails.
    """
    poly = Polygon(
        [
            (0.0, 0.0),
            (3.0, 0.0),
            (3.0, 1.0),
            (1.0, 1.0),
            (1.0, 2.0),
            (3.0, 2.0),
            (3.0, 3.0),
            (0.0, 3.0),
        ]
    )
    room = decompose(poly, id="u", room_type="living_room", max_rectangles=8)
    assert recompose(room).equals(poly)
    assert len(room.rectangles) >= 3


def test_default_max_rectangles_stays_at_four() -> None:
    """The public cap does not move: the 1.x contract (`ARCHITECTURE.md` §8)."""
    assert MAX_RECTANGLES == 4
    # Three-tooth comb: needs 6 rectangles, hence refused at the default cap.
    comb = Polygon(
        [
            (0.0, 0.0),
            (6.0, 0.0),
            (6.0, 1.0),
            (5.0, 1.0),
            (5.0, 2.0),
            (4.0, 2.0),
            (4.0, 1.0),
            (3.0, 1.0),
            (3.0, 2.0),
            (2.0, 2.0),
            (2.0, 1.0),
            (1.0, 1.0),
            (1.0, 2.0),
            (0.0, 2.0),
        ]
    )
    with pytest.raises(InvariantViolation, match="too many rectangles"):
        decompose(comb, id="e", room_type="living_room")
    room = decompose(comb, id="e", room_type="living_room", max_rectangles=8)
    assert len(room.rectangles) == 6
    assert recompose(room).equals(comb)
