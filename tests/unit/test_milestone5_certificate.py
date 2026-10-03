"""Milestone 5 certificate: bound, readable duals, two-kind report."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pytest
from scipy import sparse

from archlux.certify.bound import build_bound
from archlux.certify.dual import translate_duals
from archlux.errors import InvariantViolation
from archlux.geom.polytope import Polytope
from archlux.light.objective import Daylight
from archlux.light.protocol import Surrogate
from archlux.types import (
    Certificate,
    GeometricProof,
    Manifest,
    Orientation,
    PerformanceBound,
)
from archlux.uq.conformal import Calibration
from archlux.uq.drift import DriftDiagnostic, check_drift, measure_drift
from archlux.uq.reliability import crps, reliability_diagram, stratify_by_orientation


def _poly() -> Polytope:
    return Polytope(
        A=sparse.csr_matrix(np.eye(3)),
        b=np.ones(3),
        A_eq=sparse.csr_matrix((0, 3)),
        b_eq=np.zeros(0),
        bounds=((0.0, 1.0),) * 3,
        index={"a.x": 0, "a.y": 1, "a.w": 2},
        origins=(
            "load-bearing wall axis 3",
            "minimum kitchen area",
            "passage width",
        ),
    )


def _proof() -> GeometricProof:
    return GeometricProof(
        valid=True,
        overlap=False,
        gaps=False,
        areas_ok=True,
        structure_kept=True,
        max_displacement=0.18,
    )


def test_the_diagnostic_is_readable() -> None:
    duals = np.array([-4.1, -1.7, 0.0])
    phrases = translate_duals(duals, _poly())
    assert all(len(label) > 20 for label, _price in phrases)
    assert all("small changes" in label for label, _price in phrases)


def test_zero_price_for_an_inactive_constraint() -> None:
    duals = np.array([-4.1, 0.0, 1e-9])
    phrases = translate_duals(duals, _poly())
    assert all(price != 0.0 for _label, price in phrases)
    assert len(phrases) == 1


def test_duals_sorted_by_absolute_cost() -> None:
    duals = np.array([-1.0, 5.0, -3.0])
    phrases = translate_duals(duals, _poly())
    assert [abs(p) for _, p in phrases] == [5.0, 3.0, 1.0]


def test_the_certificate_separates_the_kinds() -> None:
    performance_bound = PerformanceBound(
        indicator="sDA",
        value=56.2,
        lower=51.4,
        upper=61.0,
        coverage=0.90,
        n_calibration=1284,
        regime="exchangeable",
    )
    text = Certificate(
        geometry=_proof(),
        performance=performance_bound,
        duals=(("load-bearing wall axis 3: relaxation", -4.1),),
        manifest=Manifest(version="0.4.0", timestamp="2026-09-09T00:00:00Z", seed=17),
    ).report()
    assert "[EXACT]" in text and "[PREDICTION" in text
    assert "1284" in text
    assert "NOT EVALUABLE" in text


def test_not_evaluable_always_present() -> None:
    text = Certificate(geometry=_proof()).report()
    assert "NOT EVALUABLE" in text
    assert "[PREDICTION" in text


def test_build_bound_refuses_drift() -> None:
    scores = np.abs(np.random.default_rng(0).normal(0.0, 1.0, 40))
    calibration = Calibration(scores, 0.10, "sDA", "abc")
    drift = DriftDiagnostic(
        exchangeable=False,
        statistic=0.4,
        threshold=0.05,
        n_observations=20,
        message="drift",
    )
    assert build_bound(50.0, calibration, drift, uncertainty=1.0, regime="exchangeable") is None
    ok = DriftDiagnostic(True, 0.05, 0.05, 20, "ok")
    performance_bound = build_bound(50.0, calibration, ok, uncertainty=1.0, regime="exchangeable")
    assert performance_bound is not None
    assert performance_bound.n_calibration == 40


def test_check_drift_detects_a_shift() -> None:
    rng = np.random.default_rng(4)
    cal = Calibration(np.abs(rng.normal(0.0, 1.0, 80)), 0.10, "sDA", "c")
    same = np.abs(rng.normal(0.0, 1.0, 80))
    assert check_drift(same, cal, seed=17).exchangeable
    shifted = np.abs(rng.normal(3.0, 1.0, 80))
    assert not check_drift(shifted, cal, seed=17).exchangeable


def test_measure_drift_is_positive_on_overestimation() -> None:
    pred = np.array([10.0, 11.0, 12.0, 13.0])
    truth = np.array([9.0, 10.0, 11.0, 12.0])
    report = measure_drift(pred, truth, seed=1)
    assert report.mean_drift == pytest.approx(1.0)
    assert report.n_samples == 4


def test_a_perfect_crps_is_small() -> None:
    y = np.array([0.0, 0.0, 0.0, 0.0])
    mu = y.copy()
    sigma = np.ones(4)
    assert crps(mu, y, sigma) < crps(mu + 2.0, y, sigma)


def test_reliability_diagram_is_an_array() -> None:
    rng = np.random.default_rng(2)
    mu = rng.normal(0.0, 1.0, 80)
    y = mu + rng.normal(0.0, 1.0, 80)
    sigma = np.ones(80)
    grid = reliability_diagram(mu, y, sigma, levels=np.array([0.80, 0.90]))
    assert grid.shape == (2, 2)
    assert grid[0, 0] == pytest.approx(0.80)


def test_stratify_eight_sectors() -> None:
    degrees = np.array([0.0, 45.0, 90.0, 180.0, 359.0])
    bins = stratify_by_orientation(degrees)
    assert set(bins) == set(range(8))
    assert 0 in bins[0]
    assert 4 in bins[7]


@dataclass
class _FakeSurrogate:
    mu: float
    sigma: float
    indicator: str = "sDA"

    def evaluate(self, x: np.ndarray, orientation: Orientation, *, glazing: object = None) -> float:
        return self.mu

    def gradient(
        self, x: np.ndarray, orientation: Orientation, *, glazing: object = None
    ) -> np.ndarray:
        return np.zeros_like(x, dtype=float)

    def uncertainty(
        self, x: np.ndarray, orientation: Orientation, *, glazing: object = None
    ) -> float:
        return self.sigma


def test_pessimistic_penalizes_uncertainty() -> None:
    """At equal prediction, the more uncertain plan has a lower objective."""
    orientation = Orientation(deg=180.0)
    x = np.ones(4)
    certain = Daylight(_FakeSurrogate(50.0, 0.2), q_hat=1.64, pessimistic=True)
    uncertain = Daylight(_FakeSurrogate(50.0, 2.0), q_hat=1.64, pessimistic=True)
    assert certain.evaluate(x, orientation) > uncertain.evaluate(x, orientation)
    assert isinstance(certain, Surrogate)


def test_daylight_without_pessimism_ignores_sigma() -> None:
    orientation = Orientation(deg=0.0)
    x = np.ones(2)
    j = Daylight(_FakeSurrogate(40.0, 9.0), q_hat=2.0, pessimistic=False)
    assert j.evaluate(x, orientation) == pytest.approx(40.0)


def test_reliability_diagram_rejects_levels_outside_unit_interval() -> None:
    """A level outside ]0, 1[ is a caller error, not a ``nan`` row."""
    mu, y, sigma = np.zeros(50), np.linspace(-1.0, 1.0, 50), np.ones(50)
    with pytest.raises(InvariantViolation):
        reliability_diagram(mu, y, sigma, levels=np.array([1.5, -0.2]))


def test_reliability_diagram_rejects_non_finite_truths() -> None:
    """A ``nan`` truth makes the reference scores non-finite: raise, never a ``nan`` grid."""
    mu, y, sigma = np.zeros(50), np.linspace(-1.0, 1.0, 50), np.ones(50)
    y[3] = np.nan
    with pytest.raises(InvariantViolation):
        reliability_diagram(mu, y, sigma, levels=np.array([0.8]))


def test_reliability_diagram_keeps_nan_only_for_too_small_n() -> None:
    """The documented sentinel survives: a level too demanding for ``n`` gives ``nan``."""
    mu, y, sigma = np.zeros(5), np.linspace(-1.0, 1.0, 5), np.ones(5)
    grid = reliability_diagram(mu, y, sigma, levels=np.array([0.5, 0.99]))
    assert np.isfinite(grid[0, 1])
    assert np.isnan(grid[1, 1])
