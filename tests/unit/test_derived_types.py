"""Derived properties of the model and error boundaries.

Completes the slices of milestone 1: these public members were implemented but never
run by a test, which the coverage measurement revealed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from archlux.errors import (
    InconsistentOrder,
    Infeasible,
    InvariantViolation,
    MissingSeparation,
)
from archlux.types import Certificate, GeometricProof, Opening, Plan, Room, Wall

LIVING_ROOM = Room(id="living_room", type="living_room", x=1.0, y=2.0, w=4.0, h=3.0)


class TestRoom:
    """Derived quantities of a room."""

    def test_area(self) -> None:
        """4 m x 3 m = 12 m²."""
        assert LIVING_ROOM.area == 12.0

    def test_center(self) -> None:
        """Bottom-left corner at (1, 2), hence center at (3, 3.5)."""
        assert LIVING_ROOM.center == (3.0, 3.5)


class TestPlan:
    """Determinism of the model."""

    def test_the_ids_are_sorted(self) -> None:
        """The iteration order is explicit, never that of a ``set``.

        A non-deterministic order produces polytopes whose rows change from one run to
        the next, hence dual prices that cannot be compared.
        """
        plan = Plan(
            rooms=(
                Room(id="toilet", type="toilet", x=0.0, y=0.0, w=1.0, h=1.0),
                Room(id="kitchen", type="kitchen", x=0.0, y=0.0, w=1.0, h=1.0),
                Room(id="bath", type="bathroom", x=0.0, y=0.0, w=1.0, h=1.0),
            ),
            walls=(),
            openings=(),
            outline=(),
        )
        assert plan.room_ids == ("bath", "kitchen", "toilet")


class TestDegenerateOpening:
    """Edge cases of deriving an opening."""

    def test_a_zero_length_wall_is_refused(self) -> None:
        """An undefined direction must raise, never return silent ``NaN``."""
        wall = Wall(id="m", a=(2.0, 2.0), b=(2.0, 2.0))
        opening = Opening(id="f", wall_id="m", s=0.5, relative_width=0.5)
        with pytest.raises(InvariantViolation, match="zero length"):
            opening.absolute_segment(wall)


class TestCertificate:
    """The certificate delegates its rendering, it does not reimplement it."""

    def test_report_delegates_to_certify(self) -> None:
        """The delegation produces the two-kind template, without a composite score."""
        certificate = Certificate(
            geometry=GeometricProof(
                valid=True,
                overlap=False,
                gaps=False,
                areas_ok=True,
                structure_kept=True,
                max_displacement=0.0,
            )
        )
        text = certificate.report()
        assert "[EXACT]" in text
        assert "[PREDICTION" in text
        assert "NOT EVALUABLE" in text


class TestExceptions:
    """Public exceptions carry their diagnostic, not only a message."""

    def test_inconsistent_order_exposes_the_cycle(self) -> None:
        """The cycle is usable by the caller, not only readable."""
        error = InconsistentOrder(cycle=("a", "b", "a"), axis="horizontal")
        assert error.cycle == ("a", "b", "a")
        assert "a -> b -> a" in str(error)

    def test_missing_separation_exposes_the_pair(self) -> None:
        """The unseparated pair is the one to fix."""
        error = MissingSeparation(pair=("kitchen", "bathroom"))
        assert error.pair == ("kitchen", "bathroom")

    def test_infeasible_carries_its_proof(self) -> None:
        """An infeasibility without a certificate teaches nobody anything."""
        error = Infeasible(farkas_certificate=[1.0, 0.0], origins=("load-bearing wall axis 3",))
        assert error.farkas_certificate == [1.0, 0.0]
        assert "load-bearing wall axis 3" in str(error)

    def test_infeasible_without_origins_says_so(self) -> None:
        """The message does not claim a diagnostic it does not have."""
        assert "no constraint identified" in str(Infeasible(farkas_certificate=None))


class TestRobustWriting:
    """Writing boundary: no untyped exception comes out of it."""

    def test_a_nan_raises_a_typed_exception(self, tmp_path: Path) -> None:
        """``NaN`` is exactly what a buggy solver produces.

        Letting it surface as a raw ``ValueError`` would break `ARCHITECTURE.md` §7 and
        take an internal fault outside the error domain of the project.
        """
        plan = Plan(
            rooms=(Room(id="a", type="living_room", x=float("nan"), y=0.0, w=1.0, h=1.0),),
            walls=(),
            openings=(),
            outline=(),
        )
        with pytest.raises(InvariantViolation, match="non-finite"):
            plan.to_json(tmp_path / "x.json")
