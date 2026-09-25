"""IFC files read by a real IFC toolkit (PLAN.md phase 2, J6).

``to_ifc(validate=True)`` used to mean "our own pathology check passed": no IFC reader
ever opened the files. ifcopenshell's schema and rule validator rejected every one of
them (hexadecimal GlobalIds, a ``ChangeAction`` without date, 3D points in ``Curve2D``,
openings voiding nothing) and walls were drawn shifted by their first end. These tests
open the files with ifcopenshell when it is installed (``dev`` and ``bim`` extras).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from hypothesis import given, settings

from archlux.export import diagnostiquer, to_ifc
from archlux.types import Mur, Ouverture, Piece, Plan
from tests.proprietes.strategies import CONTEXTE_DEFAUT, plans_valides

_GUID = re.compile(r"^[0-3][0-9A-Za-z_$]{21}$")


def _plan() -> Plan:
    walls = (
        Mur(id="south", a=(0.0, 0.0), b=(12.0, 0.0), porteur=True),
        Mur(id="mid", a=(6.0, 0.0), b=(6.0, 9.0), porteur=True),
    )
    return Plan(
        pieces=(
            Piece(id="a", type="sejour", x=0.0, y=0.0, w=6.0, h=9.0),
            Piece(id="b", type="chambre", x=6.0, y=0.0, w=6.0, h=9.0),
        ),
        murs=walls,
        ouvertures=(Ouverture(id="w1", mur_id="south", s=0.3, largeur_rel=0.2),),
        contour=CONTEXTE_DEFAUT.contour,
    )


def test_every_global_id_is_ifc_base64_and_unique(tmp_path: Path) -> None:
    to_ifc(_plan(), tmp_path / "plan.ifc", validate=True)
    ids = re.findall(r"^#\d+=IFC\w+\('([^']*)'", (tmp_path / "plan.ifc").read_text(), re.M)
    assert ids and all(_GUID.match(i) for i in ids), ids
    assert len(ids) == len(set(ids))


def test_an_opening_on_an_unknown_wall_is_refused(tmp_path: Path) -> None:
    orphan = Ouverture(id="w9", mur_id="nowhere", s=0.5, largeur_rel=0.2)
    plan = Plan(_plan().pieces, _plan().murs, (orphan,), _plan().contour)
    assert "ouverture_orpheline:w9" in diagnostiquer(plan).pathologies
    assert not to_ifc(plan, tmp_path / "plan.ifc", validate=True).valide


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


@given(plan=plans_valides())
@settings(max_examples=20, deadline=None)
def test_ifcopenshell_accepts_every_exported_plan(
    plan: Plan, tmp_path_factory: pytest.TempPathFactory
) -> None:
    path = tmp_path_factory.mktemp("ifc") / "plan.ifc"
    assert to_ifc(plan, path, validate=True).valide
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
