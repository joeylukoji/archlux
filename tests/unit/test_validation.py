"""Independent validator: one hand-computed case per constraint, plus degenerate inputs.

The expected values are geometry computed by hand, never the output of the solver or of
``verify_exactly``: the validator must stand on its own.
"""

from __future__ import annotations

import json
import math
from dataclasses import replace

import pytest

from archlux.certify.validation import (
    NOT_COVERED,
    ValidationReport,
    linear_constraint,
    plan_fingerprint,
    validate_plan,
)
from archlux.geom.rectilinear import RectilinearRoom
from archlux.types import Context, Opening, Orientation, Plan, Regulation, Room, Structure, Wall

OUTLINE = ((0.0, 0.0), (4.0, 0.0), (4.0, 3.0), (0.0, 3.0))


def _ctx(
    *,
    outline: tuple[tuple[float, float], ...] = OUTLINE,
    walls: tuple[Wall, ...] = (),
    min_areas: tuple[tuple[str, float], ...] = (),
    min_width: float = 1.0,
) -> Context:
    return Context(
        structure=Structure(load_bearing_walls=walls),
        orientation=Orientation(deg=0.0),
        regulation=Regulation(min_areas=min_areas, min_width=min_width),
        outline=outline,
    )


def _room(rid: str, x: float, y: float, w: float, h: float, kind: str = "bedroom") -> Room:
    return Room(id=rid, type=kind, x=x, y=y, w=w, h=h)


TWO = (_room("a", 0.0, 0.0, 2.0, 3.0), _room("b", 2.0, 0.0, 2.0, 3.0))


def _status(report: ValidationReport, cid: str) -> str:
    return report.result(cid).status


class TestVerdict:
    def test_a_valid_tiling_is_valid_and_exact(self) -> None:
        report = validate_plan(Plan(rooms=TWO), _ctx())
        assert report.valid
        assert report.evidence == "exact"
        assert not report.violated and not report.unknown

    def test_scope_never_claims_building_code_or_fire_safety(self) -> None:
        report = validate_plan(Plan(rooms=TWO), _ctx())
        assert report.scope == NOT_COVERED
        for topic in ("building code compliance", "accessibility", "fire safety"):
            assert topic in report.scope
        assert "Not established" in report.summary()

    def test_a_disconnected_plan_is_a_soft_violation(self) -> None:
        # Two rooms touching at a corner only: the soft rule is reported, labelled soft.
        rooms = (_room("a", 0.0, 0.0, 2.0, 1.5), _room("b", 2.0, 1.5, 2.0, 1.5))
        report = validate_plan(Plan(rooms=rooms), _ctx())
        assert _status(report, "rooms.connected") == "violated"
        assert report.result("rooms.connected").spec.kind == "soft"

    def test_unknown_hard_constraint_refuses_validity(self) -> None:
        report = validate_plan(Plan(rooms=TWO), _ctx(), budget=0.5)  # no reference
        assert _status(report, "displacement.budget") == "unknown"
        assert not report.valid
        assert report.evidence == "refused"


class TestRooms:
    def test_overlap_measured_exactly(self) -> None:
        rooms = (_room("a", 0.0, 0.0, 2.5, 3.0), _room("b", 2.0, 0.0, 2.0, 3.0))
        result = validate_plan(Plan(rooms=rooms), _ctx()).result("rooms.no_overlap")
        assert result.status == "violated"
        assert result.measure == pytest.approx(1.5)  # 0.5 x 3
        assert "a|b" in result.reason

    def test_gap_and_overhang_are_separate(self) -> None:
        # Room b slid 0.5 m to the right: 1.5 m2 uncovered inside, 1.5 m2 outside.
        rooms = (_room("a", 0.0, 0.0, 2.0, 3.0), _room("b", 2.5, 0.0, 2.0, 3.0))
        report = validate_plan(Plan(rooms=rooms), _ctx())
        assert report.result("outline.covered").measure == pytest.approx(1.5)
        assert report.result("outline.contains_rooms").measure == pytest.approx(1.5)
        assert not report.valid

    def test_min_area(self) -> None:
        report = validate_plan(Plan(rooms=TWO), _ctx(min_areas=(("bedroom", 6.5),)))
        result = report.result("rooms.min_area")
        assert result.status == "violated"
        assert result.measure == pytest.approx(-0.5)

    def test_min_width(self) -> None:
        rooms = (_room("a", 0.0, 0.0, 0.5, 3.0), _room("b", 0.5, 0.0, 3.5, 3.0))
        result = validate_plan(Plan(rooms=rooms), _ctx()).result("rooms.min_width")
        assert result.status == "violated"
        assert result.measure == pytest.approx(-0.5)

    def test_duplicate_ids(self) -> None:
        rooms = (_room("a", 0.0, 0.0, 2.0, 3.0), _room("a", 2.0, 0.0, 2.0, 3.0))
        assert _status(validate_plan(Plan(rooms=rooms), _ctx()), "ids.unique") == "violated"

    def test_non_finite_rooms_leave_geometry_unknown(self) -> None:
        bad = Room.__new__(Room)
        for name, value in zip(
            ("id", "type", "x", "y", "w", "h"),
            ("a", "bedroom", 0.0, 0.0, math.nan, 3.0),
            strict=True,
        ):
            object.__setattr__(bad, name, value)
        report = validate_plan(Plan(rooms=(bad,)), _ctx())
        assert _status(report, "rooms.finite") == "violated"
        assert _status(report, "rooms.no_overlap") == "unknown"
        assert not report.valid


class TestDegenerateGeometry:
    def test_near_zero_room(self) -> None:
        rooms = (_room("a", 0.0, 0.0, 4.0, 3.0), _room("sliver", 4.0, 0.0, 1e-9, 3.0))
        report = validate_plan(Plan(rooms=rooms), _ctx(min_width=0.0))
        assert _status(report, "rooms.non_degenerate") == "violated"

    def test_rounding_noise_on_a_shared_edge_is_tolerated(self) -> None:
        # 0.1 + 0.2 != 0.3 in floating point; the shared edge is off by ~5.6e-17 m.
        rooms = (
            _room("a", 0.0, 0.0, 0.1 + 0.2, 3.0),
            _room("b", 0.3, 0.0, 3.7, 3.0),
        )
        report = validate_plan(Plan(rooms=rooms), _ctx(min_width=0.2))
        assert report.valid, report.summary()

    def test_tiny_overlap_beyond_tolerance_is_caught(self) -> None:
        # 1e-6 m of overlap over 3 m: 3e-6 m2 > 1e-9 m2, invisible to the eye.
        rooms = (_room("a", 0.0, 0.0, 2.0 + 1e-6, 3.0), _room("b", 2.0, 0.0, 2.0, 3.0))
        assert _status(validate_plan(Plan(rooms=rooms), _ctx()), "rooms.no_overlap") == "violated"

    def test_negative_coordinates(self) -> None:
        outline = ((-4.0, -3.0), (0.0, -3.0), (0.0, 0.0), (-4.0, 0.0))
        rooms = (_room("a", -4.0, -3.0, 2.0, 3.0), _room("b", -2.0, -3.0, 2.0, 3.0))
        report = validate_plan(Plan(rooms=rooms), _ctx(outline=outline))
        assert report.valid and report.evidence == "exact"

    def test_non_rectangular_outline_is_numeric(self) -> None:
        outline = ((0.0, 0.0), (4.0, 0.0), (4.0, 3.0), (2.0, 3.0), (2.0, 6.0), (0.0, 6.0))
        rooms = (_room("a", 0.0, 0.0, 2.0, 6.0), _room("b", 2.0, 0.0, 2.0, 3.0))
        report = validate_plan(Plan(rooms=rooms), _ctx(outline=outline))
        assert report.valid
        assert report.evidence == "numeric"
        assert report.result("outline.covered").spec.method == "geos_tolerance"

    def test_degenerate_outline_is_unknown(self) -> None:
        report = validate_plan(Plan(rooms=TWO), _ctx(outline=((0.0, 0.0), (1.0, 1.0))))
        assert _status(report, "outline.covered") == "unknown"
        assert not report.valid


class TestStructure:
    def test_crossing_measured_exactly(self) -> None:
        wall = Wall(id="lb", a=(1.0, 0.0), b=(1.0, 3.0), load_bearing=True)
        report = validate_plan(Plan(rooms=TWO), _ctx(walls=(wall,)))
        result = report.result("structure.not_crossed")
        assert result.status == "violated"
        assert result.spec.method == "exact_rational"
        assert result.measure == pytest.approx(3.0 - 2e-7)

    def test_wall_on_a_partition_is_accepted(self) -> None:
        wall = Wall(id="lb", a=(2.0, 0.0), b=(2.0, 3.0), load_bearing=True)
        assert validate_plan(Plan(rooms=TWO), _ctx(walls=(wall,))).valid

    def test_near_coincident_wall_within_tolerance(self) -> None:
        wall = Wall(id="lb", a=(2.0 + 5e-8, 0.0), b=(2.0 + 5e-8, 3.0), load_bearing=True)
        assert validate_plan(Plan(rooms=TWO), _ctx(walls=(wall,))).valid

    def test_moved_wall(self) -> None:
        wall = Wall(id="lb", a=(2.0, 0.0), b=(2.0, 3.0), load_bearing=True)
        moved = Wall(id="lb", a=(2.0, 0.0), b=(2.0, 2.0), load_bearing=True)
        report = validate_plan(Plan(rooms=TWO, walls=(moved,)), _ctx(walls=(wall,)))
        assert _status(report, "structure.not_moved") == "violated"

    def test_oblique_wall_uses_geos(self) -> None:
        wall = Wall(id="lb", a=(0.0, 0.0), b=(4.0, 3.0), load_bearing=True)
        result = validate_plan(Plan(rooms=TWO), _ctx(walls=(wall,))).result("structure.not_crossed")
        assert result.status == "violated" and result.spec.method == "geos_tolerance"

    def test_degenerate_wall(self) -> None:
        wall = Wall(id="w", a=(1.0, 1.0), b=(1.0, 1.0 + 1e-9))
        report = validate_plan(Plan(rooms=TWO, walls=(wall,)), _ctx())
        assert _status(report, "walls.non_degenerate") == "violated"


class TestOpenings:
    WALL = Wall(id="s", a=(0.0, 0.0), b=(4.0, 0.0))

    def _report(self, *openings: Opening) -> ValidationReport:
        return validate_plan(Plan(rooms=TWO, walls=(self.WALL,), openings=openings), _ctx())

    def test_valid_opening(self) -> None:
        report = self._report(Opening(id="f", wall_id="s", s=0.5, relative_width=0.25))
        assert report.valid

    def test_orphan_opening(self) -> None:
        report = self._report(Opening(id="f", wall_id="ghost", s=0.5, relative_width=0.25))
        assert _status(report, "openings.on_known_wall") == "violated"

    def test_overhanging_opening(self) -> None:
        # Centre at 0, width 1 m on a 4 m wall: 0.5 m past the end.
        result = self._report(Opening(id="f", wall_id="s", s=0.0, relative_width=0.25)).result(
            "openings.within_wall"
        )
        assert result.status == "violated"
        assert result.measure == pytest.approx(0.5)

    def test_overlapping_openings(self) -> None:
        report = self._report(
            Opening(id="f", wall_id="s", s=0.4, relative_width=0.25),
            Opening(id="g", wall_id="s", s=0.5, relative_width=0.25),
        )
        assert _status(report, "openings.disjoint") == "violated"

    def test_sill_above_head(self) -> None:
        report = self._report(
            Opening(id="f", wall_id="s", s=0.5, relative_width=0.25, sill_height=2.5)
        )
        assert _status(report, "openings.sill_below_head") == "violated"

    def test_no_opening_is_not_applicable(self) -> None:
        report = validate_plan(Plan(rooms=TWO), _ctx())
        assert ("openings.*", "the plan has no opening") in report.not_applicable


class TestBudgetAndExtra:
    def test_budget(self) -> None:
        reference = Plan(rooms=(_room("a", 0.0, 0.0, 1.5, 3.0), _room("b", 1.5, 0.0, 2.5, 3.0)))
        ok = validate_plan(Plan(rooms=TWO), _ctx(), reference=reference, budget=0.5)
        assert ok.result("displacement.budget").measure == pytest.approx(0.5)
        assert ok.valid
        tight = validate_plan(Plan(rooms=TWO), _ctx(), reference=reference, budget=0.4)
        assert _status(tight, "displacement.budget") == "violated"

    def test_extra_linear_constraint_is_checked(self) -> None:
        # A cut added during optimization: a.w >= 2.5, i.e. -a.w <= -2.5.
        cut = linear_constraint("cut.width_a", (("a", "w", -1.0),), -2.5)
        report = validate_plan(Plan(rooms=TWO), _ctx(), extra=(cut,))
        assert _status(report, "cut.width_a") == "violated"
        assert not report.valid

    def test_extra_constraint_on_a_missing_room_is_unknown(self) -> None:
        cut = linear_constraint("cut.ghost", (("ghost", "w", 1.0),), 10.0)
        assert (
            _status(validate_plan(Plan(rooms=TWO), _ctx(), extra=(cut,)), "cut.ghost") == "unknown"
        )

    def test_bad_field_is_refused(self) -> None:
        with pytest.raises(ValueError, match="unknown room fields"):
            linear_constraint("cut", (("a", "area", 1.0),), 1.0)


class TestFusedRooms:
    def test_fused_room_is_checked_as_a_whole(self) -> None:
        # An L made of a 2x3 and a 2x1.5 rectangle, minimum 8 m2: the union has 9 m2.
        parts = (
            _room("l0", 0.0, 0.0, 2.0, 3.0, "living_room"),
            _room("l1", 2.0, 0.0, 2.0, 1.5, "living_room"),
        )
        rest = _room("c", 2.0, 1.5, 2.0, 1.5)
        fused = RectilinearRoom(id="l", rectangles=parts, merges=((0, 1, "partage_bord_droit"),))
        ctx = _ctx(min_areas=(("living_room", 8.0),))
        report = validate_plan(Plan(rooms=(*parts, rest)), ctx, merges=(fused,))
        assert _status(report, "rooms.min_area") == "satisfied", report.summary()
        assert report.evidence == "numeric"


class TestFingerprintAndSerialization:
    def test_report_is_bound_to_its_plan(self) -> None:
        plan = Plan(rooms=TWO)
        report = validate_plan(plan, _ctx())
        assert report.matches(plan)
        moved = replace(plan, rooms=(replace(TWO[0], w=2.0000000001), TWO[1]))
        assert not report.matches(moved)
        assert plan_fingerprint(plan) != plan_fingerprint(moved)

    def test_round_trip_through_json(self) -> None:
        rooms = (_room("a", 0.0, 0.0, 2.5, 3.0), _room("b", 2.0, 0.0, 2.0, 3.0))
        report = validate_plan(Plan(rooms=rooms), _ctx(), budget=1.0)
        again = ValidationReport.from_dict(json.loads(json.dumps(report.to_dict())))
        assert again == report
        assert again.valid is report.valid

    def test_a_tampered_verdict_is_refused(self) -> None:
        rooms = (_room("a", 0.0, 0.0, 2.5, 3.0), _room("b", 2.0, 0.0, 2.0, 3.0))
        data = validate_plan(Plan(rooms=rooms), _ctx()).to_dict()
        data["valid"] = True
        with pytest.raises(ValueError, match="disagrees"):
            ValidationReport.from_dict(data)
