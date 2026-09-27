"""Library functions that replaced code of the experiment scripts (AUDIT.md M12, phase 2)."""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings

import archlux
from archlux.data.synthese import two_room_plan, two_room_vectors
from archlux.errors import InvariantViolation
from archlux.geom.graphe import deduce_order
from archlux.geom.polytope import build_polytope, decision_vector, vectorize
from archlux.light.analytique import AnalyticSurrogate
from archlux.types import Context, Orientation, Plan, Regulation, Room, Structure, Wall
from archlux.uq.conforme import ConformalCalibrator
from archlux.uq.fiabilite import measure_coverage
from tests.properties.strategies import CONTEXTE_DEFAUT, realistic_scenarios


def test_the_decision_vector_matches_the_polytope_columns() -> None:
    plan = Plan(
        rooms=(
            Room(id="c", type="living_room", x=8.0, y=0.0, w=4.0, h=9.0),
            Room(id="a", type="living_room", x=0.0, y=0.0, w=3.0, h=9.0),
            Room(id="b", type="living_room", x=3.0, y=0.0, w=5.0, h=9.0),
        ),
        walls=(),
        openings=(),
        outline=CONTEXTE_DEFAUT.outline,
    )
    index = build_polytope(deduce_order(plan), CONTEXTE_DEFAUT).index
    assert np.array_equal(decision_vector(plan), vectorize(plan, index))


def test_two_room_vectors_are_reproducible_and_in_range() -> None:
    xs, orientations = two_room_vectors(50, seed=17)
    again, _ = two_room_vectors(50, seed=17)
    assert all(np.array_equal(a, b) for a, b in zip(xs, again, strict=True))
    cuts = np.array([x[2] for x in xs])
    assert cuts.min() >= 4.0 and cuts.max() <= 8.0
    assert all(x[2] + x[6] == pytest.approx(12.0) for x in xs)
    assert all(0.0 <= o.deg < 360.0 for o in orientations)
    assert not np.array_equal(xs[0], two_room_vectors(1, seed=18)[0][0])


def test_two_room_vectors_refuse_a_negative_size() -> None:
    with pytest.raises(InvariantViolation):
        two_room_vectors(-1, seed=17)


def test_measure_coverage_on_gaussian_noise() -> None:
    """Exchangeable Gaussian noise: coverage near 0.90, width near 2 x 1.645 sigma."""
    rng = np.random.default_rng(3)
    mu = rng.normal(50.0, 10.0, 4000)
    y = mu + rng.normal(0.0, 1.0, 4000)
    calibrator = ConformalCalibrator()
    calibrator.fit(mu[:2000], y[:2000], np.ones(2000), alpha=0.10)
    report = measure_coverage(calibrator, mu[2000:], y[2000:], np.ones(2000), regime="exchangeable")
    assert report.n == 2000
    assert report.coverage == pytest.approx(0.90, abs=0.02)
    assert report.mean_width == pytest.approx(2 * 1.645, rel=0.05)
    assert report.target_std == pytest.approx(np.hypot(10.0, 1.0), rel=0.05)
    assert report.width_over_std == pytest.approx(report.mean_width / report.target_std)
    assert report.coverage_low < report.coverage < report.coverage_high
    assert report.coverage_high - report.coverage_low == pytest.approx(0.026, abs=0.004)


def test_measure_coverage_refuses_a_zero_uncertainty() -> None:
    calibrator = ConformalCalibrator()
    calibrator.fit(np.zeros(30), np.ones(30), np.ones(30), alpha=0.10)
    sigma = np.array([1.0, 0.0, 1.0])
    with pytest.raises(InvariantViolation, match="strictly positive"):
        measure_coverage(calibrator, np.zeros(3), np.ones(3), sigma, regime="selected")


def test_measure_coverage_refuses_misaligned_arrays() -> None:
    calibrator = ConformalCalibrator()
    calibrator.fit(np.zeros(30), np.ones(30), np.ones(30), alpha=0.10)
    with pytest.raises(InvariantViolation):
        measure_coverage(calibrator, np.zeros(3), np.ones(3), np.ones(2), regime="selected")


def test_two_room_plan_is_the_inverse_of_decision_vector() -> None:
    xs, _ = two_room_vectors(5, seed=4)
    for x in xs:
        assert np.array_equal(decision_vector(two_room_plan(x)), x)


@given(scenario=realistic_scenarios())
@settings(max_examples=100, deadline=None)
def test_the_decision_vector_matches_the_columns_of_every_polytope(
    scenario: tuple[Plan, Context],
) -> None:
    """Review of phase 2, Minor 11: the invariant on every plan, not on one."""
    plan, ctx = scenario
    index = build_polytope(deduce_order(plan, structure=ctx.structure), ctx).index
    assert np.array_equal(decision_vector(plan), vectorize(plan, index))


def test_a_flat_optimum_gives_different_plans_at_equal_value() -> None:
    """J3 review: theta = 0 and 360 give plans 5.2 m apart at the same objective value."""
    wall = Wall(id="lb0", a=(1.01, 0.0), b=(1.01, 9.0), load_bearing=True)
    rooms = (
        Room(id="p0", type="living_room", x=0.0, y=0.0, w=1.01, h=9.0),
        Room(id="p1", type="living_room", x=1.01, y=0.0, w=1.41, h=1.0),
        Room(id="p2", type="living_room", x=1.01, y=1.0, w=1.41, h=8.0),
        Room(id="p3", type="living_room", x=2.42, y=0.0, w=9.58, h=1.0),
        Room(id="p4", type="living_room", x=2.42, y=1.0, w=9.58, h=8.0),
    )
    plan = Plan(rooms, (wall,), (), CONTEXTE_DEFAUT.outline)
    surrogate, values, widths = AnalyticSurrogate(), [], []
    for deg in (0.0, 360.0):
        ctx = Context(
            structure=Structure(load_bearing_walls=(wall,)),
            orientation=Orientation(deg=deg),
            outline=CONTEXTE_DEFAUT.outline,
            regulation=Regulation(min_areas=(("living_room", 1.41),), min_width=1.0),
        )
        out = archlux.legalize(plan, ctx, objective=surrogate)
        values.append(surrogate.evaluate(decision_vector(out), Orientation(deg=0.0)))
        widths.append(next(r.w for r in out.rooms if r.id == "p1"))
    assert values[0] == pytest.approx(values[1], rel=1e-12)
    assert abs(widths[0] - widths[1]) > 1.0  # not unique: the criterion is on values
