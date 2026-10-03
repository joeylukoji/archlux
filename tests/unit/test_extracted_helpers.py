"""Unit tests of the helpers extracted in PLAN.md phase 4, block 3.

``_chord_through_pivot`` and ``_line_pieces`` (``geom.rectilinear``) and
``_verify_partition`` (``geom.grid``) were split out of larger functions; these tests
pin their behaviour on their own.
"""

from __future__ import annotations

import pytest
from shapely.geometry import GeometryCollection, LineString, Point

from archlux.errors import GridNotRecoverable, UnsupportedInput
from archlux.geom.grid import _verify_partition
from archlux.geom.rectilinear import _chord_through_pivot, _line_rooms
from archlux.types import Context, Orientation, Regulation, Structure

SQUARE = ((0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0))


def _context(outline: tuple[tuple[float, float], ...] = SQUARE) -> Context:
    return Context(
        structure=Structure(load_bearing_walls=()),
        orientation=Orientation(deg=0.0),
        outline=outline,
        regulation=Regulation(min_areas=(), min_width=1.0),
    )


def test_chord_through_pivot_axis_1_joins_collinear_pieces() -> None:
    pieces = [LineString([(1.0, 0.0), (1.0, 1.0)]), LineString([(1.0, 1.0), (1.0, 3.0)])]
    assert _chord_through_pivot(pieces, Point(1.0, 1.0), axis=1) == (0.0, 3.0)


def test_chord_through_pivot_axis_0_ignores_pieces_off_the_pivot() -> None:
    pieces = [LineString([(0.0, 1.0), (2.0, 1.0)]), LineString([(5.0, 1.0), (7.0, 1.0)])]
    assert _chord_through_pivot(pieces, Point(2.0, 1.0), axis=0) == (0.0, 2.0)


def test_chord_through_pivot_none_when_nothing_touches_the_pivot() -> None:
    pieces = [LineString([(0.0, 1.0), (2.0, 1.0)])]
    assert _chord_through_pivot(pieces, Point(9.0, 9.0), axis=0) is None


def test_line_pieces_keeps_only_lines_of_a_geometry_collection() -> None:
    segment = LineString([(0.0, 0.0), (1.0, 0.0)])
    pieces = _line_rooms(GeometryCollection([Point(5.0, 5.0), segment]))
    assert len(pieces) == 1
    assert pieces[0].equals(segment)


def test_verify_partition_accepts_a_partition() -> None:
    incidences = [("a", 0, 1, 0, 1), ("b", 1, 2, 0, 1)]
    out = _verify_partition(_context(), [0.0, 1.0, 2.0], [0.0, 2.0], incidences, 0)
    assert out == incidences


def test_verify_partition_repairs_a_one_cell_gap() -> None:
    incidences = [("a", 0, 1, 0, 1)]
    out = _verify_partition(_context(), [0.0, 1.0, 2.0], [0.0, 2.0], incidences, 4)
    assert out == [("a", 0, 2, 0, 1)]


def test_verify_partition_refuses_without_budget() -> None:
    with pytest.raises(GridNotRecoverable):
        _verify_partition(_context(), [0.0, 1.0, 2.0], [0.0, 2.0], [("a", 0, 1, 0, 1)], 0)


def test_verify_partition_refuses_an_invalid_outline() -> None:
    bowtie = ((0.0, 0.0), (2.0, 2.0), (2.0, 0.0), (0.0, 2.0))
    with pytest.raises(UnsupportedInput):
        _verify_partition(_context(bowtie), [0.0, 2.0], [0.0, 2.0], [("a", 0, 1, 0, 1)], 0)
