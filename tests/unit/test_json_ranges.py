"""The ranges documented by `ARCHITECTURE.md` §6 are checked **at the boundary**.

Architecture decision (ADR-6): validation happens when reading JSON, not in the
constructors. Data coming from outside is guaranteed sound; the object in memory stays
free, so that the solver can go through intermediate states without paying for a
validation at every construction.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from archlux.errors import InvariantViolation
from archlux.io.json_io import from_dict, load, to_dict
from archlux.types import Opening, Plan, Room, Wall

PLAN = Plan(
    rooms=(Room(id="living_room", type="living_room", x=0.0, y=0.0, w=4.0, h=3.5),),
    walls=(Wall(id="m", a=(0.0, 0.0), b=(4.0, 0.0)),),
    openings=(Opening(id="f", wall_id="m", s=0.5, relative_width=0.2),),
    outline=((0.0, 0.0), (4.0, 0.0), (4.0, 3.5), (0.0, 3.5)),
)


def _with(path: list[str | int], value: object) -> dict:
    """Copy the reference plan, replacing one field with a faulty value."""
    data = to_dict(PLAN)
    target = data
    for key in path[:-1]:
        target = target[key]  # type: ignore[index]
    target[path[-1]] = value  # type: ignore[index]
    return data


class TestOpeningRanges:
    """`s ∈ [0, 1]` and `relative_width ∈ ]0, 1]`."""

    @pytest.mark.parametrize("s", [-0.01, 1.5])
    def test_abscissa_out_of_range(self, s: float) -> None:
        """An opening outside its wall has no derivable position."""
        with pytest.raises(InvariantViolation, match="s"):
            from_dict(_with(["openings", 0, "s"], s))

    @pytest.mark.parametrize("s", [0.0, 1.0])
    def test_the_bounds_are_included(self, s: float) -> None:
        """An opening at the end of a wall is legal: the interval is closed."""
        assert from_dict(_with(["openings", 0, "s"], s)).openings[0].s == s

    @pytest.mark.parametrize("width", [0.0, -0.5, 1.01])
    def test_relative_width_out_of_range(self, width: float) -> None:
        """A zero or negative width is not an opening; beyond 1, it overflows."""
        with pytest.raises(InvariantViolation, match="relative_width"):
            from_dict(_with(["openings", 0, "relative_width"], width))

    def test_a_full_width_opening_is_legal(self) -> None:
        """``relative_width = 1`` is the upper bound, included."""
        reread = from_dict(_with(["openings", 0, "relative_width"], 1.0))
        assert reread.openings[0].relative_width == 1.0


class TestRoomRanges:
    """A room has strictly positive dimensions."""

    @pytest.mark.parametrize("field", ["w", "h"])
    @pytest.mark.parametrize("value", [0.0, -2.0])
    def test_non_positive_dimension(self, field: str, value: float) -> None:
        """A room of zero or negative width would break the polytope silently."""
        with pytest.raises(InvariantViolation, match=field):
            from_dict(_with(["rooms", 0, field], value))


class TestWallRanges:
    """A wall has a strictly positive thickness."""

    def test_non_positive_thickness(self) -> None:
        """A zero thickness would make the load-bearing structure nonexistent."""
        with pytest.raises(InvariantViolation, match="thickness"):
            from_dict(_with(["walls", 0, "thickness"], 0.0))


class TestNonFiniteValues:
    """`save` refuses to write `NaN`; `load` must refuse to read it.

    ``json.loads`` accepts the ``NaN`` and ``Infinity`` literals by default. Without this
    guard, a file not written by archlux would bring ``NaN`` into the solver.
    """

    def test_nan_in_a_field(self) -> None:
        """A ``NaN`` coordinate is refused when reading."""
        with pytest.raises(InvariantViolation, match="non-finite"):
            from_dict(_with(["rooms", 0, "x"], float("nan")))

    def test_infinity_in_a_point(self) -> None:
        """So is an infinite outline vertex."""
        with pytest.raises(InvariantViolation, match="non-finite"):
            from_dict(_with(["outline", 0], [float("inf"), 0.0]))

    def test_nan_read_from_a_file(self, tmp_path: Path) -> None:
        """The real case: a file produced by another tool."""
        path = tmp_path / "nan.json"
        path.write_text(
            '{"schema": "1", "contour": [[NaN, 0.0]], "pieces": [], "murs": [],'
            ' "ouvertures": [], "certificat": null}',
            encoding="utf-8",
        )
        with pytest.raises(InvariantViolation, match="non-finite"):
            load(path)


class TestDiagnostic:
    """The refusal reports **every** violation, not only the first."""

    def test_every_violation_is_listed(self) -> None:
        """Fixing a file one error at a time is a needless ordeal."""
        data = to_dict(PLAN)
        data["rooms"][0]["w"] = -1.0
        data["openings"][0]["s"] = 3.0
        with pytest.raises(InvariantViolation) as capture:
            from_dict(data)
        message = str(capture.value)
        assert "w" in message
        assert "s" in message


def test_a_valid_plan_always_passes() -> None:
    """Validation must reject nothing legal."""
    assert from_dict(to_dict(PLAN)) == PLAN
