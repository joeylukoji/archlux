"""The position of an opening is **derived**, never stored.

The expected end points are literals computed by hand on walls chosen so that the
geometry can be checked mentally (10 m horizontal wall, 3-4-5 triangle).
"""

from __future__ import annotations

import pytest

from archlux.errors import InvariantViolation
from archlux.types import Opening, Wall

SOUTH_WALL = Wall(id="m_sud", a=(0.0, 0.0), b=(10.0, 0.0))
OBLIQUE_WALL = Wall(id="m_obl", a=(0.0, 0.0), b=(3.0, 4.0))  # length 5

OPENING = Opening(id="f1", wall_id="m_sud", s=0.5, relative_width=0.2)


def test_opening_centered_on_a_horizontal_wall() -> None:
    """10 m wall, centered 20 % opening: from 4 m to 6 m."""
    start, end = OPENING.absolute_segment(SOUTH_WALL)
    assert start == pytest.approx((4.0, 0.0))
    assert end == pytest.approx((6.0, 0.0))


def test_opening_on_an_oblique_wall() -> None:
    """3-4-5 wall (length 5), centered 20 % opening: length 1, centered at (1.5, 2)."""
    opening = Opening(id="f2", wall_id="m_obl", s=0.5, relative_width=0.2)
    start, end = opening.absolute_segment(OBLIQUE_WALL)
    assert start == pytest.approx((1.2, 1.6))
    assert end == pytest.approx((1.8, 2.4))


def test_the_opening_follows_the_wall_when_the_solver_moves_it() -> None:
    """**The reason for the invariant.**

    The same ``Opening``, unchanged, returns a different position as soon as its wall
    moves. That is exactly what a stored absolute coordinate would not do: it would stay
    in place and desynchronize the window from its partition.
    """
    moved_wall = Wall(id="m_sud", a=(0.0, 3.0), b=(10.0, 3.0))
    start, end = OPENING.absolute_segment(moved_wall)
    assert start == pytest.approx((4.0, 3.0))
    assert end == pytest.approx((6.0, 3.0))


def test_a_foreign_wall_is_refused() -> None:
    """Deriving an opening on another wall than its own is a bug, not an edge case."""
    with pytest.raises(InvariantViolation) as capture:
        OPENING.absolute_segment(OBLIQUE_WALL)
    assert "m_sud" in str(capture.value)
