"""``Plan.from_dxf`` and ``Structure.from_dxf`` (PLAN.md 5.1).

The drawings are built with ``ezdxf`` in a temporary directory, so each test states the
convention it checks: closed rectangles on the room layer, a type label inside each.
"""

from __future__ import annotations

import importlib.util
from collections.abc import Callable
from pathlib import Path

import pytest

ezdxf = pytest.importorskip("ezdxf")

import archlux  # noqa: E402 - after the skip: the module needs ezdxf
from archlux.errors import InvalidInput, UnsupportedInput  # noqa: E402
from archlux.types import Context, Orientation, Plan, Regulation, Structure  # noqa: E402

Drawer = Callable[[object], None]


def _drawing(tmp_path: Path, draw: Drawer, *, insunits: int = 6) -> Path:
    """Write a DXF whose model space ``draw`` fills; ``insunits`` 4 is mm, 6 is m."""
    doc = ezdxf.new()
    doc.units = insunits
    draw(doc.modelspace())
    path = tmp_path / "plan.dxf"
    doc.saveas(path)
    return path


def _room(msp: object, x: float, y: float, w: float, h: float, label: str | None) -> None:
    """A closed rectangle on ``ROOMS``, its label at the center."""
    corners = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    msp.add_lwpolyline(corners, close=True, dxfattribs={"layer": "ROOMS"})  # type: ignore[attr-defined]
    if label is not None:
        msp.add_text(label, dxfattribs={"layer": "ROOMS", "insert": (x + w / 2, y + h / 2)})  # type: ignore[attr-defined]


def _t2(msp: object) -> None:
    """A two-room flat in millimetres, a load-bearing wall at x = 5 m."""
    _room(msp, 0, 0, 5000, 4000, "Living room")
    _room(msp, 5000, 0, 3000, 4000, "bedroom")
    msp.add_line((5000, 0), (5000, 4000), dxfattribs={"layer": "LOAD_BEARING"})  # type: ignore[attr-defined]


def test_rooms_are_read_in_metres_and_named_after_their_label(tmp_path: Path) -> None:
    plan = Plan.from_dxf(_drawing(tmp_path, _t2, insunits=4), load_bearing_layer="load_bearing")
    by_id = {r.id: r for r in plan.rooms}
    assert set(by_id) == {"living_room-1", "bedroom-1"}
    assert (by_id["living_room-1"].w, by_id["living_room-1"].h) == (5.0, 4.0)
    assert (by_id["bedroom-1"].x, by_id["bedroom-1"].type) == (5.0, "bedroom")
    assert plan.outline == ((0.0, 0.0), (8.0, 0.0), (8.0, 4.0), (0.0, 4.0))
    assert [(w.id, w.a, w.b, w.load_bearing) for w in plan.walls] == [
        ("load-bearing-1", (5.0, 0.0), (5.0, 4.0), True)
    ]


def test_an_imported_plan_legalizes_with_its_structure(tmp_path: Path) -> None:
    path = _drawing(tmp_path, _t2, insunits=4)
    plan, structure = Plan.from_dxf(path), Structure.from_dxf(path)
    regulation = Regulation(min_areas=(("living_room", 14.0), ("bedroom", 9.0)), min_width=0.9)
    ctx = Context(structure, Orientation(0.0), regulation, outline=plan.outline)
    fixed = archlux.legalize(plan, ctx)
    assert fixed.certificate is not None and fixed.certificate.geometry.valid


def test_rooms_of_the_same_type_are_numbered_bottom_to_top_then_left_to_right(
    tmp_path: Path,
) -> None:
    def draw(msp: object) -> None:
        _room(msp, 3, 0, 3, 3, "bedroom")
        _room(msp, 0, 3, 6, 3, "bedroom")
        _room(msp, 0, 0, 3, 3, "bedroom")

    rooms = Plan.from_dxf(_drawing(tmp_path, draw)).rooms
    assert [(r.id, r.x, r.y) for r in rooms] == [
        ("bedroom-1", 0.0, 0.0),
        ("bedroom-2", 3.0, 0.0),
        ("bedroom-3", 0.0, 3.0),
    ]


def test_an_mtext_label_and_a_label_layer_are_read(tmp_path: Path) -> None:
    def draw(msp: object) -> None:
        _room(msp, 0, 0, 4, 3, None)
        msp.add_mtext("Living\\Proom", dxfattribs={"layer": "NAMES", "insert": (2, 2)})  # type: ignore[attr-defined]

    assert (
        Plan.from_dxf(_drawing(tmp_path, draw), label_layer="NAMES").rooms[0].type == "living_room"
    )


def test_an_unlabelled_room_is_refused_unless_a_default_type_is_given(tmp_path: Path) -> None:
    path = _drawing(tmp_path, lambda msp: _room(msp, 0, 0, 4, 3, None))
    with pytest.raises(InvalidInput, match="no TEXT or MTEXT label"):
        Plan.from_dxf(path)
    assert Plan.from_dxf(path, default_type="kitchen").rooms[0].id == "kitchen-1"


def test_two_different_labels_in_a_room_are_refused(tmp_path: Path) -> None:
    def draw(msp: object) -> None:
        _room(msp, 0, 0, 4, 3, "kitchen")
        msp.add_text("bedroom", dxfattribs={"layer": "ROOMS", "insert": (1, 1)})  # type: ignore[attr-defined]

    with pytest.raises(InvalidInput, match="several labels"):
        Plan.from_dxf(_drawing(tmp_path, draw))


@pytest.mark.parametrize(
    ("points", "why"),
    [
        ([(0, 0), (4, 0), (4, 2), (2, 2), (2, 3), (0, 3)], "4 vertices"),
        ([(0, 0), (4, 3), (4, 0), (0, 3)], "axis-aligned rectangle"),
        ([(0, 0), (3, 1), (2, 4), (-1, 3)], "axis-aligned rectangle"),
        ([(0, 0), (4, 0), (4, 1e-9), (0, 1e-9)], "axis-aligned rectangle"),
    ],
    ids=["L-shape", "bowtie", "rotated", "flat"],
)
def test_a_room_that_is_not_an_axis_aligned_rectangle_is_refused(
    tmp_path: Path, points: list[tuple[float, float]], why: str
) -> None:
    def draw(msp: object) -> None:
        msp.add_lwpolyline(points, close=True, dxfattribs={"layer": "ROOMS"})  # type: ignore[attr-defined]

    with pytest.raises(UnsupportedInput, match=why):
        Plan.from_dxf(_drawing(tmp_path, draw), default_type="kitchen")


def test_an_arc_segment_is_refused(tmp_path: Path) -> None:
    def draw(msp: object) -> None:
        points = [(0, 0, 0.5), (4, 0, 0), (4, 3, 0), (0, 3, 0)]
        msp.add_lwpolyline(points, format="xyb", close=True, dxfattribs={"layer": "ROOMS"})  # type: ignore[attr-defined]

    with pytest.raises(UnsupportedInput, match="bulges"):
        Plan.from_dxf(_drawing(tmp_path, draw), default_type="kitchen")


def test_a_repeated_closing_vertex_reads_as_a_closed_room(tmp_path: Path) -> None:
    def draw(msp: object) -> None:
        points = [(0, 0), (4, 0), (4, 3), (0, 3), (0, 0)]
        msp.add_lwpolyline(points, dxfattribs={"layer": "ROOMS"})  # type: ignore[attr-defined]

    assert Plan.from_dxf(_drawing(tmp_path, draw), default_type="kitchen").rooms[0].w == 4.0


def test_no_room_on_the_layer_is_refused(tmp_path: Path) -> None:
    with pytest.raises(InvalidInput, match="no room polyline on layer 'PIECES'"):
        Plan.from_dxf(_drawing(tmp_path, _t2), "PIECES")


def test_an_outline_layer_gives_the_outline(tmp_path: Path) -> None:
    def draw(msp: object) -> None:
        _t2(msp)
        outline = [(0, 0), (9000, 0), (9000, 5000), (0, 5000)]
        msp.add_lwpolyline(outline, close=True, dxfattribs={"layer": "OUTLINE"})  # type: ignore[attr-defined]

    path = _drawing(tmp_path, draw, insunits=4)
    assert Plan.from_dxf(path, outline_layer="OUTLINE").outline[2] == (9.0, 5.0)
    with pytest.raises(InvalidInput, match="exactly one closed polyline"):
        Plan.from_dxf(path, outline_layer="ROOMS")


def test_partitions_are_read_as_non_load_bearing_walls(tmp_path: Path) -> None:
    def draw(msp: object) -> None:
        _t2(msp)
        msp.add_lwpolyline([(0, 2000), (2000, 2000), (2000, 4000)], dxfattribs={"layer": "WALLS"})  # type: ignore[attr-defined]

    walls = Plan.from_dxf(_drawing(tmp_path, draw, insunits=4), wall_layer="WALLS").walls
    assert [(w.id, w.a, w.b, w.load_bearing) for w in walls] == [
        ("wall-1", (0.0, 2.0), (2.0, 2.0), False),
        ("wall-2", (2.0, 2.0), (2.0, 4.0), False),
    ]


def test_the_structure_reads_walls_and_columns(tmp_path: Path) -> None:
    def draw(msp: object) -> None:
        _t2(msp)
        msp.add_point((2500, 2000), dxfattribs={"layer": "LOAD_BEARING"})  # type: ignore[attr-defined]
        msp.add_circle((7000, 1000), radius=150, dxfattribs={"layer": "LOAD_BEARING"})  # type: ignore[attr-defined]

    structure = Structure.from_dxf(_drawing(tmp_path, draw, insunits=4))
    assert [(w.a, w.b, w.load_bearing) for w in structure.load_bearing_walls] == [
        ((5.0, 0.0), (5.0, 4.0), True)
    ]
    assert structure.columns == ((2.5, 2.0), (7.0, 1.0))
    with pytest.raises(InvalidInput, match="no wall or column"):
        Structure.from_dxf(_drawing(tmp_path, _t2), "COLUMNS")


def test_scale_overrides_the_units_of_the_file(tmp_path: Path) -> None:
    path = _drawing(tmp_path, _t2, insunits=0)
    assert Plan.from_dxf(path).rooms[0].w == 5000.0  # unitless reads as metres
    assert Plan.from_dxf(path, scale=0.001).rooms[0].w == 5.0
    with pytest.raises(InvalidInput, match="scale"):
        Plan.from_dxf(path, scale=0.0)


def test_a_file_that_is_not_dxf_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "plan.dxf"
    path.write_text("not a drawing", encoding="utf-8")
    with pytest.raises(InvalidInput, match="not a readable DXF file"):
        Plan.from_dxf(path)
    with pytest.raises(InvalidInput, match="not a readable DXF file"):
        Plan.from_dxf(tmp_path / "missing.dxf")


def test_without_ezdxf_the_error_says_how_to_install_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = importlib.util.find_spec
    monkeypatch.setattr(
        importlib.util, "find_spec", lambda name, *a: None if name == "ezdxf" else real(name, *a)
    )
    with pytest.raises(UnsupportedInput, match=r"archlux\[cad\]"):
        Plan.from_dxf(tmp_path / "plan.dxf")


def test_the_command_line_reads_a_dxf_plan(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from archlux.cli import main

    path, out = str(_drawing(tmp_path, _t2, insunits=4)), tmp_path / "fixed.json"
    areas = ["--min-area", "living_room=14", "--min-area", "bedroom=9"]
    assert main(["legalize", path, *areas, "-o", str(out)]) == 0
    fixed = Plan.from_json(out)
    assert {w.id for w in fixed.walls if w.load_bearing} == {"load-bearing-1"}
    assert main(["verify", path, *areas]) == 0
    bad = tmp_path / "bad.dxf"
    bad.write_text("not a drawing", encoding="utf-8")
    assert main(["verify", str(bad)]) == 2
    assert "not a readable DXF file" in capsys.readouterr().err


def test_an_open_polyline_on_the_room_layer_is_refused(tmp_path: Path) -> None:
    def draw(msp: object) -> None:
        _room(msp, 0, 0, 4, 3, "kitchen")
        msp.add_lwpolyline([(4, 0), (6, 0), (6, 3), (4, 3)], dxfattribs={"layer": "ROOMS"})  # type: ignore[attr-defined]

    with pytest.raises(InvalidInput, match="open polyline"):
        Plan.from_dxf(_drawing(tmp_path, draw))


@pytest.mark.parametrize(("insunits", "width"), [(1, 0.0254), (5, 0.01), (14, 0.1)])
def test_units_convert_exactly(tmp_path: Path, insunits: int, width: float) -> None:
    path = _drawing(tmp_path, lambda msp: _room(msp, 0, 0, 1, 1, "kitchen"), insunits=insunits)
    assert Plan.from_dxf(path).rooms[0].w == width


def test_an_exotic_unit_is_refused_unless_scale_is_given(tmp_path: Path) -> None:
    path = _drawing(tmp_path, lambda msp: _room(msp, 0, 0, 1, 1, "kitchen"), insunits=18)
    with pytest.raises(InvalidInput, match=r"\$INSUNITS 18"):
        Plan.from_dxf(path)
    assert Plan.from_dxf(path, scale=2.0).rooms[0].w == 2.0
