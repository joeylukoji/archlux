"""Features the article describes: trust radius from calibration, two-sided coverage
acceptance, Benjamini-Hochberg, Nadeau-Bengio, and the naive local repair baseline."""

from __future__ import annotations

import math

import pytest

import archlux as ax
from archlux.bench.naive import naive_repair
from archlux.bench.stats import benjamini_hochberg, holm, nadeau_bengio
from archlux.certify import verify_exactly
from archlux.errors import InvariantViolation
from archlux.types import Plan, Room
from archlux.uq import TrustRadius, chebyshev_displacement, trust_radius
from archlux.uq.reliability import ACCEPTANCE_BAND, CoverageReport

SQUARE = ((0.0, 0.0), (4.0, 0.0), (4.0, 2.0), (0.0, 2.0))


def _room(rid: str, x: float, w: float = 2.0) -> Room:
    return Room(id=rid, type="bedroom", x=x, y=0.0, w=w, h=2.0)


def test_trust_radius_is_the_conformal_quantile_of_the_displacements() -> None:
    values = [0.1 * k for k in range(1, 20)]
    radius = trust_radius(values, 0.10)
    assert radius == TrustRadius(radius=pytest.approx(1.8), alpha=0.10, n=19)


@pytest.mark.parametrize("values", [[-0.1, 1.0, 2.0], [math.nan, 1.0, 2.0], []])
def test_trust_radius_refuses_bad_displacements(values: list[float]) -> None:
    with pytest.raises(InvariantViolation):
        trust_radius(values, 0.5)


def test_trust_radius_refuses_a_calibration_too_small_for_alpha() -> None:
    with pytest.raises(InvariantViolation, match="too small"):
        trust_radius([1.0, 2.0], 0.10)


def test_chebyshev_displacement_is_the_largest_coordinate_move() -> None:
    before = Plan(rooms=(_room("a", 0.0), _room("b", 2.0)))
    after = Plan(rooms=(_room("a", 0.25), _room("b", 2.0, w=1.5)))
    assert chebyshev_displacement(after, before) == pytest.approx(0.5)


def test_chebyshev_displacement_refuses_different_rooms() -> None:
    with pytest.raises(InvariantViolation, match="identifiers"):
        chebyshev_displacement(Plan(rooms=(_room("a", 0.0),)), Plan(rooms=(_room("b", 0.0),)))


def test_the_trust_radius_bounds_legalize_through_budget() -> None:
    plan = Plan(rooms=(_room("a", 0.0), _room("b", 2.05)), outline=SQUARE)
    ctx = ax.Context(
        structure=ax.Structure(()),
        orientation=ax.Orientation(0.0),
        outline=SQUARE,
        regulation=ax.Regulation((("bedroom", 1.0),), 0.5),
    )
    radius = trust_radius([0.05 * k for k in range(1, 20)], 0.10).radius
    out = ax.legalize(plan, ctx, budget=radius)
    assert chebyshev_displacement(out, plan) <= radius + 1e-6
    assert verify_exactly(out, ctx).valid


def _report(coverage: float) -> CoverageReport:
    return CoverageReport(
        n=100,
        coverage=coverage,
        mean_width=1.0,
        target_std=1.0,
        coverage_low=0.0,
        coverage_high=1.0,
    )


@pytest.mark.parametrize(
    ("coverage", "accepted"),
    [(0.85, False), (0.86, True), (0.90, True), (0.94, True), (0.99, False)],
)
def test_coverage_acceptance_is_two_sided(coverage: float, accepted: bool) -> None:
    assert ACCEPTANCE_BAND == (0.86, 0.94)
    assert _report(coverage).within() is accepted


def test_coverage_acceptance_refuses_an_inverted_band() -> None:
    with pytest.raises(InvariantViolation):
        _report(0.9).within((0.95, 0.85))


def test_benjamini_hochberg_is_step_up_and_weaker_than_holm() -> None:
    p = [0.010, 0.020, 0.030, 0.040, 0.60]
    assert benjamini_hochberg(p) == (True, True, True, True, False)
    assert holm(p) == (True, False, False, False, False)
    assert benjamini_hochberg([0.2, 0.3]) == (False, False)


@pytest.mark.parametrize(("p", "q"), [([], 0.05), ([0.1], 1.5), ([1.2], 0.05)])
def test_benjamini_hochberg_refuses_bad_input(p: list[float], q: float) -> None:
    with pytest.raises(InvariantViolation):
        benjamini_hochberg(p, q=q)


def test_nadeau_bengio_is_more_conservative_than_the_naive_t_test() -> None:
    diffs = [0.02, 0.03, 0.01, 0.04, 0.02]
    t_corrected, p_corrected = nadeau_bengio(diffs, n_train=80, n_test=20)
    mean = sum(diffs) / 5
    sd = math.sqrt(sum((d - mean) ** 2 for d in diffs) / 4)
    assert 0.0 < t_corrected < mean / (sd / math.sqrt(5))
    assert 0.0 < p_corrected < 1.0


def test_nadeau_bengio_edges() -> None:
    assert nadeau_bengio([0.0, 0.0], n_train=10, n_test=5) == (0.0, 1.0)
    assert nadeau_bengio([0.1, 0.1], n_train=10, n_test=5) == (math.inf, 0.0)
    with pytest.raises(InvariantViolation):
        nadeau_bengio([0.1], n_train=10, n_test=5)
    with pytest.raises(InvariantViolation):
        nadeau_bengio([0.1, 0.2], n_train=0, n_test=5)


def test_naive_repair_moves_a_room_to_the_nearest_free_slot() -> None:
    plan = Plan(rooms=(_room("a", 0.0), _room("b", 1.0)), outline=SQUARE)
    out = naive_repair(plan)
    assert [(r.id, r.x) for r in out.rooms] == [("a", 0.0), ("b", 2.0)]
    assert out.certificate is None


def test_naive_repair_leaves_a_valid_plan_alone() -> None:
    plan = Plan(rooms=(_room("a", 0.0), _room("b", 2.0)), outline=SQUARE)
    assert naive_repair(plan) == plan


def test_naive_repair_keeps_a_room_that_fits_nowhere() -> None:
    plan = Plan(rooms=(_room("a", 0.0, w=3.0), _room("b", 1.0, w=3.0)), outline=SQUARE)
    assert naive_repair(plan).rooms[1].x == 1.0


def test_naive_repair_without_outline_uses_the_rooms_box() -> None:
    plan = Plan(rooms=(_room("a", 0.0), _room("b", 1.0), _room("c", 3.0)))
    out = naive_repair(plan)
    # The box is the rooms' own (0..5); c is not placed yet when b moves.
    assert out.rooms[1].x == 2.0
