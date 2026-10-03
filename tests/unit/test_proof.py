"""Exact check: `MILESTONE-2.md` §6.

The cases are geometries computable by hand, not solver oracles.
"""

from __future__ import annotations

from archlux.certify.proof import verify_exactly
from archlux.types import (
    Context,
    Orientation,
    Plan,
    Regulation,
    Room,
    Structure,
    Wall,
)
from tests.properties.strategies import DEFAULT_CONTEXT

CTX = DEFAULT_CONTEXT


def _plan(*rooms: Room) -> Plan:
    return Plan(rooms=rooms, walls=(), openings=(), outline=CTX.outline)


class TestOverlap:
    def test_detects_an_overlap(self) -> None:
        """Two 2×2 squares whose intersection is 1 m²."""
        a = Room(id="cuisine", type="kitchen", x=0.0, y=0.0, w=2.0, h=2.0)
        b = Room(id="sdb", type="bathroom", x=1.0, y=0.0, w=2.0, h=2.0)
        proof = verify_exactly(_plan(a, b), CTX)
        assert proof.overlap is True
        assert proof.valid is False
        assert any("overlap cuisine|sdb" in v for v in proof.violations)

    def test_two_disjoint_rooms_do_not_overlap(self) -> None:
        a = Room(id="a", type="living_room", x=0.0, y=0.0, w=2.0, h=2.0)
        b = Room(id="b", type="living_room", x=3.0, y=0.0, w=2.0, h=2.0)
        assert verify_exactly(_plan(a, b), CTX).overlap is False


class TestGaps:
    def test_detects_a_gap(self) -> None:
        """A 2×2 room in 12×9 leaves a gap of area 108 − 4 = 104 m²."""
        p = Room(id="a", type="living_room", x=0.0, y=0.0, w=2.0, h=2.0)
        proof = verify_exactly(_plan(p), CTX)
        assert proof.gaps is True
        assert proof.valid is False


class TestAreas:
    def test_insufficient_area(self) -> None:
        ctx = Context(
            structure=Structure(load_bearing_walls=()),
            orientation=Orientation(deg=0.0),
            outline=CTX.outline,
            regulation=Regulation(min_areas=(("bathroom", 5.0),), min_width=1.0),
        )
        p = Room(id="sdb", type="bathroom", x=0.0, y=0.0, w=2.0, h=2.0)
        proof = verify_exactly(_plan(p), ctx)
        assert proof.areas_ok is False


class TestStructure:
    def test_moved_load_bearing_wall(self) -> None:
        wall = Wall(id="p1", a=(0.0, 0.0), b=(3.0, 0.0), load_bearing=True)
        ctx = Context(
            structure=Structure(load_bearing_walls=(wall,)),
            orientation=Orientation(deg=0.0),
            outline=CTX.outline,
            regulation=Regulation(min_areas=(), min_width=1.0),
        )
        plan = Plan(
            rooms=(),
            walls=(Wall(id="p1", a=(0.0, 1.0), b=(3.0, 1.0), load_bearing=True),),
            openings=(),
            outline=CTX.outline,
        )
        proof = verify_exactly(plan, ctx)
        assert proof.structure_kept is False
