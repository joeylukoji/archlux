"""Command line (``archlux.cli``, PLAN.md 5.2)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from archlux import Plan, Room
from archlux.cli import main

OUTLINE = ((0.0, 0.0), (6.0, 0.0), (6.0, 4.0), (0.0, 4.0))
VALID = Plan(
    rooms=(
        Room(id="a", type="living_room", x=0.0, y=0.0, w=3.0, h=4.0),
        Room(id="b", type="bedroom", x=3.0, y=0.0, w=3.0, h=4.0),
    ),
    walls=(),
    openings=(),
    outline=OUTLINE,
)
# Overlap of 0.5 m: invalid, repairable without moving the outline.
OVERLAPPING = Plan(
    rooms=(
        Room(id="a", type="living_room", x=0.0, y=0.0, w=3.5, h=4.0),
        Room(id="b", type="bedroom", x=3.0, y=0.0, w=3.0, h=4.0),
    ),
    walls=(),
    openings=(),
    outline=OUTLINE,
)


def _write(plan: Plan, tmp_path: Path) -> str:
    path = tmp_path / "plan.json"
    plan.to_json(path)
    return str(path)


def test_verify_exits_zero_on_a_valid_plan(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["verify", _write(VALID, tmp_path), "--min-width", "0.9"]) == 0
    assert "valid" in capsys.readouterr().out


def test_verify_exits_one_and_names_the_overlap(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["verify", _write(OVERLAPPING, tmp_path), "--min-width", "0.9"]) == 1
    assert "overlap" in capsys.readouterr().out


def test_legalize_writes_a_valid_plan_and_its_svg(tmp_path: Path) -> None:
    out, svg = tmp_path / "fixed.json", tmp_path / "fixed.svg"
    argv = ["legalize", _write(OVERLAPPING, tmp_path), "--min-width", "0.9", "--tiling"]
    assert main([*argv, "-o", str(out), "--svg", str(svg), "--report"]) == 0
    assert main(["verify", str(out), "--min-width", "0.9"]) == 0
    assert svg.read_text(encoding="utf-8").lstrip().startswith("<")


def test_min_area_is_read_as_type_equals_square_metres(tmp_path: Path) -> None:
    # The bedroom has 12 m²; 20 m² cannot be met inside the outline without the room.
    assert main(["verify", _write(VALID, tmp_path), "--min-area", "bedroom=20"]) == 1


def test_a_library_error_is_a_message_and_exit_two(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    broken = tmp_path / "broken.json"
    broken.write_text(json.dumps({"schema": 2, "rooms": "nope"}), encoding="utf-8")
    assert main(["verify", str(broken)]) == 2
    assert "error" in capsys.readouterr().err


def test_feasible_answers_yes_for_a_valid_program(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["feasible", _write(VALID, tmp_path), "--min-width", "0.9"]) == 0
    assert "feasible" in capsys.readouterr().out
