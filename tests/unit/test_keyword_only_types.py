"""Model types are keyword-only where positions are easy to swap, with light defaults.

PLAN.md 3.6. ``Room("a", "living_room", 0, 0, 6, 9)`` swapped ``x, y, w, h`` without error;
``Plan`` needed ``murs=()`` and ``ouvertures=()`` even for a plan without walls; and the
outline had to be given twice, in the ``Plan`` and in the ``Context``.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from archlux import (
    Context,
    InvalidInput,
    Opening,
    Orientation,
    Plan,
    Regulation,
    Room,
    Structure,
    Wall,
    legalize,
)

SQUARE = ((0.0, 0.0), (12.0, 0.0), (12.0, 9.0), (0.0, 9.0))


def rooms() -> tuple[Room, ...]:
    return (
        Room(id="a", type="living_room", x=0.0, y=0.0, w=6.0, h=9.0),
        Room(id="b", type="living_room", x=6.0, y=0.0, w=6.0, h=9.0),
    )


def test_piece_refuses_positional_arguments() -> None:
    with pytest.raises(TypeError):
        Room("a", "living_room", 0.0, 0.0, 6.0, 9.0)  # type: ignore[misc]


def test_wall_refuses_positional_arguments() -> None:
    with pytest.raises(TypeError):
        Wall("m", (0.0, 0.0), (1.0, 0.0))  # type: ignore[misc]


def test_opening_refuses_positional_arguments() -> None:
    with pytest.raises(TypeError):
        Opening("o", "m", 0.5, 0.2)  # type: ignore[misc]


def test_a_plan_needs_only_its_rooms() -> None:
    plan = Plan(rooms=rooms())
    assert plan.walls == ()
    assert plan.openings == ()
    assert plan.outline == ()
    assert plan.certificate is None


def test_the_plan_keeps_its_positional_order() -> None:
    """Only the three types above became keyword-only: existing ``Plan(...)`` calls hold."""
    plan = Plan(rooms(), (), (), SQUARE)
    assert plan.outline == SQUARE


def context(**changes: object) -> Context:
    base = Context(
        structure=Structure(load_bearing_walls=()),
        orientation=Orientation(deg=0.0),
        regulation=Regulation(min_areas=(), min_width=1.0),
    )
    return replace(base, **changes)  # type: ignore[arg-type]


def test_the_context_outline_defaults_to_empty() -> None:
    assert context().outline == ()


def test_legalize_reads_the_outline_from_the_plan() -> None:
    legal = legalize(Plan(rooms=rooms(), outline=SQUARE), context())
    assert legal.outline == SQUARE
    assert legal.certificate is not None
    assert legal.certificate.geometry.valid


def test_legalize_reads_the_outline_from_the_context() -> None:
    legal = legalize(Plan(rooms=rooms()), context(outline=SQUARE))
    assert legal.outline == SQUARE
    assert legal.certificate is not None
    assert legal.certificate.geometry.valid


def test_the_context_outline_wins_when_both_are_given() -> None:
    other = ((0.0, 0.0), (12.0, 0.0), (12.0, 9.0), (0.0, 9.0), (0.0, 9.0))
    legal = legalize(Plan(rooms=rooms(), outline=other), context(outline=SQUARE))
    assert legal.outline == SQUARE


def test_no_outline_anywhere_is_refused_with_the_fix() -> None:
    with pytest.raises(InvalidInput, match=r"Context.outline") as raised:
        legalize(Plan(rooms=rooms()), context())
    assert raised.value.field == "outline"


def test_a_two_point_outline_is_still_refused() -> None:
    with pytest.raises(InvalidInput) as raised:
        legalize(Plan(rooms=rooms(), outline=((0.0, 0.0), (1.0, 0.0))), context())
    assert raised.value.field == "outline"
