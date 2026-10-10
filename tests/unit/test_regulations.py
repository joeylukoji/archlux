"""Regulation presets (PLAN.md 5.4): sourced thresholds, and what they leave unchecked."""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

import archlux as ax
from archlux.cli import main
from archlux.errors import InvalidInput
from archlux.regulations import PRESETS

FR = "fr/new-collective-housing"


def test_the_french_preset_holds_the_sourced_thresholds() -> None:
    regulation = ax.preset(FR).regulation
    assert regulation.min_area("living_room") == 9.0
    assert regulation.min_area("bedroom") == 7.0
    assert regulation.min_area("kitchen") == 0.0  # no area rule for service rooms
    assert regulation.min_width == 0.90


@pytest.mark.parametrize("name", sorted(PRESETS))
def test_every_threshold_has_a_source(name: str) -> None:
    """One source per regulated type and one for the width, each with a link."""
    found = ax.preset(name)
    rules = " ".join(source.rule for source in found.sources)
    for room_type, _ in found.regulation.min_areas:
        assert room_type in rules
    assert "min_width" in rules
    assert all(source.url.startswith("https://") and source.provision for source in found.sources)
    assert found.not_checked, "a preset must say what the model cannot check"
    assert found.name == name


def test_an_unknown_preset_names_the_known_ones() -> None:
    with pytest.raises(InvalidInput, match=FR):
        ax.preset("fr/maison")


def test_a_plan_legalized_under_the_preset_meets_it() -> None:
    plan = _plan()
    ctx = ax.Context(
        ax.Structure(()), ax.Orientation(0.0), ax.preset(FR).regulation, outline=plan.outline
    )
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # both types are regulated: no "unregulated" warning
        fixed = ax.legalize(plan, ctx)
    areas = {room.type: room.w * room.h for room in fixed.rooms}
    assert areas["living_room"] >= 9.0 - 1e-9 and areas["bedroom"] >= 7.0 - 1e-9


def _plan() -> ax.Plan:
    """A 7.5 m2 living room and a 10.5 m2 bedroom, both 3 m deep."""
    return ax.Plan(
        rooms=(
            ax.Room(id="living", type="living_room", x=0.0, y=0.0, w=2.5, h=3.0),
            ax.Room(id="bed", type="bedroom", x=2.5, y=0.0, w=3.5, h=3.0),
        ),
        outline=((0.0, 0.0), (6.0, 0.0), (6.0, 3.0), (0.0, 3.0)),
    )


def _plan_file(tmp_path: Path) -> str:
    path = tmp_path / "plan.json"
    _plan().to_json(path)
    return str(path)


def test_the_command_line_applies_a_preset(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _plan_file(tmp_path)
    assert main(["verify", path, "--preset", FR]) == 1  # living room 7.5 m2 < 9 m2
    assert "area living: 7.5000 m² < 9.0000 m²" in capsys.readouterr().out
    assert main(["verify", path, "--preset", FR, "--min-area", "living_room=7"]) == 0


def test_without_a_preset_the_command_line_keeps_its_default_width(tmp_path: Path) -> None:
    path = _plan_file(tmp_path)
    assert main(["verify", path]) == 0  # 2.5 m >= the default 1.80 m
    assert main(["verify", path, "--preset", FR, "--min-width", "2.6"]) == 1
