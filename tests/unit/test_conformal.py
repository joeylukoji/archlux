"""Conformal prediction: `MILESTONE-5.md` §3. The naive 0.90 quantile is forbidden."""

from __future__ import annotations

import math

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from archlux.errors import InvariantViolation
from archlux.types import PerformanceBound
from archlux.uq.conformal import Calibration, ConformalCalibrator, bound, conformal_quantile


def _scores(n: int, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return np.abs(rng.normal(0.0, 1.0, size=n))


def test_finite_sample_correction() -> None:
    """``ceil((n+1)(1−α))`` is strictly wider than the empirical 0.90 quantile."""
    n = 100
    rng = np.random.default_rng(7)
    predictions = rng.normal(50.0, 1.0, n)
    truths = predictions + rng.normal(0.0, 1.0, n)
    uncertainties = np.ones(n)
    scores = np.abs(truths - predictions) / uncertainties
    calibrator = ConformalCalibrator()
    calibrator.fit(predictions, truths, uncertainties, alpha=0.10)
    assert calibrator.q > float(np.quantile(scores, 0.90))
    rank = math.ceil((n + 1) * 0.90)
    assert calibrator.q == pytest.approx(float(np.sort(scores)[rank - 1]))


def test_quantile_refuses_a_set_too_small() -> None:
    """n too small for 1−α: an explicit failure, not an infinite bound."""
    with pytest.raises(InvariantViolation, match="too small"):
        conformal_quantile(_scores(8), alpha=0.10)


def test_no_bound_without_calibration() -> None:
    """A bound without a calibration set cannot be checked."""
    with pytest.raises(InvariantViolation, match="n_calibration"):
        PerformanceBound(
            indicator="sDA",
            value=56.2,
            lower=51.4,
            upper=61.0,
            coverage=0.90,
            n_calibration=0,
            regime="exchangeable",
        )


def test_ase_direction_is_reversed() -> None:
    """ASE publishes an upper bound: above the prediction."""
    n = 80
    rng = np.random.default_rng(3)
    predictions = rng.normal(6.0, 0.4, n)
    truths = predictions + rng.normal(0.0, 0.5, n)
    uncertainties = np.ones(n)
    calibrator = ConformalCalibrator(indicator="ASE")
    calibrator.fit(predictions, truths, uncertainties, alpha=0.10)
    conformal_bound = calibrator.bound(6.1, 1.0, "<=", regime="exchangeable")
    assert conformal_bound.upper > conformal_bound.value
    assert conformal_bound.indicator == "ASE"


def test_bound_reproduces_the_quantile() -> None:
    """``bound`` relies on the same conformal rank, not on ``np.quantile``."""
    scores = _scores(60, seed=11)
    calibration = Calibration(
        scores=scores,
        alpha=0.10,
        indicator="sDA",
        data_fingerprint="test",
    )
    conformal_bound = bound(50.0, calibration, uncertainty=1.0, regime="exchangeable")
    q = conformal_quantile(scores, 0.10)
    assert conformal_bound.lower == pytest.approx(50.0 - q)
    assert conformal_bound.n_calibration == 60
    assert conformal_bound.coverage == pytest.approx(0.90)


@given(alpha=st.floats(min_value=0.05, max_value=0.20, allow_nan=False))
@settings(max_examples=8, deadline=None)
def test_coverage_on_synthetic_data(alpha: float) -> None:
    """On i.i.d. data, the one-sided coverage holds at 1−α within 3 points."""
    rng = np.random.default_rng(17)
    n_cal, n_test = 250, 400
    pred_cal = rng.normal(40.0, 2.0, n_cal)
    sig_cal = np.full(n_cal, 1.5)
    truth_cal = pred_cal + sig_cal * rng.normal(0.0, 1.0, n_cal)
    calibrator = ConformalCalibrator()
    calibrator.fit(pred_cal, truth_cal, sig_cal, alpha=alpha)
    pred = rng.normal(40.0, 2.0, n_test)
    sig = np.full(n_test, 1.5)
    truth = pred + sig * rng.normal(0.0, 1.0, n_test)
    covered = [
        v >= calibrator.bound(float(p), float(s), ">=", regime="exchangeable").lower
        for p, v, s in zip(pred, truth, sig, strict=True)
    ]
    assert float(np.mean(covered)) >= 1.0 - alpha - 0.03
