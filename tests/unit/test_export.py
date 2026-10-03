"""IFC / DXF export and survival rate: `MILESTONE-6.md` §4."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from hypothesis import given, settings

from archlux.errors import InvariantViolation
from archlux.export import diagnose, survival_rate, to_dxf, to_ifc
from archlux.export.wilson import wilson_interval
from archlux.types import Plan, Room, Wall
from tests.properties.strategies import DEFAULT_CONTEXT, valid_plans


def _sound_plan() -> Plan:
    return Plan(
        rooms=(
            Room(id="a", type="living_room", x=0.0, y=0.0, w=6.0, h=9.0),
            Room(id="b", type="bedroom", x=6.0, y=0.0, w=6.0, h=9.0),
        ),
        walls=(Wall(id="m1", a=(0.0, 0.0), b=(12.0, 0.0), load_bearing=True),),
        openings=(),
        outline=DEFAULT_CONTEXT.outline,
    )


def _pathological_plan() -> Plan:
    return Plan(
        rooms=(
            Room(id="a", type="living_room", x=0.0, y=0.0, w=7.0, h=9.0),
            Room(id="b", type="bedroom", x=6.0, y=0.0, w=6.0, h=9.0),
        ),
        walls=(Wall(id="nul", a=(1.0, 1.0), b=(1.0, 1.0), load_bearing=False),),
        openings=(),
        outline=DEFAULT_CONTEXT.outline,
    )


@given(plan=valid_plans())
@settings(max_examples=40, deadline=None)
def test_valid_export(plan: Plan) -> None:
    """`MILESTONE-6.md` §4: to_ifc on valid_plans stays valid."""
    assert diagnose(plan).exportable
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "plan.ifc"
        export_report = to_ifc(plan, path, validate=True)
        assert export_report.valid
        assert path.is_file()
        text = path.read_text(encoding="utf-8")
        assert "ISO-10303-21" in text
        assert "IFCSPACE" in text


def test_survival_rate_with_wilson() -> None:
    """`MILESTONE-6.md` §4: 0 ≤ lo ≤ rate ≤ hi ≤ 1."""
    plans = [_sound_plan(), _sound_plan(), _pathological_plan()]
    rate, (lo, hi) = survival_rate(plans)
    assert 0.0 <= lo <= rate <= hi <= 1.0
    assert rate == pytest.approx(2.0 / 3.0)


def test_wilson_at_the_extremes() -> None:
    """Wilson stays in [0, 1] for 0/n and n/n."""
    lo, hi = wilson_interval(0, 10)
    assert 0.0 <= lo <= hi <= 1.0
    lo, hi = wilson_interval(10, 10)
    assert 0.0 <= lo <= hi <= 1.0


def test_to_ifc_refuses_pathological(tmp_path: Path) -> None:
    path = tmp_path / "bad.ifc"
    export_report = to_ifc(_pathological_plan(), path, validate=True)
    assert not export_report.valid
    assert not path.exists()
    assert export_report.engine == "refuse"


def test_to_dxf_writes_lwpolyline(tmp_path: Path) -> None:
    path = tmp_path / "plan.dxf"
    to_dxf(_sound_plan(), path)
    text = path.read_text(encoding="utf-8")
    assert "LWPOLYLINE" in text
    assert "EOF" in text


def test_to_dxf_raises_on_pathology(tmp_path: Path) -> None:
    with pytest.raises(InvariantViolation):
        to_dxf(_pathological_plan(), tmp_path / "x.dxf")


def test_zero_edge_pathology() -> None:
    diag = diagnose(_pathological_plan())
    assert any(p.startswith("arete_nulle:") for p in diag.pathologies)
    assert any(p.startswith("chevauchement:") for p in diag.pathologies)
