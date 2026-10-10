"""The repair report for an architect (PLAN.md 5.5): room by room, in m and m²."""

from __future__ import annotations

from pathlib import Path

import pytest

import archlux as ax
from archlux.certify import RoomChange, render_repair, room_changes
from archlux.cli import main
from archlux.errors import InvalidInput

REGULATION = ax.Regulation((("living_room", 9.0), ("bedroom", 7.0)), min_width=0.9)


def _before() -> ax.Plan:
    """A 7.5 m² living room next to a 10.5 m² bedroom."""
    return ax.Plan(
        rooms=(
            ax.Room(id="living", type="living_room", x=0.0, y=0.0, w=2.5, h=3.0),
            ax.Room(id="bed", type="bedroom", x=2.5, y=0.0, w=3.5, h=3.0),
        ),
        outline=((0.0, 0.0), (6.0, 0.0), (6.0, 3.0), (0.0, 3.0)),
    )


def _after() -> ax.Plan:
    ctx = ax.Context(ax.Structure(()), ax.Orientation(0.0), REGULATION, outline=_before().outline)
    return ax.legalize(_before(), ctx)


def test_room_changes_pair_rooms_and_measure_wall_moves() -> None:
    before = _before()
    after = ax.Plan(
        rooms=(
            ax.Room(id="living", type="living_room", x=0.0, y=0.0, w=3.0, h=3.0),
            ax.Room(id="hall", type="corridor", x=3.0, y=0.0, w=1.0, h=3.0),
        )
    )
    changes = {change.id: change for change in room_changes(before, after, REGULATION)}
    assert changes["living"].moved == pytest.approx(0.5)
    assert changes["living"].margin == pytest.approx(0.0)
    assert changes["bed"].after is None and changes["bed"].margin is None
    assert changes["hall"].before is None and changes["hall"].minimum == 0.0
    assert changes["hall"].moved == 0.0
    assert isinstance(changes["hall"], RoomChange)


def test_the_report_shows_each_room_before_and_after() -> None:
    report = _after().repair_report(_before(), REGULATION)
    assert report.startswith("PLAN REPAIR")
    assert "Verdict: valid (exact check)" in report
    living = next(line for line in report.splitlines() if line.startswith("living"))
    assert "2.50 x 3.00 = 7.50 m²" in living and "= 9.00 m²" in living
    assert "+0.00 m²" in living and "0.50 m" in living
    assert "Largest wall move: 0.50 m" in report
    assert "every room is at least 0.90 m wide" in report


def test_the_report_speaks_french() -> None:
    report = render_repair(_before(), _after(), REGULATION, lang="fr")
    assert "Verdict : valide (vérification exacte)" in report
    assert "pièce" in report and "déplacé" in report
    with pytest.raises(InvalidInput, match="lang"):
        render_repair(_before(), _after(), REGULATION, lang="de")  # type: ignore[arg-type]


def test_the_report_lists_what_is_not_checked() -> None:
    fr = ax.preset("fr/new-collective-housing")
    report = _after().repair_report(_before(), fr.regulation, not_checked=fr.not_checked)
    assert all(rule in report for rule in fr.not_checked)
    assert "check the regulation in force yourself" in _after().repair_report(_before(), REGULATION)


def test_an_uncertified_or_invalid_plan_says_so() -> None:
    assert "not certified" in render_repair(_before(), _before(), REGULATION)
    after = _after()
    assert after.certificate is not None
    broken = ax.Plan(
        after.rooms,
        certificate=ax.Certificate(
            geometry=ax.GeometricProof(
                valid=False,
                overlap=True,
                gaps=False,
                areas_ok=True,
                structure_kept=True,
                max_displacement=0.0,
                violations=("overlap living|bed: 0.5 m²",),
            )
        ),
    )
    report = render_repair(_before(), broken, REGULATION)
    assert "Verdict: NOT valid" in report and "overlap living|bed" in report


def test_narrow_rooms_are_named() -> None:
    narrow = ax.Plan(rooms=(ax.Room(id="hall", type="corridor", x=0.0, y=0.0, w=0.6, h=3.0),))
    report = render_repair(narrow, narrow, REGULATION)
    assert "1 room(s) narrower than 0.90 m" in report and "hall: 0.60 m" in report


def test_the_command_line_prints_the_report_and_a_comparison(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path, svg = tmp_path / "plan.json", tmp_path / "compare.svg"
    _before().to_json(path)
    argv = ["legalize", str(path), "--preset", "fr/new-collective-housing", "--report"]
    assert main([*argv, "--lang", "fr", "--compare-svg", str(svg)]) == 0
    out = capsys.readouterr().out
    assert "CORRECTION DU PLAN" in out and "ceiling height" in out
    drawing = svg.read_text(encoding="utf-8")
    assert drawing.startswith("<svg") and "before" in drawing and "after" in drawing
