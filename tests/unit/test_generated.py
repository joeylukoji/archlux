"""Generated-plan loader (``archlux.data.generated``, PLAN.md phase 4, block 16)."""

from __future__ import annotations

import pytest

from archlux.data.generated import generated_boxes, generated_plan, generated_scale


def _record(*rooms: tuple[str, tuple[float, float, float, float]]) -> dict[str, object]:
    """A vendor JSONL record: corner coordinates of each room, in generator units."""
    pieces = [
        {"type": kind, "coins": [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]}
        for kind, (x0, y0, x1, y1) in rooms
    ]
    return {"pieces": pieces, "programme": [kind for kind, _ in rooms]}


TWO_ROOMS = _record(("living_room", (0.0, 0.0, 2.0, 2.0)), ("bedroom", (2.0, 0.0, 4.0, 2.0)))


def test_boxes_are_axis_aligned_and_scaled() -> None:
    assert generated_boxes(TWO_ROOMS, 2.0) == [
        ("living_room", (0.0, 0.0, 4.0, 4.0)),
        ("bedroom", (4.0, 0.0, 4.0, 4.0)),
    ]


def test_the_scale_matches_the_median_area() -> None:
    scale = generated_scale([TWO_ROOMS], target_area_m2=32.0)  # union area 8 units²
    assert scale == pytest.approx(2.0)


def test_a_plan_tiles_its_bounding_box() -> None:
    built = generated_plan(TWO_ROOMS, 1.0)
    assert not isinstance(built, str)
    plan, context, _diagnostic = built
    assert [room.id for room in plan.rooms] == ["p000", "p001"]
    assert plan.outline == ((0.0, 0.0), (4.0, 0.0), (4.0, 2.0), (0.0, 2.0))
    assert context.program == ("bedroom", "living_room")
    assert context.regulation.min_width == 0.50


def test_a_degenerate_room_rejects_the_record() -> None:
    thin = _record(("living_room", (0.0, 0.0, 2.0, 2.0)), ("bedroom", (2.0, 0.0, 2.01, 2.0)))
    assert generated_plan(thin, 1.0) == "degenerate room"
