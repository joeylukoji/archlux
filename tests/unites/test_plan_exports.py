"""``Plan.to_dxf`` / ``to_ifc`` / ``to_svg`` accept ``str`` and ``Path`` (PLAN.md 3.11).

Before, ``to_dxf(plan, "a.dxf")`` failed with ``'str' object has no attribute
'write_text'`` (AUDIT.md §8, step 6), and the exports were free functions in a package
the public API did not expose.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from archlux import Piece, Plan
from archlux.erreurs import InvariantViolation
from archlux.export import to_dxf

SQUARE = ((0.0, 0.0), (12.0, 0.0), (12.0, 9.0), (0.0, 9.0))


def sound_plan() -> Plan:
    return Plan(
        pieces=(
            Piece(id="a", type="sejour", x=0.0, y=0.0, w=6.0, h=9.0),
            Piece(id="b", type="sejour", x=6.0, y=0.0, w=6.0, h=9.0),
        ),
        murs=(),
        ouvertures=(),
        contour=SQUARE,
    )


def overlapping_plan() -> Plan:
    return Plan(
        pieces=(
            Piece(id="a", type="sejour", x=0.0, y=0.0, w=8.0, h=9.0),
            Piece(id="b", type="sejour", x=6.0, y=0.0, w=6.0, h=9.0),
        ),
        murs=(),
        ouvertures=(),
        contour=SQUARE,
    )


@pytest.mark.parametrize("as_text", [True, False])
def test_to_dxf_accepts_str_and_path(tmp_path: Path, as_text: bool) -> None:
    target = tmp_path / "plan.dxf"
    sound_plan().to_dxf(str(target) if as_text else target)
    assert "LWPOLYLINE" in target.read_text(encoding="utf-8")


def test_the_free_function_accepts_a_str_too(tmp_path: Path) -> None:
    target = tmp_path / "plan.dxf"
    to_dxf(sound_plan(), str(target))
    assert target.exists()


@pytest.mark.parametrize("as_text", [True, False])
def test_to_ifc_accepts_str_and_path(tmp_path: Path, as_text: bool) -> None:
    target = tmp_path / "plan.ifc"
    report = sound_plan().to_ifc(str(target) if as_text else target)
    assert report.valide
    assert target.exists()


def test_to_ifc_reports_a_pathological_plan_without_writing(tmp_path: Path) -> None:
    target = tmp_path / "bad.ifc"
    report = overlapping_plan().to_ifc(target)
    assert not report.valide
    assert not target.exists()


@pytest.mark.parametrize("as_text", [True, False])
def test_to_svg_accepts_str_and_path(tmp_path: Path, as_text: bool) -> None:
    target = tmp_path / "plan.svg"
    sound_plan().to_svg(str(target) if as_text else target, titre="essai")
    assert target.read_text(encoding="utf-8").startswith("<svg")


def test_to_svg_draws_an_invalid_plan(tmp_path: Path) -> None:
    """The drawing is the diagnostic tool: it must work on a plan that is not valid."""
    target = tmp_path / "bad.svg"
    overlapping_plan().to_svg(target)
    assert target.exists()


def test_to_dxf_still_refuses_a_pathological_plan(tmp_path: Path) -> None:
    with pytest.raises(InvariantViolation):
        overlapping_plan().to_dxf(tmp_path / "bad.dxf")
