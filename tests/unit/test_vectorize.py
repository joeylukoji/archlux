"""``archlux.types.vectorize``: the plain plan-to-vector conversion (PLAN.md phase 4,
block 2).

Distinct from :func:`archlux.geom.polytope.vectorize`, which orders its output by a
solver-specific index: this one has no index, just ``plan.rooms`` order, so a caller
that only wants a numeric encoding does not need to reach into ``geom``.
"""

from __future__ import annotations

import numpy as np

from archlux.light.tokens import plan_to_vector
from archlux.types import FIELDS_VECTOR, Plan, Room, vectorize


def _plan(*rooms: Room) -> Plan:
    return Plan(rooms=rooms, outline=((0.0, 0.0), (12.0, 0.0), (12.0, 9.0), (0.0, 9.0)))


def test_fields_vector_is_pinned() -> None:
    assert FIELDS_VECTOR == ("x", "y", "w", "h")


def test_vectorize_flattens_in_room_order() -> None:
    plan = _plan(
        Room(id="a", type="living_room", x=0.0, y=0.5, w=6.0, h=9.0),
        Room(id="b", type="bedroom", x=6.0, y=0.0, w=5.5, h=8.0),
    )
    expected = [getattr(room, f) for room in plan.rooms for f in FIELDS_VECTOR]
    np.testing.assert_array_equal(vectorize(plan), expected)


def test_vectorize_shape_matches_fields_vector_times_rooms() -> None:
    plan = _plan(Room(id="a", type="living_room", x=1.0, y=2.0, w=3.0, h=4.0))
    assert vectorize(plan).shape == (len(FIELDS_VECTOR) * len(plan.rooms),)


def test_light_plan_to_vector_delegates_to_the_shared_one() -> None:
    """``light`` may not import ``geom``, but it may import ``types`` (PLAN.md phase 4,
    block 2: the duplicated inline computation is gone)."""
    plan = _plan(Room(id="a", type="living_room", x=1.0, y=2.0, w=3.0, h=4.0))
    np.testing.assert_array_equal(plan_to_vector(plan), vectorize(plan))
