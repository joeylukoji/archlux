"""Analytic surrogate: `MILESTONE-3.md` §4. Vector input only."""

from __future__ import annotations

import numpy as np
import pytest

from archlux.light.analytic import AnalyticSurrogate
from archlux.light.protocol import Surrogate
from archlux.types import Orientation


def test_satisfies_the_protocol() -> None:
    assert isinstance(AnalyticSurrogate(), Surrogate)


def test_a_room_further_south_is_better_exposed() -> None:
    """At orientation 0° (y axis towards north), a room of smaller y is further south."""
    surrogate = AnalyticSurrogate()
    north = Orientation(deg=0.0)
    to_south = np.array([0.0, 0.0, 4.0, 4.0])
    to_north = np.array([0.0, 6.0, 4.0, 4.0])
    assert surrogate.evaluate(to_south, north) > surrogate.evaluate(to_north, north)


def test_south_beats_north_at_equal_geometry() -> None:
    """The useful-depth rule is modulated by the sector (8 steps of 45°)."""
    surrogate = AnalyticSurrogate()
    x = np.array([0.0, 0.0, 4.0, 5.0])
    assert surrogate.evaluate(x, Orientation(deg=180.0)) > surrogate.evaluate(
        x, Orientation(deg=0.0)
    )


def test_gradient_consistent_with_finite_differences() -> None:
    surrogate = AnalyticSurrogate()
    x = np.array([1.0, 2.0, 4.0, 5.0, 5.0, 2.0, 3.0, 5.0])
    orientation = Orientation(deg=135.0)
    analytic = surrogate.gradient(x, orientation)
    step = 1e-6
    numeric = np.empty_like(x)
    for i in range(x.size):
        plus, minus = x.copy(), x.copy()
        plus[i] += step
        minus[i] -= step
        numeric[i] = (
            surrogate.evaluate(plus, orientation) - surrogate.evaluate(minus, orientation)
        ) / (2.0 * step)
    assert np.allclose(analytic, numeric, rtol=1e-4, atol=1e-5)


def test_a_wider_facade_gives_more_light() -> None:
    """Vector analogue of "more glazing": a wider south facade gives more light."""
    surrogate = AnalyticSurrogate()
    south = Orientation(deg=180.0)
    narrow = np.array([0.0, 0.0, 3.0, 4.0])
    large = np.array([0.0, 0.0, 6.0, 4.0])
    assert surrogate.evaluate(large, south) > surrogate.evaluate(narrow, south)


def test_a_deep_room_saturates() -> None:
    """Beyond 2.5 times the head height at south, more depth adds no more light."""
    surrogate = AnalyticSurrogate()
    south = Orientation(deg=180.0)
    shallow = np.array([0.0, 0.0, 4.0, 6.0])
    deeper = np.array([0.0, 0.0, 4.0, 9.0])
    assert surrogate.evaluate(deeper, south) <= surrogate.evaluate(shallow, south) + 1e-9


def test_documented_constant_uncertainty() -> None:
    surrogate = AnalyticSurrogate(sigma_nominal=0.08)
    x = np.ones(4)
    assert surrogate.uncertainty(x, Orientation(deg=0.0)) == pytest.approx(0.08)


def test_the_indicator_follows_the_target() -> None:
    assert AnalyticSurrogate(target_indicator="ASE").indicator == "ASE"
