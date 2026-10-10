"""``Plan.from_ifc`` and ``Structure.from_ifc`` (PLAN.md 5.1, optional IFC reading).

The models are built with the ``ifcopenshell`` API in millimetres, the unit of most BIM
programs, so each test states the convention it checks.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import numpy as np
import pytest

ifcopenshell = pytest.importorskip("ifcopenshell")
api = pytest.importorskip("ifcopenshell.api")

import archlux as ax  # noqa: E402 - after the skip: the module needs ifcopenshell
from archlux.errors import InvalidInput, UnsupportedInput  # noqa: E402


class _Model:
    """A one-building IFC model in millimetres, storeys created on demand."""

    def __init__(self) -> None:
        self.f = api.run("project.create_file")
        project = api.run("root.create_entity", self.f, ifc_class="IfcProject", name="p")
        mm = api.run("unit.add_si_unit", self.f, unit_type="LENGTHUNIT", prefix="MILLI")
        api.run("unit.assign_unit", self.f, units=[mm])
        model = api.run("context.add_context", self.f, context_type="Model")
        self.body = api.run(
            "context.add_context",
            self.f,
            context_type="Model",
            context_identifier="Body",
            target_view="MODEL_VIEW",
            parent=model,
        )
        plan = api.run("context.add_context", self.f, context_type="Plan")
        self.axis_ctx = api.run(
            "context.add_context",
            self.f,
            context_type="Plan",
            context_identifier="Axis",
            target_view="GRAPH_VIEW",
            parent=plan,
        )
        site = api.run("root.create_entity", self.f, ifc_class="IfcSite")
        self.building = api.run("root.create_entity", self.f, ifc_class="IfcBuilding")
        api.run("aggregate.assign_object", self.f, relating_object=project, products=[site])
        api.run("aggregate.assign_object", self.f, relating_object=site, products=[self.building])
        self.storeys: dict[str, Any] = {}

    def storey(self, name: str) -> Any:
        if name not in self.storeys:
            storey = api.run("root.create_entity", self.f, ifc_class="IfcBuildingStorey", name=name)
            api.run(
                "aggregate.assign_object", self.f, relating_object=self.building, products=[storey]
            )
            self.storeys[name] = storey
        return self.storeys[name]

    def _place(self, product: Any, x: float, y: float) -> None:
        matrix = np.eye(4)
        matrix[0][3], matrix[1][3] = x, y
        api.run(
            "geometry.edit_object_placement", self.f, product=product, matrix=matrix, is_si=False
        )

    def space(
        self,
        name: str,
        label: str | None,
        x: float,
        y: float,
        w: float,
        h: float,
        *,
        storey: str = "Ground",
        direction: tuple[float, float] = (1.0, 0.0),
    ) -> Any:
        """A space extruded from a w x h rectangle whose corner is at (x, y), in mm."""
        space = api.run("root.create_entity", self.f, ifc_class="IfcSpace", name=name)
        space.LongName = label
        api.run(
            "aggregate.assign_object", self.f, relating_object=self.storey(storey), products=[space]
        )
        self._place(space, x, y)
        centre = self.f.createIfcAxis2Placement2D(
            self.f.createIfcCartesianPoint((w / 2, h / 2)), self.f.createIfcDirection(direction)
        )
        profile = self.f.createIfcRectangleProfileDef("AREA", None, centre, w, h)
        rep = api.run(
            "geometry.add_profile_representation",
            self.f,
            context=self.body,
            profile=profile,
            depth=2.5,
        )
        api.run("geometry.assign_representation", self.f, product=space, representation=rep)
        return space

    def wall(
        self,
        name: str,
        a: tuple[float, float] | None,
        b: tuple[float, float] | None,
        *,
        load_bearing: bool,
        storey: str = "Ground",
    ) -> None:
        wall = api.run("root.create_entity", self.f, ifc_class="IfcWall", name=name)
        api.run(
            "spatial.assign_container",
            self.f,
            relating_structure=self.storey(storey),
            products=[wall],
        )
        if a is not None and b is not None:
            line = self.f.createIfcPolyline(
                [self.f.createIfcCartesianPoint(a), self.f.createIfcCartesianPoint(b)]
            )
            rep = self.f.createIfcShapeRepresentation(self.axis_ctx, "Axis", "Curve2D", [line])
            api.run("geometry.assign_representation", self.f, product=wall, representation=rep)
        pset = api.run("pset.add_pset", self.f, product=wall, name="Pset_WallCommon")
        api.run("pset.edit_pset", self.f, pset=pset, properties={"LoadBearing": load_bearing})

    def column(self, x: float, y: float) -> None:
        column = api.run("root.create_entity", self.f, ifc_class="IfcColumn", name="C1")
        api.run(
            "spatial.assign_container",
            self.f,
            relating_structure=self.storey("Ground"),
            products=[column],
        )
        self._place(column, x, y)

    def save(self, tmp_path: Path) -> Path:
        path = tmp_path / "model.ifc"
        self.f.write(str(path))
        return path


def _flat(model: _Model) -> _Model:
    """A living room and a bedroom split by a load-bearing wall at x = 5 m."""
    model.space("101", "Living room", 0, 0, 5000, 4000)
    model.space("102", "Bedroom", 5000, 0, 3000, 4000)
    model.wall("W1", (5000.0, 0.0), (5000.0, 4000.0), load_bearing=True)
    model.wall("P1", (0.0, 2000.0), (2000.0, 2000.0), load_bearing=False)
    return model


def test_spaces_are_read_in_metres_with_their_name_and_type(tmp_path: Path) -> None:
    plan = ax.Plan.from_ifc(_flat(_Model()).save(tmp_path))
    assert [(r.id, r.type, r.x, r.y, r.w, r.h) for r in plan.rooms] == [
        ("101", "living_room", 0.0, 0.0, 5.0, 4.0),
        ("102", "bedroom", 5.0, 0.0, 3.0, 4.0),
    ]
    assert [(w.id, w.a, w.b, w.load_bearing) for w in plan.walls] == [
        ("W1", (5.0, 0.0), (5.0, 4.0), True),
        ("P1", (0.0, 2.0), (2.0, 2.0), False),
    ]
    assert plan.outline == ((0.0, 0.0), (8.0, 0.0), (8.0, 4.0), (0.0, 4.0))


def test_the_structure_reads_load_bearing_walls_and_columns(tmp_path: Path) -> None:
    model = _flat(_Model())
    model.column(2500, 1000)
    structure = ax.Structure.from_ifc(model.save(tmp_path))
    assert [w.id for w in structure.load_bearing_walls] == ["W1"]
    assert structure.columns == ((2.5, 1.0),)


def test_an_exported_plan_reads_back_with_its_structure(tmp_path: Path) -> None:
    plan = ax.Plan.from_ifc(_flat(_Model()).save(tmp_path))
    plan.to_ifc(tmp_path / "again.ifc")
    again = ax.Plan.from_ifc(tmp_path / "again.ifc")
    assert again.rooms == plan.rooms
    assert [(w.id, w.a, w.b, w.load_bearing) for w in again.walls] == [
        (w.id, w.a, w.b, w.load_bearing) for w in plan.walls
    ]


def test_an_imported_plan_legalizes(tmp_path: Path) -> None:
    path = _flat(_Model()).save(tmp_path)
    plan, structure = ax.Plan.from_ifc(path), ax.Structure.from_ifc(path)
    ctx = ax.Context(
        structure, ax.Orientation(0.0), ax.preset("fr/new-collective-housing").regulation
    )
    fixed = ax.legalize(plan, ctx)
    assert fixed.certificate is not None and fixed.certificate.geometry.valid


def test_several_storeys_need_one_named(tmp_path: Path) -> None:
    model = _flat(_Model())
    model.space("201", "Bedroom", 0, 0, 4000, 4000, storey="First")
    path = model.save(tmp_path)
    with pytest.raises(InvalidInput, match="several storeys"):
        ax.Plan.from_ifc(path)
    assert [r.id for r in ax.Plan.from_ifc(path, storey="First").rooms] == ["201"]
    assert len(ax.Plan.from_ifc(path, storey="Ground").rooms) == 2
    with pytest.raises(InvalidInput, match="no space on storey 'Attic'"):
        ax.Plan.from_ifc(path, storey="Attic")


def test_an_unlabelled_space_needs_a_default_type(tmp_path: Path) -> None:
    model = _Model()
    model.space("101", None, 0, 0, 4000, 3000)
    path = model.save(tmp_path)
    with pytest.raises(InvalidInput, match="no LongName or ObjectType"):
        ax.Plan.from_ifc(path)
    assert ax.Plan.from_ifc(path, default_type="kitchen").rooms[0].type == "kitchen"


def test_duplicate_names_fall_back_to_type_numbering(tmp_path: Path) -> None:
    model = _Model()
    model.space("A", "Bedroom", 0, 0, 3000, 3000)
    model.space("A", "Bedroom", 3000, 0, 3000, 3000)
    assert [r.id for r in ax.Plan.from_ifc(model.save(tmp_path)).rooms] == [
        "bedroom-1",
        "bedroom-2",
    ]


def test_a_rotated_space_is_refused(tmp_path: Path) -> None:
    model = _Model()
    model.space("101", "Bedroom", 0, 0, 4000, 3000, direction=(1.0, 1.0))
    with pytest.raises(UnsupportedInput, match="axis-aligned rectangle"):
        ax.Plan.from_ifc(model.save(tmp_path))


def test_a_space_without_a_readable_footprint_is_refused(tmp_path: Path) -> None:
    model = _Model()
    space = api.run("root.create_entity", model.f, ifc_class="IfcSpace", name="101")
    space.LongName = "Bedroom"
    api.run(
        "aggregate.assign_object", model.f, relating_object=model.storey("Ground"), products=[space]
    )
    with pytest.raises(UnsupportedInput, match="no footprint"):
        ax.Plan.from_ifc(model.save(tmp_path))


def test_a_wall_without_an_axis_is_skipped_unless_load_bearing(tmp_path: Path) -> None:
    model = _Model()
    model.space("101", "Bedroom", 0, 0, 4000, 3000)
    model.wall("P1", None, None, load_bearing=False)
    path = model.save(tmp_path)
    assert ax.Plan.from_ifc(path).walls == ()
    model.wall("W1", None, None, load_bearing=True)
    with pytest.raises(UnsupportedInput, match="without an Axis"):
        ax.Plan.from_ifc(model.save(tmp_path))


def test_a_file_that_is_not_ifc_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "plan.ifc"
    path.write_text("not a model", encoding="utf-8")
    with pytest.raises(InvalidInput, match="not a readable IFC file"):
        ax.Plan.from_ifc(path)


def test_without_ifcopenshell_the_error_says_how_to_install_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = importlib.util.find_spec
    monkeypatch.setattr(
        importlib.util,
        "find_spec",
        lambda name, *a: None if name == "ifcopenshell" else real(name, *a),
    )
    with pytest.raises(UnsupportedInput, match=r"archlux\[bim\]"):
        ax.Plan.from_ifc(tmp_path / "plan.ifc")
