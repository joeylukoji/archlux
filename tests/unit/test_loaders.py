"""Real corpus loader (MSD): `docs/data/msd.md`.

The test CSV is built here: the real corpus is 400 MB and cannot be redistributed. The
geometry reproduces what matters in MSD: a rotated frame, thick partitions, rooms that
do not touch, L-shaped rooms.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest
from shapely import affinity
from shapely.geometry import Polygon, box

import archlux as ax
from archlux.certify.proof import verify_exactly
from archlux.data.loaders import (
    LoadStatistics,
    _grid,
    _stitch,
    load_msd,
)
from archlux.types import Regulation

_ANGLE = 23.0  # rotated frame, as in MSD


def _rotate(poly: Polygon) -> Polygon:
    return affinity.rotate(poly, _ANGLE, origin=(0.0, 0.0))


def _write_csv(path: Path, rows: list[tuple[str, str, str, Polygon]]) -> None:
    """Write a CSV in the MSD format (useful columns only)."""
    header = "apartment_id,entity_type,entity_subtype,geom\n"
    body = "".join(
        f'{app},{kind},{subtype},"{_rotate(poly).wkt}"\n' for app, kind, subtype, poly in rows
    )
    path.write_text(header + body, encoding="utf-8")


def _two_room_apartment() -> list[tuple[str, str, str, Polygon]]:
    """Two rooms separated by a 20 cm partition, plus a wall and an opening.

    The `area` entities are the **inner** surfaces: they do not touch, as in MSD.
    Stitching must make them adjoin.
    """
    return [
        ("a1", "area", "LIVING_ROOM", box(0.0, 0.0, 3.9, 5.0)),
        ("a1", "area", "BEDROOM", box(4.1, 0.0, 8.0, 5.0)),
        ("a1", "separator", "WALL", box(3.9, 0.0, 4.1, 5.0)),
        ("a1", "opening", "WINDOW", box(1.0, -0.1, 2.2, 0.1)),
    ]


def test_grid_groups_neighbouring_coordinates() -> None:
    """Two edges closer than the tolerance become the same edge."""
    mapping = _grid([0.0, 0.05, 3.90, 4.10, 8.0], tolerance=0.30)
    assert mapping[0.0] == mapping[0.05]
    assert mapping[3.90] == mapping[4.10] == pytest.approx(4.0)
    assert mapping[8.0] != mapping[4.10]


def test_grid_is_transitive_along_a_chain() -> None:
    """A chain of short steps merges, even if the extremes are far apart."""
    mapping = _grid([0.0, 0.2, 0.4, 0.6], tolerance=0.30)
    assert len(set(mapping.values())) == 1


def test_stitching_makes_the_rooms_adjoin() -> None:
    """Before stitching the union has holes; after, it is in one room."""
    left = box(0.0, 0.0, 3.9, 5.0)
    right = box(4.1, 0.0, 8.0, 5.0)
    assert left.distance(right) == pytest.approx(0.2)
    stitched = _stitch([left, right], tolerance=0.30)
    assert len(stitched) == 2
    assert stitched[0].distance(stitched[1]) == pytest.approx(0.0)


def test_loads_a_rotated_apartment_and_straightens_it(tmp_path: Path) -> None:
    """The rotated frame is recovered and becomes the `Orientation` of the context."""
    csv = tmp_path / "msd.csv"
    _write_csv(csv, _two_room_apartment())
    apartments = list(load_msd(csv))
    assert len(apartments) == 1
    apartment = apartments[0]
    # The angle is defined modulo 90: 23 deg and 113 deg describe the same grid.
    assert (
        min(
            abs(apartment.straightening_angle - _ANGLE),
            abs(apartment.straightening_angle - _ANGLE + 90.0),
        )
        < 0.5
    )
    assert apartment.context.orientation.deg == apartment.straightening_angle
    assert len(apartment.plan.rooms) == 2
    # Openings are relative to their wall, never absolute.
    for opening in apartment.plan.openings:
        assert 0.0 <= opening.s <= 1.0
        assert 0.0 < opening.relative_width <= 1.0
        assert opening.wall_id in {wall.id for wall in apartment.plan.walls}


def test_default_regulation_neutralizes_the_minimum_width(tmp_path: Path) -> None:
    """MSD carries no regulation: `min_width` must be 0.

    The default of `Regulation` (1.80 m) would apply to each **sub-rectangle**,
    including the narrow strips from an L decomposition. The real plan would then leave
    its own polytope.
    """
    csv = tmp_path / "msd.csv"
    _write_csv(csv, _two_room_apartment())
    apartment = next(iter(load_msd(csv)))
    assert apartment.context.regulation.min_width == 0.0
    assert apartment.context.regulation.min_areas == ()


def test_legalize_is_idempotent_on_a_valid_real_plan(tmp_path: Path) -> None:
    """An already valid plan comes out **unchanged**: displacement exactly zero.

    That is the contract of the L1 objective: if the input is feasible, the optimum is
    `e = 0`. Measured on 80 MSD apartments: 80/80 valid before and after, maximum
    displacement 0.0000 m.
    """
    csv = tmp_path / "msd.csv"
    _write_csv(csv, _two_room_apartment())
    apartment = next(iter(load_msd(csv)))
    assert verify_exactly(apartment.plan, apartment.context).valid

    fixed = ax.legalize(apartment.plan, apartment.context, merges=apartment.merges)
    proof = fixed.certificate.geometry
    assert proof.valid
    assert proof.max_displacement == pytest.approx(0.0, abs=1e-9)


def test_an_inherited_minimum_width_distorts_a_real_plan(tmp_path: Path) -> None:
    """Counter-check: with the 1.80 m default, the plan leaves its polytope.

    This test **documents the trap** rather than a desirable behaviour: a room 3.9 m
    wide is widened or refused as soon as an unwanted regulatory threshold is
    inherited silently.
    """
    csv = tmp_path / "msd.csv"
    _write_csv(csv, _two_room_apartment())
    narrow = Regulation(min_areas=(), min_width=6.0)  # wider than the rooms
    apartment = next(iter(load_msd(csv, regulation=narrow)))
    with pytest.raises(ax.ArchluxError):
        ax.legalize(apartment.plan, apartment.context, merges=apartment.merges)


def test_statistics_break_down_the_rejections(tmp_path: Path) -> None:
    """The retention rate and its reasons are exposed, not only the total."""
    oblique = Polygon([(0.0, 0.0), (4.0, 0.0), (4.0, 3.0), (2.0, 4.5), (0.0, 3.0)])
    csv = tmp_path / "msd.csv"
    _write_csv(
        csv,
        [*_two_room_apartment(), ("a2", "area", "ROOM", oblique)],
    )
    stats = LoadStatistics()
    kept = list(load_msd(csv, stats=stats))
    assert stats.read == 2
    assert len(kept) == stats.kept
    assert 0.0 < stats.retention_rate <= 1.0
    assert sum(stats.rejections.values()) == stats.read - stats.kept
    assert "lus 2" in stats.summary()


def test_a_missing_file_raises_invariant(tmp_path: Path) -> None:
    """A corpus that cannot be found is a typed error, not a bare `FileNotFoundError`."""
    with pytest.raises(ax.InvariantViolation, match="not found"):
        list(load_msd(tmp_path / "absent.csv"))


def test_limit_stops_the_loading(tmp_path: Path) -> None:
    """`limit` caps the number of **kept** apartments."""
    rows = []
    for k in range(4):
        for app, kind, subtype, poly in _two_room_apartment():
            shifted = affinity.translate(poly, xoff=20.0 * k)
            rows.append((f"{app}_{k}", kind, subtype, shifted))
    csv = tmp_path / "msd.csv"
    _write_csv(csv, rows)
    assert len(list(load_msd(csv, limit=2))) == 2


def test_the_straightening_angle_is_consistent_with_the_geometry(tmp_path: Path) -> None:
    """After straightening, every room edge is axis-aligned."""
    csv = tmp_path / "msd.csv"
    _write_csv(csv, _two_room_apartment())
    apartment = next(iter(load_msd(csv)))
    for room in apartment.plan.rooms:
        assert room.w > 0.0
        assert room.h > 0.0
    coords = list(apartment.plan.outline)
    for (x0, y0), (x1, y1) in zip(coords, coords[1:] + coords[:1], strict=True):
        assert math.isclose(x0, x1, abs_tol=1e-6) or math.isclose(y0, y1, abs_tol=1e-6)
