"""IFC files read by a real IFC toolkit (PLAN.md phase 2, J6).

``to_ifc(validate=True)`` used to mean "our own pathology check passed": no IFC reader
ever opened the files. ifcopenshell's schema and rule validator rejected every one of
them (hexadecimal GlobalIds, a ``ChangeAction`` without date, 3D points in ``Curve2D``,
openings voiding nothing) and walls were drawn shifted by their first end. These tests
open the files with ifcopenshell when it is installed (``dev`` and ``bim`` extras).
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest
from hypothesis import given, settings

from archlux import __version__, legalize
from archlux.export import diagnose, to_ifc
from archlux.types import Opening, Plan, Room, Wall
from tests.properties.strategies import DEFAULT_CONTEXT, valid_plans

_GUID = re.compile(r"^[0-3][0-9A-Za-z_$]{21}$")


def _plan() -> Plan:
    walls = (
        Wall(id="south", a=(0.0, 0.0), b=(12.0, 0.0), load_bearing=True),
        Wall(id="mid", a=(6.0, 0.0), b=(6.0, 9.0), load_bearing=True),
    )
    return Plan(
        rooms=(
            Room(id="a", type="living_room", x=0.0, y=0.0, w=6.0, h=9.0),
            Room(id="b", type="bedroom", x=6.0, y=0.0, w=6.0, h=9.0),
        ),
        walls=walls,
        openings=(Opening(id="w1", wall_id="south", s=0.3, relative_width=0.2),),
        outline=DEFAULT_CONTEXT.outline,
    )


def test_every_global_id_is_ifc_base64_and_unique(tmp_path: Path) -> None:
    to_ifc(_plan(), tmp_path / "plan.ifc", validate=True)
    ids = re.findall(r"^#\d+=IFC\w+\('([^']*)'", (tmp_path / "plan.ifc").read_text(), re.M)
    assert ids and all(_GUID.match(i) for i in ids), ids
    assert len(ids) == len(set(ids))


def test_an_opening_on_an_unknown_wall_is_refused(tmp_path: Path) -> None:
    orphan = Opening(id="w9", wall_id="nowhere", s=0.5, relative_width=0.2)
    plan = Plan(_plan().rooms, _plan().walls, (orphan,), _plan().outline)
    assert "ouverture_orpheline:w9" in diagnose(plan).pathologies
    assert not to_ifc(plan, tmp_path / "plan.ifc", validate=True).valid


def _errors(path: Path, *, rules: bool = True) -> list[str]:
    """Validator messages; ``rules=False`` checks the schema only (0.02 s, not 2.8 s)."""
    ifcopenshell = pytest.importorskip("ifcopenshell")
    validate = pytest.importorskip("ifcopenshell.validate")
    logger = validate.json_logger()
    validate.validate(ifcopenshell.open(str(path)), logger, express_rules=rules)
    return [str(statement["message"]).splitlines()[0] for statement in logger.statements]


def test_ifcopenshell_accepts_a_plan_with_walls_and_an_opening(tmp_path: Path) -> None:
    to_ifc(_plan(), tmp_path / "plan.ifc", validate=True)
    assert _errors(tmp_path / "plan.ifc") == []


@given(plan=valid_plans())
@settings(max_examples=20, deadline=None)
def test_ifcopenshell_accepts_every_exported_plan(
    plan: Plan, tmp_path_factory: pytest.TempPathFactory
) -> None:
    path = tmp_path_factory.mktemp("ifc") / "plan.ifc"
    assert to_ifc(plan, path, validate=True).valid
    assert _errors(path, rules=False) == []


def test_walls_are_drawn_where_they_are(tmp_path: Path) -> None:
    """The wall axis sits at its coordinates, not shifted by its first end."""
    ifcopenshell = pytest.importorskip("ifcopenshell")
    placement = pytest.importorskip("ifcopenshell.util.placement")
    to_ifc(_plan(), tmp_path / "plan.ifc", validate=True)
    model = ifcopenshell.open(str(tmp_path / "plan.ifc"))
    drawn = {}
    for wall in model.by_type("IfcWall"):
        matrix = placement.get_local_placement(wall.ObjectPlacement)
        points = wall.Representation.Representations[0].Items[0].Points
        drawn[wall.Name] = [
            (round(p.Coordinates[0] + matrix[0][3], 6), round(p.Coordinates[1] + matrix[1][3], 6))
            for p in points
        ]
    assert drawn == {"south": [(0.0, 0.0), (12.0, 0.0)], "mid": [(6.0, 0.0), (6.0, 9.0)]}


def test_two_different_plans_share_no_global_id(tmp_path: Path) -> None:
    """Review of phase 2, Major 1: labels alone gave two flats the same IfcSpace ids."""
    first = _plan()
    second = Plan(
        rooms=(
            Room(id="a", type="kitchen", x=0.0, y=0.0, w=5.0, h=9.0),
            Room(id="b", type="bedroom", x=5.0, y=0.0, w=7.0, h=9.0),
        ),
        walls=first.walls,
        openings=first.openings,
        outline=first.outline,
    )
    ids = []
    for k, plan in enumerate((first, second, first)):
        to_ifc(plan, tmp_path / f"{k}.ifc", validate=True)
        text = (tmp_path / f"{k}.ifc").read_text()
        ids.append(set(re.findall(r"^#\d+=IFC\w+\('([^']*)'", text, re.M)))
    assert not ids[0] & ids[1]
    assert ids[0] == ids[2]  # deterministic for one plan


def test_the_global_ids_do_not_depend_on_class_or_field_names(tmp_path: Path) -> None:
    """Review of the stack (#6): the salt hashed ``repr`` of the dataclasses, so the English
    rename changed every GlobalId of the same plan. Pinned: change it only on purpose."""
    to_ifc(_plan(), tmp_path / "plan.ifc", validate=True)
    project = re.search(r"IFCPROJECT\('([^']*)'", (tmp_path / "plan.ifc").read_text())
    assert project is not None
    assert project.group(1) == "0Iie9ISb$ViPPopaAp6Tto"


_GOLDEN_SHA256 = "230697e34fe521d96ed76cdc5188ac4dd2aaa2f543785d2bf90595d0364e913d"
"""SHA-256 of the golden export below, package version replaced by ``<version>``."""


def test_the_export_of_a_certified_plan_is_byte_identical(tmp_path: Path) -> None:
    """Golden file (review of PLAN.md phase 4, block 13): the IFC writer split must not
    change one byte. Walls, an opening and a certificate annex cover every emission block.

    The writer has no timestamp; the only environment-dependent content is the package
    version (``IFCAPPLICATION`` and the certificate text), normalized before hashing so a
    release does not break the pin. Change the constant only on purpose.
    """
    plan = legalize(_plan(), DEFAULT_CONTEXT)
    assert plan.certificate is not None and plan.openings
    assert to_ifc(plan, tmp_path / "plan.ifc", validate=True).valid
    data = (tmp_path / "plan.ifc").read_bytes().replace(__version__.encode(), b"<version>")
    assert hashlib.sha256(data).hexdigest() == _GOLDEN_SHA256
