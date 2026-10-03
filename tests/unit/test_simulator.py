"""Frozen split-flux oracle (`SplitFluxOracle`): `MILESTONE-4.md` §3."""

from __future__ import annotations

import numpy as np
import pytest

from archlux.light.protocol import Surrogate
from archlux.light.split_flux import SplitFluxOracle, daylight_factor
from archlux.light.validation import validate_gradient
from archlux.types import Orientation


def test_simulator_respects_the_protocol() -> None:
    assert isinstance(SplitFluxOracle(), Surrogate)


def test_deterministic_simulation() -> None:
    radiance = SplitFluxOracle()
    x = np.array([0.0, 0.0, 6.0, 4.5, 6.0, 0.0, 6.0, 4.5])
    ctx = Orientation(deg=40.0)
    assert radiance.evaluate(x, ctx) == radiance.evaluate(x, ctx)


def test_ase_is_the_opposite_of_sda() -> None:
    """ASE negates the full score once, not the analytic part and then the total."""
    x = np.array([0.0, 0.0, 6.0, 4.5, 6.0, 0.0, 6.0, 4.5])
    ctx = Orientation(deg=40.0)
    sda = SplitFluxOracle(target_indicator="sDA").evaluate(x, ctx)
    ase = SplitFluxOracle(target_indicator="ASE").evaluate(x, ctx)
    assert ase == pytest.approx(-sda)


def test_df_of_a_canonical_room_in_the_bre_range() -> None:
    """Room 6 m × 4 m, WWR 30 %, south, clear sky: typical mean DF 1–5 %."""
    df = daylight_factor(6.0, 4.0, Orientation(deg=180.0), wwr=0.30)
    assert 0.008 <= df <= 0.05


def test_df_drops_when_the_room_deepens() -> None:
    south = Orientation(deg=180.0)
    shallow = daylight_factor(6.0, 4.0, south, wwr=0.30)
    deep = daylight_factor(6.0, 8.0, south, wwr=0.30)
    assert deep < shallow


def test_df_south_beats_north() -> None:
    x_w, y_d = 6.0, 4.0
    assert daylight_factor(x_w, y_d, Orientation(deg=180.0)) > daylight_factor(
        x_w, y_d, Orientation(deg=0.0)
    )


def test_df_increases_with_the_wwr() -> None:
    south = Orientation(deg=180.0)
    narrow = daylight_factor(6.0, 4.0, south, wwr=0.20)
    large = daylight_factor(6.0, 4.0, south, wwr=0.40)
    assert large > narrow


def test_simulator_follows_the_wwr() -> None:
    x = np.array([0.0, 0.0, 6.0, 4.0])
    south = Orientation(deg=180.0)
    assert SplitFluxOracle(wwr=0.40).evaluate(x, south) > SplitFluxOracle(wwr=0.20).evaluate(
        x, south
    )


def test_gradient_consistent_with_split_flux() -> None:
    report = validate_gradient(
        SplitFluxOracle(),
        np.array([[0.0, 0.0, 6.0, 4.0, 6.0, 0.0, 6.0, 4.5]]),
        Orientation(deg=180.0),
        seed=17,
    )
    assert report.passed
