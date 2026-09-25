"""Library functions that replaced code of the experiment scripts (AUDIT.md M12, phase 2)."""

from __future__ import annotations

import numpy as np
import pytest

from archlux.data.synthese import two_room_plan, two_room_vectors
from archlux.erreurs import InvariantViole
from archlux.geom.graphe import deduire_ordre
from archlux.geom.polytope import construire_polytope, decision_vector, vectoriser
from archlux.types import Piece, Plan
from archlux.uq.conforme import CalibrateurConforme
from archlux.uq.fiabilite import measure_coverage
from tests.proprietes.strategies import CONTEXTE_DEFAUT


def test_the_decision_vector_matches_the_polytope_columns() -> None:
    plan = Plan(
        pieces=(
            Piece(id="c", type="sejour", x=8.0, y=0.0, w=4.0, h=9.0),
            Piece(id="a", type="sejour", x=0.0, y=0.0, w=3.0, h=9.0),
            Piece(id="b", type="sejour", x=3.0, y=0.0, w=5.0, h=9.0),
        ),
        murs=(),
        ouvertures=(),
        contour=CONTEXTE_DEFAUT.contour,
    )
    index = construire_polytope(deduire_ordre(plan), CONTEXTE_DEFAUT).index
    assert np.array_equal(decision_vector(plan), vectoriser(plan, index))


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
    with pytest.raises(InvariantViole):
        two_room_vectors(-1, seed=17)


def test_measure_coverage_on_gaussian_noise() -> None:
    """Exchangeable Gaussian noise: coverage near 0.90, width near 2 x 1.645 sigma."""
    rng = np.random.default_rng(3)
    mu = rng.normal(50.0, 10.0, 4000)
    y = mu + rng.normal(0.0, 1.0, 4000)
    calibrator = CalibrateurConforme()
    calibrator.ajuster(mu[:2000], y[:2000], np.ones(2000), alpha=0.10)
    report = measure_coverage(calibrator, mu[2000:], y[2000:], np.ones(2000), regime="exchangeable")
    assert report.n == 2000
    assert report.coverage == pytest.approx(0.90, abs=0.02)
    assert report.mean_width == pytest.approx(2 * 1.645, rel=0.05)
    assert report.target_std == pytest.approx(np.hypot(10.0, 1.0), rel=0.05)
    assert report.width_over_std == pytest.approx(report.mean_width / report.target_std)


def test_measure_coverage_refuses_misaligned_arrays() -> None:
    calibrator = CalibrateurConforme()
    calibrator.ajuster(np.zeros(30), np.ones(30), np.ones(30), alpha=0.10)
    with pytest.raises(InvariantViole):
        measure_coverage(calibrator, np.zeros(3), np.ones(3), np.ones(2), regime="selected")


def test_two_room_plan_is_the_inverse_of_decision_vector() -> None:
    xs, _ = two_room_vectors(5, seed=4)
    for x in xs:
        assert np.array_equal(decision_vector(two_room_plan(x)), x)
