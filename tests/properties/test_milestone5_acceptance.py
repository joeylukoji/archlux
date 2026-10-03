"""Acceptance criterion of milestone 5: coverage on the TEST set.

The oracle is ``SplitFluxOracle`` (split-flux), not a ray-tracing engine. The guarantee
holds for that frozen oracle (`ARCHITECTURE.md` §2).
"""

from __future__ import annotations

import numpy as np

from archlux.light.analytic import AnalyticSurrogate
from archlux.light.split_flux import SplitFluxOracle
from archlux.types import Orientation
from archlux.uq.conformal import ConformalCalibrator
from archlux.uq.reliability import stratify_by_orientation


def _draw(rng: np.random.Generator, n: int) -> tuple[list[np.ndarray], list[Orientation]]:
    xs: list[np.ndarray] = []
    os_: list[Orientation] = []
    for _ in range(n):
        width = float(rng.uniform(4.0, 8.0))
        xs.append(np.array([0.0, 0.0, width, 4.5, width, 0.0, 12.0 - width, 4.5]))
        os_.append(Orientation(deg=float(rng.uniform(0.0, 360.0))))
    return xs, os_


def _evaluate(
    model: AnalyticSurrogate,
    oracle: SplitFluxOracle,
    xs: list[np.ndarray],
    os_: list[Orientation],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    pred = np.array([model.evaluate(x, o) for x, o in zip(xs, os_, strict=True)])
    truth = np.array([oracle.evaluate(x, o) for x, o in zip(xs, os_, strict=True)])
    sigma = np.array([model.uncertainty(x, o) for x, o in zip(xs, os_, strict=True)])
    return pred, truth, sigma


def test_empirical_coverage() -> None:
    """On the TEST set, never on the calibration set. Target 0.90 ± 4 points."""
    rng = np.random.default_rng(17)
    model = AnalyticSurrogate()
    oracle = SplitFluxOracle()
    xs_cal, os_cal = _draw(rng, 220)
    xs_test, os_test = _draw(rng, 280)
    p_cal, v_cal, s_cal = _evaluate(model, oracle, xs_cal, os_cal)
    calibrator = ConformalCalibrator()
    calibrator.fit(p_cal, v_cal, s_cal, alpha=0.10)
    p_test, v_test, s_test = _evaluate(model, oracle, xs_test, os_test)
    # Interval coverage (both sides): "the upper bound counts as much".
    ok = []
    for pred, truth, sigma in zip(p_test, v_test, s_test, strict=True):
        bound = calibrator.bound(float(pred), float(sigma), ">=", regime="exchangeable")
        ok.append(bound.lower <= truth <= bound.upper)
    cov = float(np.mean(ok))
    assert 0.86 <= cov <= 0.94, f"test coverage = {cov:.3f}"


def test_calibration_holds_per_orientation() -> None:
    """Eight sectors: the coverage must not collapse at north only."""
    rng = np.random.default_rng(21)
    n = 1600
    mu = rng.normal(40.0, 2.0, n)
    sigma = np.full(n, 1.5)
    y = mu + sigma * rng.normal(0.0, 1.0, n)
    degrees = rng.uniform(0.0, 360.0, n)
    cal = slice(0, 800)
    test = slice(800, 1600)
    calibrator = ConformalCalibrator()
    calibrator.fit(mu[cal], y[cal], sigma[cal], alpha=0.10)
    bins = stratify_by_orientation(degrees[test])
    for sector, idx_rel in bins.items():
        if idx_rel.size < 40:
            continue
        idx = idx_rel + 800
        ok = []
        for i in idx:
            bound = calibrator.bound(float(mu[i]), float(sigma[i]), ">=", regime="exchangeable")
            ok.append(bound.lower <= y[i] <= bound.upper)
        cov = float(np.mean(ok))
        assert 0.84 <= cov <= 0.96, f"sector {sector}: {cov:.3f}"


def test_bounded_drift_on_frozen_oracle() -> None:
    """The analytic surrogate does not drift explosively against the i.i.d. split-flux."""
    from archlux.uq.drift import measure_drift

    rng = np.random.default_rng(9)
    model = AnalyticSurrogate()
    oracle = SplitFluxOracle()
    xs, os_ = _draw(rng, 40)
    pred, truth, _sigma = _evaluate(model, oracle, xs, os_)
    report = measure_drift(pred, truth, seed=9)
    amplitude = float(np.std(truth) + 1e-9)
    assert abs(report.mean_drift) < 3.0 * amplitude
    assert report.trend_pvalue > 0.05 or report.trend_slope <= 0.0
