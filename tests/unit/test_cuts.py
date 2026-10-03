"""Area cuts: `MILESTONE-2.md` §5.

The expected values are literals independent of the implementation: AM-GM gives the
equality on the hyperbola, not a recomputation of the code.
"""

from __future__ import annotations

import pytest

from archlux.errors import InvariantViolation
from archlux.geom.graph import RelativeOrder
from archlux.geom.polytope import build_polytope
from archlux.lmo.cuts import area_cut, violated_areas
from archlux.types import Context, Orientation, Regulation, Room, Structure

CTX = Context(
    structure=Structure(load_bearing_walls=()),
    orientation=Orientation(deg=0.0),
    outline=((0.0, 0.0), (10.0, 0.0), (10.0, 8.0), (0.0, 8.0)),
    regulation=Regulation(min_areas=(("living_room", 9.0),), min_width=1.5),
)


class TestTangent:
    """Formula: h₀ w + w₀ h ≥ 2a at the point of the hyperbola w₀ h₀ = a."""

    def test_equality_at_the_linearization_point(self) -> None:
        """(w, h) = (3, 3), a = 9: 3·3 + 3·3 = 18 = 2a."""
        cut = area_cut(3.0, 3.0, 9.0)
        assert cut.satisfied(3.0, 3.0)
        assert cut.lower_bound == pytest.approx(18.0)

    def test_a_larger_rectangle_passes(self) -> None:
        """4 × 3 = 12 > 9: the point stays on the right side of the tangent."""
        assert area_cut(3.0, 3.0, 9.0).satisfied(4.0, 3.0)

    def test_a_square_too_small_is_cut(self) -> None:
        """2 × 2 = 4 < 9. After projection, the tangent excludes this point."""
        assert not area_cut(2.0, 2.0, 9.0).satisfied(2.0, 2.0)

    def test_the_origin_names_the_room(self) -> None:
        assert "living_room" in area_cut(3.0, 3.0, 9.0, room="living_room").origin

    def test_a_degenerate_point_is_refused(self) -> None:
        with pytest.raises(InvariantViolation, match="strictly positive"):
            area_cut(0.0, 3.0, 9.0)


class TestViolatedAreas:
    """Direct reading of w·h against a_min, without going through the solver."""

    def test_a_room_below_the_threshold_is_listed(self) -> None:
        poly = build_polytope(RelativeOrder((), (), ("A",)), CTX)
        # A.x, A.y, A.w, A.h
        x = [0.0, 0.0, 2.0, 2.0]
        rooms = (Room(id="A", type="living_room", x=0.0, y=0.0, w=2.0, h=2.0),)
        assert violated_areas(x, poly, CTX, rooms=rooms) == ("A",)

    def test_a_room_at_the_threshold_is_not_listed(self) -> None:
        poly = build_polytope(RelativeOrder((), (), ("A",)), CTX)
        x = [0.0, 0.0, 3.0, 3.0]
        rooms = (Room(id="A", type="living_room", x=0.0, y=0.0, w=3.0, h=3.0),)
        assert violated_areas(x, poly, CTX, rooms=rooms) == ()
