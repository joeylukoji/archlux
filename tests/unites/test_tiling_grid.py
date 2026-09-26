"""Recovery of the tiling grid from a nearly valid plan (``legalize(..., pavage=True)``).

The faulty cases come from the guarantee benchmark (``benchmarks/guarantees``), modes
``classic_noisy`` and ``partial_one_fault``. They are written out as literals so that
the test does not depend on the generator. Inputs the grid cannot describe are refused
with a typed input error, never with ``InvariantViolation`` (reserved for internal bugs).
"""

from __future__ import annotations

from dataclasses import replace

import pytest

import archlux
from archlux.errors import UnsupportedInput
from archlux.geom.pavage import deduce_grid
from archlux.types import Context, Orientation, Plan, Regulation, Room, Structure, Wall
from tests import checkers

WIDTH = 11.0
HEIGHT = 7.8
OUTLINE = ((0.0, 0.0), (WIDTH, 0.0), (WIDTH, HEIGHT), (0.0, HEIGHT))


def _context(outline: tuple[tuple[float, float], ...] = OUTLINE) -> Context:
    return Context(
        structure=Structure(load_bearing_walls=()),
        orientation=Orientation(deg=0.0),
        outline=outline,
        regulation=Regulation(min_areas=(), min_width=1.0),
    )


def _plan(*rooms: Room, outline: tuple[tuple[float, float], ...] = OUTLINE) -> Plan:
    return Plan(rooms=rooms, walls=(), openings=(), outline=outline)


def _room(name: str, left: float, bottom: float, right: float, top: float) -> Room:
    return Room(id=name, type="living_room", x=left, y=bottom, w=right - left, h=top - bottom)


# Two right edges fall a few millimetres on each side of the outline edge at x = 11:
# grouped with it, they must not pull the outer grid line off the outline.
NOISY_RIGHT_EDGE = _plan(
    _room("a", 0.0, 0.0, 5.5, HEIGHT),
    _room("b", 5.5, 0.0, 10.9957, 3.9),
    _room("c", 5.5, 3.9, 11.0035, HEIGHT),
)


def test_tiling_legalization_of_a_noisy_edge_keeps_every_guarantee() -> None:
    result = archlux.legalize(NOISY_RIGHT_EDGE, _context(), pavage=True)
    assert result.certificate is not None
    assert result.certificate.geometry.valid
    assert checkers.violations(result, _context()) == []


def test_a_room_overlapping_a_neighbour_on_both_axes_keeps_the_grid_relation() -> None:
    """Benchmark mode ``partial_one_fault``: ``r4`` is moved 25 cm left, onto ``r7``.

    The two rooms then overlap on both axes, and their centres alone would put ``r4``
    *below* ``r7``. The recovered grid knows better: ``r4`` is to the right of ``r7``.
    The partial load-bearing wall pins the line between ``r6`` and ``r7``, so the wrong
    relation cannot be absorbed by collapsing a grid line.
    """
    outline = ((0.0, 0.0), (13.3, 0.0), (13.3, 10.4), (0.0, 10.4))
    wall = Wall(id="refend", a=(0.0, 2.6), b=(3.2, 2.6), load_bearing=True)
    kinds = {
        "r0": "living_room",
        "r1": "corridor",
        "r2": "bedroom",
        "r3": "bathroom",
        "r4": "corridor",
        "r5": "bedroom",
        "r6": "toilet",
        "r7": "bedroom",
    }
    edges = {
        "r0": (11.1, 3.6, 13.3, 10.4),
        "r1": (3.2, 3.6, 5.5, 10.4),
        "r2": (5.5, 3.6, 11.1, 8.4),
        "r3": (5.5, 8.4, 11.1, 10.4),
        "r4": (2.95, 0.0, 5.85, 3.6),
        "r5": (6.1, 0.0, 13.3, 3.6),
        "r6": (0.0, 0.0, 3.2, 2.6),
        "r7": (0.0, 2.6, 3.2, 10.4),
    }
    rooms = tuple(replace(_room(name, *edges[name]), type=kind) for name, kind in kinds.items())
    plan = Plan(rooms=rooms, walls=(wall,), openings=(), outline=outline)
    ctx = replace(
        _context(outline),
        structure=Structure(load_bearing_walls=(wall,)),
        regulation=Regulation(
            min_areas=(
                ("bedroom", 20.5806),
                ("corridor", 8.6082),
                ("bathroom", 9.2349),
                ("living_room", 12.3352),
                ("toilet", 6.8602),
            ),
            min_width=1.0,
        ),
    )
    result = archlux.legalize(plan, ctx, pavage=True)
    assert checkers.violations(result, ctx) == []
    by_id = {room.id: room for room in result.rooms}
    assert by_id["r4"].x == pytest.approx(by_id["r7"].x + by_id["r7"].w)


def test_outer_grid_lines_lie_exactly_on_the_outline() -> None:
    grid = deduce_grid(NOISY_RIGHT_EDGE, _context())
    assert grid.x_lines[0] == 0.0
    assert grid.x_lines[-1] == WIDTH
    assert grid.y_lines[0] == 0.0
    assert grid.y_lines[-1] == HEIGHT


STEPPED_OUTLINE = (
    (0.0, 0.0),
    (WIDTH, 0.0),
    (WIDTH, 3.0),
    (WIDTH + 0.004, 3.0),
    (WIDTH + 0.004, HEIGHT),
    (0.0, HEIGHT),
)

INPUT_LIMITS = {
    "empty plan": (_plan(), _context()),
    "empty outline": (_plan(_room("a", 0.0, 0.0, WIDTH, HEIGHT), outline=()), _context(())),
    # Every room and the outline are flat in y: fewer than two grid lines.
    "flat grid": (
        _plan(_room("a", 0.0, 0.0, WIDTH, 0.0), outline=((0.0, 0.0), (WIDTH, 0.0))),
        _context(((0.0, 0.0), (WIDTH, 0.0))),
    ),
    # A room thinner than the grouping tolerance collapses onto one grid line.
    "flat room": (
        _plan(_room("a", 0.0, 0.0, WIDTH, HEIGHT), _room("sliver", 0.0, 0.0, 0.005, HEIGHT)),
        _context(),
    ),
    # A self-intersecting outline has no inside: the partition cannot be checked.
    "invalid outline": (
        _plan(
            _room("a", 0.0, 0.0, WIDTH, HEIGHT),
            outline=((0.0, 0.0), (WIDTH, HEIGHT), (WIDTH, 0.0), (0.0, HEIGHT)),
        ),
        _context(((0.0, 0.0), (WIDTH, HEIGHT), (WIDTH, 0.0), (0.0, HEIGHT))),
    ),
    # A 4 mm step in the outline: both outline edges fall on one grid line, which
    # cannot lie exactly on both.
    "outline step below tolerance": (
        _plan(_room("a", 0.0, 0.0, WIDTH, HEIGHT), outline=STEPPED_OUTLINE),
        _context(STEPPED_OUTLINE),
    ),
}


@pytest.mark.parametrize("case", sorted(INPUT_LIMITS))
def test_an_input_the_grid_cannot_describe_is_a_typed_refusal(case: str) -> None:
    plan, ctx = INPUT_LIMITS[case]
    with pytest.raises(UnsupportedInput):
        deduce_grid(plan, ctx)
