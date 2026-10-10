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


# A 0.5 m corridor: no overlap, no gap, no area rule broken, but narrower than 0.9 m.
NARROW = Plan(
    rooms=(
        Room(id="a", type="living_room", x=0.0, y=0.0, w=5.5, h=4.0),
        Room(id="corridor", type="corridor", x=5.5, y=0.0, w=0.5, h=4.0),
    ),
    walls=(),
    openings=(),
    outline=OUTLINE,
)


def test_verify_exits_one_and_names_a_room_narrower_than_min_width(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["verify", _write(NARROW, tmp_path), "--min-width", "0.9"]) == 1
    out = capsys.readouterr().out
    assert out.startswith("invalid")
    assert "corridor" in out
    assert "0.50 m < 0.90 m" in out


def test_verify_accepts_a_room_exactly_as_wide_as_min_width(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["verify", _write(NARROW, tmp_path), "--min-width", "0.5"]) == 0
    out = capsys.readouterr().out
    assert "widths met" in out
    assert "areas and widths" not in out


COMMANDS = ["verify", "feasible", "legalize"]


@pytest.mark.parametrize("command", COMMANDS)
@pytest.mark.parametrize(
    ("options", "named"),
    [
        (["--min-width", "nan"], "--min-width"),
        (["--min-width", "inf"], "--min-width"),
        (["--min-width", "-1"], "--min-width"),
        (["--min-area", "bedroom=nan"], "--min-area"),
        (["--min-area", "bedroom=inf"], "--min-area"),
        (["--min-area", "bedroom=-1"], "--min-area"),
        (["--min-area", "=9"], "--min-area"),
        (["--min-area", "bedroom"], "--min-area"),
        (["--min-area", "bedroom=9", "--min-area", "bedroom=12"], "bedroom"),
        (["--min-area", "Bedroom=9"], "Bedroom"),
        (["--orientation", "nan"], "--orientation"),
        (["--orientation", "inf"], "--orientation"),
    ],
)
def test_a_hostile_option_is_a_message_and_exit_two(
    command: str,
    options: list[str],
    named: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main([command, _write(VALID, tmp_path), *options]) == 2
    err = capsys.readouterr().err
    assert named in err
    assert "Traceback" not in err


def test_an_unknown_room_type_lists_the_known_ones(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["verify", _write(VALID, tmp_path), "--min-area", "Bedroom=9"]) == 2
    assert "bedroom, living_room" in capsys.readouterr().err


@pytest.mark.parametrize("command", COMMANDS)
@pytest.mark.parametrize("degrees", ["-90", "360", "725.5"])
def test_any_finite_orientation_is_accepted_modulo_360(
    command: str, degrees: str, tmp_path: Path
) -> None:
    assert main([command, _write(VALID, tmp_path), "--orientation", degrees]) == 0


def test_report_says_so_when_there_is_no_certificate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    import archlux.api

    monkeypatch.setattr(archlux.api, "legalize", lambda plan, ctx, **_: plan)
    assert main(["legalize", _write(VALID, tmp_path), "--report"]) == 0
    assert "no certificate" in capsys.readouterr().out


def test_a_missing_file_is_named_plainly(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = tmp_path / "absent.json"
    assert main(["verify", str(missing)]) == 2
    err = capsys.readouterr().err
    assert f"{missing}: no such file" in err
    assert "Errno" not in err


def test_a_missing_field_is_named_with_its_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    broken = tmp_path / "broken.json"
    broken.write_text(json.dumps({"schema": "2", "rooms": []}), encoding="utf-8")
    assert main(["verify", str(broken)]) == 2
    err = capsys.readouterr().err
    assert f"{broken}: missing field 'walls'" in err
    assert "invariant violated" not in err


def test_output_may_overwrite_the_input_file(tmp_path: Path) -> None:
    path = _write(OVERLAPPING, tmp_path)
    assert main(["legalize", path, "--min-width", "0.9", "--tiling", "-o", path]) == 0
    assert main(["verify", path, "--min-width", "0.9"]) == 0


def test_output_in_a_missing_directory_is_a_message_and_exit_two(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "no" / "such" / "fixed.json"
    argv = ["legalize", _write(OVERLAPPING, tmp_path), "--min-width", "0.9", "-o", str(out)]
    assert main(argv) == 2
    err = capsys.readouterr().err
    assert f"{out}: no such file or directory" in err
    assert "Errno" not in err
