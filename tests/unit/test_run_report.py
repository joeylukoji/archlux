"""Failure taxonomy and run report (``certify.run``): every attempt leaves a record."""

from __future__ import annotations

import json
from dataclasses import replace

import numpy as np
import pytest

import archlux
from archlux.certify.run import (
    NO_CERTIFIED_SOLUTION,
    RunReport,
    classify_failure,
    run_repair,
    tally,
)
from archlux.errors import (
    InconsistentOrder,
    Infeasible,
    InvalidInput,
    InvariantViolation,
    UnsupportedInput,
)
from archlux.light.analytic import AnalyticSurrogate
from archlux.types import Context, Orientation, Plan, Regulation, Room, Structure, Wall

OUTLINE = ((0.0, 0.0), (4.0, 0.0), (4.0, 3.0), (0.0, 3.0))
CTX = Context(
    structure=Structure(load_bearing_walls=()),
    orientation=Orientation(deg=0.0),
    regulation=Regulation(min_areas=(), min_width=1.0),
    outline=OUTLINE,
)
# Room b overlaps a by 0.3 m: legalize must move it.
NOISY = Plan(
    rooms=(
        Room(id="a", type="bedroom", x=0.0, y=0.0, w=2.3, h=3.0),
        Room(id="b", type="bedroom", x=2.0, y=0.0, w=2.0, h=3.0),
    ),
    outline=OUTLINE,
)


class _Clock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        self.t += 0.25
        return self.t


def _raising(error: BaseException):  # type: ignore[no-untyped-def]
    def legalize(plan, ctx, **options):  # type: ignore[no-untyped-def]
        raise error

    return legalize


class TestClassification:
    @pytest.mark.parametrize(
        ("error", "expected"),
        [
            (Infeasible(farkas_certificate=None, origins=("area a",), verified=True), "infeasible"),
            (InvalidInput("rooms[0].w", "must be positive"), "rejected"),
            (InconsistentOrder(("a", "b"), "x"), "rejected"),
            (UnsupportedInput("oblique load-bearing wall"), "rejected"),
            (InvariantViolation(("overlap a|b",)), "computation_failure"),
            (FloatingPointError("overflow"), "computation_failure"),
        ],
    )
    def test_each_failure_has_its_outcome(self, error: BaseException, expected: str) -> None:
        status, reason = classify_failure(error)
        assert status == expected
        assert reason.startswith(NO_CERTIFIED_SOLUTION)

    def test_infeasibility_states_its_scope(self) -> None:
        _, reason = classify_failure(
            Infeasible(farkas_certificate=None, origins=(), verified=False)
        )
        assert "proposed relative order" in reason and "NOT verified" in reason


class TestRunRepair:
    def test_a_repair_is_recorded(self) -> None:
        report = run_repair(NOISY, CTX, legalize=archlux.legalize, plan_id="p1", clock=_Clock())
        assert report.status == "repaired" and report.certified
        assert report.certificate_status == "exact"
        assert not report.initial.valid
        assert report.final is not None and report.final.valid
        assert report.max_displacement_m == pytest.approx(0.3)
        assert report.elapsed_s == pytest.approx(0.25)
        assert report.reason.startswith("independent validator accepts")

    def test_a_traced_run_records_iterations_and_bound(self) -> None:
        report = run_repair(
            NOISY,
            CTX,
            legalize=archlux.legalize_trace,
            plan_id="p1",
            objective=AnalyticSurrogate(),
        )
        assert report.status == "repaired"
        assert report.iterations is not None and report.iterations >= 0
        assert report.stop_status is not None
        if report.stop_status != "converged":
            assert any("not a certified stationary point" in w for w in report.warnings)

    @pytest.mark.parametrize(
        ("error", "expected"),
        [
            (Infeasible(farkas_certificate=None, origins=(), verified=True), "infeasible"),
            (InvalidInput("plan", "bad"), "rejected"),
            (InvariantViolation(("x",)), "computation_failure"),
        ],
    )
    def test_a_failure_is_recorded_not_raised(self, error: BaseException, expected: str) -> None:
        report = run_repair(NOISY, CTX, legalize=_raising(error), plan_id="p2")
        assert report.status == expected
        assert report.final is None
        assert report.certificate_status == "none"
        assert report.error_type == type(error).__name__

    def test_a_programming_error_propagates(self) -> None:
        with pytest.raises(TypeError):
            run_repair(NOISY, CTX, legalize=_raising(TypeError("bug")), plan_id="p3")

    def test_a_real_infeasibility(self) -> None:
        ctx = replace(CTX, regulation=Regulation(min_areas=(("bedroom", 7.0),), min_width=1.0))
        report = run_repair(NOISY, ctx, legalize=archlux.legalize, plan_id="p4")
        assert report.status == "infeasible"

    def test_a_lying_solver_is_not_certified(self) -> None:
        """A plan the solver certified but the validator refuses: no certified solution."""
        certified = archlux.legalize(NOISY, CTX)

        def lying(plan, ctx, **options):  # type: ignore[no-untyped-def]
            broken = replace(certified.rooms[1], x=certified.rooms[1].x - 0.5)
            return replace(certified, rooms=(certified.rooms[0], broken))

        report = run_repair(NOISY, CTX, legalize=lying, plan_id="p5")
        assert report.status == "computation_failure"
        assert report.reason.startswith(NO_CERTIFIED_SOLUTION)
        assert "rooms.no_overlap" in report.reason
        assert any("disagrees" in w for w in report.warnings)
        assert report.certificate_status == "none"

    def test_a_budget_is_rechecked_independently(self) -> None:
        def ignores_budget(plan, ctx, **options):  # type: ignore[no-untyped-def]
            return archlux.legalize(plan, ctx)  # drops the budget on the floor

        report = run_repair(NOISY, CTX, legalize=ignores_budget, plan_id="p6", budget=0.1)
        assert report.status == "computation_failure"
        assert "displacement.budget" in report.reason

    def test_a_wrong_surrogate_cannot_certify_an_invalid_plan(self) -> None:
        class Adversarial(AnalyticSurrogate):
            def gradient(self, x, orientation, *, glazing=None):  # type: ignore[no-untyped-def]
                return 1e6 * np.ones(len(x))

        wall = Wall(id="lb", a=(2.0, 0.0), b=(2.0, 3.0), load_bearing=True)
        ctx = replace(CTX, structure=Structure(load_bearing_walls=(wall,)))
        report = run_repair(
            NOISY, ctx, legalize=archlux.legalize, plan_id="p7", objective=Adversarial()
        )
        if report.status == "repaired":
            assert report.final is not None and report.final.valid
        else:
            assert report.certificate_status == "none"


class TestSerializationAndTally:
    def test_json_round_trip(self) -> None:
        for legalize in (archlux.legalize, _raising(InvariantViolation(("x",)))):
            report = run_repair(NOISY, CTX, legalize=legalize, plan_id="p", budget=1.0)
            again = RunReport.from_json(report.to_json())
            assert again == report
            assert json.loads(report.to_json())["certificate_status"] == report.certificate_status

    def test_a_tampered_status_is_refused(self) -> None:
        data = run_repair(NOISY, CTX, legalize=archlux.legalize, plan_id="p").to_dict()
        data["certificate_status"] = "exact" if data["certificate_status"] != "exact" else "none"
        with pytest.raises(ValueError, match="disagrees"):
            RunReport.from_dict(data)
        data = run_repair(NOISY, CTX, legalize=archlux.legalize, plan_id="p").to_dict()
        data["status"] = "perfect"
        with pytest.raises(ValueError):
            RunReport.from_dict(data)

    def test_tally_counts_every_input(self) -> None:
        reports = [
            run_repair(NOISY, CTX, legalize=archlux.legalize, plan_id="ok"),
            run_repair(NOISY, CTX, legalize=_raising(InvalidInput("p", "bad")), plan_id="bad"),
        ]
        counts = tally(reports)
        assert counts == {
            "n_inputs": 2,
            "repaired": 1,
            "rejected": 1,
            "infeasible": 0,
            "computation_failure": 0,
        }
