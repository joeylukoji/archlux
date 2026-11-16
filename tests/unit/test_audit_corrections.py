"""Corrections asked by the technical audit (Audit_technique_ArchLux): continuous gradient
measures (2.1), three-state comparison (2.2), user outcomes and B8 failure classes (2.3),
functional checks apart from the certificate (3), edge cases and determinism (4)."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

import archlux as ax
from archlux.bench.failures import classify_row, failure_table
from archlux.certify import run_repair
from archlux.certify.functional import (
    FUNCTIONAL_NOT_CHECKED,
    check_functional,
    facade_length,
    shared_wall,
)
from archlux.certify.outcome import outcome
from archlux.cli import main
from archlux.errors import InvariantViolation
from archlux.light.analytic import AnalyticSurrogate
from archlux.light.reference import ClosedFormReference
from archlux.light.split_flux import SplitFluxOracle
from archlux.light.three_states import compare_three_states, facade_glazing
from archlux.light.trust import FiniteDifferenceSurrogate, gradient_agreement
from archlux.types import Opening, Plan, Room, Wall

ORACLE = SplitFluxOracle()
OUTLINE = ((0.0, 0.0), (12.0, 0.0), (12.0, 4.5), (0.0, 4.5))


def _ctx(outline=OUTLINE, program: tuple[str, ...] = (), minima=(), width=0.5) -> ax.Context:
    return ax.Context(
        ax.Structure(()),
        ax.Orientation(0.0),
        ax.Regulation(minima, width),
        program=program,
        outline=outline,
    )


def _room(rid: str, kind: str, x: float, y: float, w: float, h: float) -> Room:
    return Room(id=rid, type=kind, x=x, y=y, w=w, h=h)


# 2.1 -------------------------------------------------------------------------------------
def test_a_perfect_gradient_has_zero_angle_and_unit_correlation() -> None:
    points = [np.array([0, 0, c, 4.5, c, 0, 12 - c, 4.5], dtype=float) for c in (5.0, 6.0, 7.0)]
    a = gradient_agreement(
        FiniteDifferenceSurrogate(ORACLE), ORACLE, points, [ax.Orientation(180.0)] * 3, step=0.10
    )
    assert a.mean_angle_deg == pytest.approx(0.0, abs=0.01)
    assert a.pearson == pytest.approx(1.0, abs=1e-6)
    assert a.median_norm_error == pytest.approx(0.0, abs=1e-3)


def test_an_opposite_gradient_has_a_180_degree_angle() -> None:
    class Opposite:
        indicator, sense = "sDA", ">="

        def evaluate(self, x, o, *, glazing=None):
            return -ORACLE.evaluate(x, o)

        def gradient(self, x, o, *, glazing=None):
            return -FiniteDifferenceSurrogate(ORACLE).gradient(x, o)

        def uncertainty(self, x, o, *, glazing=None):
            return 1.0

    x = [np.array([0, 0, 6.0, 4.5, 6.0, 0, 6.0, 4.5])]
    a = gradient_agreement(Opposite(), ORACLE, x, [ax.Orientation(180.0)])
    assert a.mean_angle_deg == pytest.approx(180.0, abs=0.01)
    assert a.sign_agreement == 0.0


# 2.2 -------------------------------------------------------------------------------------
def test_facade_glazing_puts_one_window_per_edge() -> None:
    g = facade_glazing(OUTLINE, relative_width=0.3)
    assert [w.id for w in g.walls] == ["facade0", "facade1", "facade2", "facade3"]
    assert {o.relative_width for o in g.openings} == {0.3}


def test_three_states_are_measured_by_one_labelled_reference() -> None:
    x0 = np.array([0, 0, 5.0, 4.5, 5.2, 0, 6.8, 4.5])
    x1 = np.array([0, 0, 5.0, 4.5, 5.0, 0, 7.0, 4.5])
    x2 = np.array([0, 0, 6.0, 4.5, 6.0, 0, 6.0, 4.5])
    rows = compare_three_states(
        AnalyticSurrogate(),
        ClosedFormReference(ORACLE),
        [("p", x0, x1, x2, ax.Orientation(180.0), facade_glazing(OUTLINE))],
    )
    (row,) = rows
    assert row.reference_kind == "closed_form"
    assert row.status == "closed_form_only"  # a formula never "confirms" a gain
    assert all(
        math.isfinite(v)
        for v in (
            row.reference_initial,
            row.reference_classic,
            row.reference_optimized,
            row.predicted_initial,
        )
    )


# 2.3 -------------------------------------------------------------------------------------
def _report(plan: Plan, ctx: ax.Context, **options: object):
    return run_repair(plan, ctx, legalize=ax.legalize, plan_id="p", **options)


def test_outcomes_name_the_failure_and_the_strong_deformation() -> None:
    gap = Plan(
        rooms=(_room("a", "bedroom", 0, 0, 5, 4.5), _room("b", "bedroom", 6, 0, 6, 4.5)),
        outline=OUTLINE,
    )
    failed = outcome(_report(gap, _ctx()), side_m=12.0)
    assert (failed.outcome, failed.failure_class) == ("not_repairable", "gap_needs_tiling")
    assert "tiling=True" in failed.message
    fixed = _report(gap, _ctx(), tiling=True)
    assert outcome(fixed, side_m=12.0).outcome == "repaired"
    assert outcome(fixed, side_m=1.0, strong=0.1).outcome == "repaired_strong_deformation"
    with pytest.raises(InvariantViolation):
        outcome(fixed, side_m=0.0)


def test_b8_rows_are_classified_and_tabulated() -> None:
    rows = [
        {"status": "ok", "relative_displacement": "0.10", "set": "a"},
        {"status": "ok", "relative_displacement": "0.40", "set": "a"},
        {"status": "infaisable", "relative_displacement": "", "set": "a"},
        {"status": "trame", "relative_displacement": "", "set": "b"},
        {"status": "weird", "relative_displacement": "", "set": "b"},
    ]
    assert [classify_row(r) for r in rows] == [
        "repaired",
        "repaired_strong_deformation",
        "contradictory_constraints",
        "grid_budget_exceeded",
        "other",
    ]
    (ga, na, ca, _), (gb, nb, cb, (low, _)) = failure_table(rows, by="set")
    assert (ga, na, ca["repaired"], ca["repaired_strong_deformation"]) == ("a", 3, 1, 1)
    assert (gb, nb, cb["other"], low) == ("b", 2, 1, 0.0)


# 3 ---------------------------------------------------------------------------------------
TWO = (_room("a", "bedroom", 0, 0, 6, 4.5), _room("b", "living_room", 6, 0, 6, 4.5))


def test_a_good_plan_passes_every_functional_check() -> None:
    wall = Wall(id="s", a=(0.0, 0.0), b=(12.0, 0.0))
    window = Opening(id="w", wall_id="s", s=0.25, relative_width=0.2)
    plan = Plan(rooms=TWO, walls=(wall,), openings=(window,), outline=OUTLINE)
    report = check_functional(
        plan,
        _ctx(program=("bedroom", "living_room")),
        required_adjacencies=(("bedroom", "living_room"),),
    )
    assert report.passed
    assert [c.status for c in report.checks] == ["satisfied"] * 5
    assert report.not_checked == FUNCTIONAL_NOT_CHECKED


def test_functional_checks_report_each_failure() -> None:
    outline = ((0.0, 0.0), (12.0, 0.0), (12.0, 9.0), (0.0, 9.0))
    rooms = (
        _room("a", "bedroom", 0, 0, 12, 3),
        _room("c", "bedroom", 0, 3, 12, 3),
        _room("b", "kitchen", 0, 6, 0.5, 0.5),
        _room("d", "bathroom", 0.5, 6, 11.5, 3),
    )
    inner = Wall(id="i", a=(0.0, 3.0), b=(12.0, 3.0))
    plan = Plan(
        rooms=rooms,
        walls=(inner,),
        outline=outline,
        openings=(
            Opening(id="w1", wall_id="i", s=0.5, relative_width=0.2),
            Opening(id="w2", wall_id="ghost", s=0.5, relative_width=0.2),
        ),
    )
    report = check_functional(
        plan,
        _ctx(outline, program=("living_room",)),
        required_adjacencies=(("kitchen", "living_room"),),
        habitable=("bedroom", "kitchen", "study"),
    )
    status = {c.id: c for c in report.checks}
    assert not report.passed
    assert status["topology"].status == "violated"  # the 0.5 m kitchen strip is isolated
    assert status["adjacencies"].status == "violated"
    assert "interior wall" in status["openings"].detail and "missing" in status["openings"].detail
    assert status["facade"].status == "satisfied"
    assert status["program"].detail.endswith("living_room")


def test_shared_wall_and_facade_lengths() -> None:
    a, b = TWO
    assert shared_wall(a, b) == pytest.approx(4.5)
    assert shared_wall(a, _room("far", "x", 20, 20, 1, 1)) == 0.0
    assert facade_length(a, OUTLINE) == pytest.approx(6 + 4.5 + 6)
    blind = check_functional(
        Plan(rooms=(_room("x", "bedroom", 1, 1, 2, 2),), outline=OUTLINE), _ctx()
    )
    assert {c.id: c.status for c in blind.checks}["facade"] == "violated"


def test_verify_functional_prints_the_checks_without_changing_the_exit_code(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "p.json"
    Plan(rooms=TWO, outline=OUTLINE).to_json(path)
    assert main(["verify", str(path), "--min-width", "0.9", "--functional"]) == 0
    out = capsys.readouterr().out
    assert "functional checks (not part of the certificate)" in out
    assert "topology: satisfied" in out


# 4 ---------------------------------------------------------------------------------------
def test_negative_coordinates_are_legalized_like_positive_ones() -> None:
    shift = -50.0
    outline = tuple((x + shift, y + shift) for x, y in OUTLINE)
    rooms = (
        _room("a", "bedroom", shift, shift, 6.1, 4.5),
        _room("b", "bedroom", shift + 6.0, shift, 6.0, 4.5),
    )
    out = ax.legalize(Plan(rooms=rooms, outline=outline), _ctx(outline), tiling=True)
    assert out.certificate is not None and out.certificate.geometry.valid
    assert min(r.x for r in out.rooms) == pytest.approx(shift)


def test_legalize_is_deterministic() -> None:
    plan = Plan(
        rooms=(_room("a", "bedroom", 0, 0, 6.3, 4.5), _room("b", "bedroom", 6.0, 0, 6.0, 4.4)),
        outline=OUTLINE,
    )
    first = ax.legalize(plan, _ctx(), tiling=True)
    assert all(ax.legalize(plan, _ctx(), tiling=True).rooms == first.rooms for _ in range(3))


def test_an_already_valid_plan_is_left_unchanged() -> None:
    plan = Plan(rooms=TWO, outline=OUTLINE)
    assert ax.legalize(plan, _ctx()).rooms == plan.rooms


def test_an_opening_flush_with_the_wall_end_is_accepted_and_one_beyond_is_refused() -> None:
    wall = Wall(id="s", a=(0.0, 0.0), b=(12.0, 0.0))
    flush = Plan(
        rooms=TWO,
        walls=(wall,),
        outline=OUTLINE,
        openings=(Opening(id="w", wall_id="s", s=0.1, relative_width=0.2),),
    )
    assert check_functional(flush, _ctx()).passed
    with pytest.raises(ax.ArchluxError):
        Opening(id="w", wall_id="s", s=1.2, relative_width=0.2)


# review fixes ------------------------------------------------------------------------------
def test_spearman_ignores_numerical_noise_on_null_derivatives() -> None:
    from archlux.light.trust import _continuous_measures

    signal = np.array([3.0, 1.0, 2.0])
    noise_a, noise_b = np.array([1e-17, -1e-17]), np.array([-1e-17, 1e-17])
    a = _continuous_measures([np.r_[signal, noise_a]], [np.r_[signal, noise_b]], [1.0])
    assert a["spearman"] == pytest.approx(1.0)


def test_the_default_acceptance_band_is_refused_at_another_level() -> None:
    from archlux.uq.reliability import CoverageReport

    report = CoverageReport(
        n=10,
        coverage=0.9,
        mean_width=1.0,
        target_std=1.0,
        coverage_low=0.5,
        coverage_high=1.0,
        alpha=0.05,
    )
    with pytest.raises(InvariantViolation, match=r"alpha=0\.05"):
        report.within()
    assert report.within((0.93, 0.97)) is False
