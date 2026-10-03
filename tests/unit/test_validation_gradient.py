"""Gradient checkpoint: `MILESTONE-4.md` §7."""

from __future__ import annotations

import numpy as np
import pytest

from archlux.errors import InvalidSurrogate
from archlux.light.analytic import AnalyticSurrogate
from archlux.light.validation import validate_gradient
from archlux.types import Orientation

X = np.array([[1.0, 2.0, 4.0, 5.0, 5.0, 2.0, 3.0, 5.0]])
NORTH = Orientation(deg=0.0)


def test_analytic_is_consistent_with_its_finite_differences() -> None:
    report = validate_gradient(AnalyticSurrogate(), X, NORTH, seed=17, epsilon=1e-5)
    assert report.passed
    assert report.mean_cosine > 0.99


def test_a_wrong_gradient_raises_invalid_surrogate() -> None:
    class Wrong:
        indicator = "sDA"

        def evaluate(self, x, orientation):
            del orientation
            return float(np.sum(x))

        def gradient(self, x, orientation):
            del orientation
            return np.ones_like(x) * 7.0

        def uncertainty(self, x, orientation):
            del x, orientation
            return 0.08

    with pytest.raises(InvalidSurrogate):
        validate_gradient(Wrong(), X, NORTH, seed=17)


def test_a_failed_check_carries_its_report() -> None:
    """PLAN.md phase 2, J4: the failing value is read from the report, not the message."""
    from archlux.light.analytic import AnalyticSurrogate

    class Negated(AnalyticSurrogate):
        def gradient(self, x, orientation, *, glazing=None):  # type: ignore[no-untyped-def]
            return -super().gradient(x, orientation, glazing=glazing)

    with pytest.raises(InvalidSurrogate) as capture:
        validate_gradient(Negated(), X, NORTH, seed=17, reference=AnalyticSurrogate())
    report = capture.value.report
    assert report is not None and not report.passed
    assert report.sign_agreement < 0.8
