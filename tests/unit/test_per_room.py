"""The `PerRoomSurrogate` protocol: values per room.

The thesis: daylight is a quantity **per room**, not per plan. Measured on 367,466
rooms of Swiss Dwellings: 92 % of the variance is within an apartment, the building
identity explains only 2.6 %. These tests pin the consistency between the fine
granularity and the scalar that `solve` still optimizes.
"""

from __future__ import annotations

import numpy as np
import pytest

from archlux.light.analytic import AnalyticSurrogate
from archlux.light.protocol import PerRoomSurrogate, Surrogate
from archlux.light.split_flux import SplitFluxOracle
from archlux.types import Orientation

IMPLEMENTATIONS = [AnalyticSurrogate, SplitFluxOracle]
INDICATORS = ["sDA", "ASE", "UDI", "vue"]


def _plan(n: int) -> np.ndarray:
    """Decision vector of ``n`` rooms, non-trivial dimensions."""
    rng = np.random.default_rng(11)
    pieces = []
    for _ in range(n):
        pieces.extend(
            [
                float(rng.uniform(0.0, 8.0)),
                float(rng.uniform(0.0, 6.0)),
                float(rng.uniform(2.0, 7.0)),
                float(rng.uniform(2.0, 6.0)),
            ]
        )
    return np.array(pieces, dtype=float)


@pytest.mark.parametrize("cls", IMPLEMENTATIONS, ids=lambda c: c.__name__)
def test_implements_both_protocols(cls: type) -> None:
    """A per-room surrogate stays a `Surrogate`: the extension is additive."""
    instance = cls()
    assert isinstance(instance, Surrogate)
    assert isinstance(instance, PerRoomSurrogate)


@pytest.mark.parametrize("cls", IMPLEMENTATIONS, ids=lambda c: c.__name__)
@pytest.mark.parametrize("indicator", INDICATORS)
@pytest.mark.parametrize("n_rooms", [1, 3, 7])
def test_the_sum_of_the_parts_gives_back_the_scalar(
    cls: type, indicator: str, n_rooms: int
) -> None:
    """Central contract: the scalarization of the repository is the **sum**.

    Without that guarantee, `solve` would optimize a quantity unrelated to the exposed
    per-room values, and the certificate would be inconsistent with itself.
    """
    surrogate = cls(target_indicator=indicator)
    x = _plan(n_rooms)
    orientation = Orientation(deg=143.0)
    parts = surrogate.evaluate_rooms(x, orientation)
    assert parts.shape == (n_rooms,)
    assert float(parts.sum()) == pytest.approx(
        surrogate.evaluate(x, orientation), rel=1e-9, abs=1e-9
    )


@pytest.mark.parametrize("cls", IMPLEMENTATIONS, ids=lambda c: c.__name__)
def test_the_ase_sign_applies_to_each_room(cls: type) -> None:
    """ASE is returned negative: the convention must hold **room by room**.

    Inverting it only globally would let through a plan where a glaring room makes up
    for a dark one.
    """
    x = _plan(4)
    orientation = Orientation(deg=200.0)
    positive = cls(target_indicator="sDA").evaluate_rooms(x, orientation)
    negative = cls(target_indicator="ASE").evaluate_rooms(x, orientation)
    assert np.allclose(negative, -positive)
    assert np.all(positive > 0.0)


@pytest.mark.parametrize("cls", IMPLEMENTATIONS, ids=lambda c: c.__name__)
def test_the_parts_are_deterministic(cls: type) -> None:
    """Two identical calls return the same vector, bit for bit."""
    surrogate = cls()
    x = _plan(5)
    orientation = Orientation(deg=17.0)
    assert np.array_equal(
        surrogate.evaluate_rooms(x, orientation),
        surrogate.evaluate_rooms(x, orientation),
    )


@pytest.mark.parametrize("cls", IMPLEMENTATIONS, ids=lambda c: c.__name__)
def test_a_larger_room_receives_more(cls: type) -> None:
    """Minimal physical consistency: enlarging a room increases its part.

    A coarse test, on purpose: it does not check the physics, it checks that the fine
    granularity did not invert a convention.
    """
    surrogate = cls()
    orientation = Orientation(deg=180.0)
    small = np.array([0.0, 0.0, 3.0, 3.0, 5.0, 0.0, 3.0, 3.0])
    large = np.array([0.0, 0.0, 6.0, 3.0, 5.0, 0.0, 3.0, 3.0])
    assert (
        surrogate.evaluate_rooms(large, orientation)[0]
        > (surrogate.evaluate_rooms(small, orientation)[0])
    )


def test_the_parts_ignore_glazing_for_the_analytic_surrogates() -> None:
    """Both analytic surrogates assume a constant glazed band: they ignore `glazing`.

    That is explicit, not accidental, and it is what earns them `R2 = -0.000` against a
    simulated irradiance.
    """
    from archlux.light.protocol import Glazing
    from archlux.types import Opening, Wall

    x = _plan(3)
    orientation = Orientation(deg=90.0)
    glazing = Glazing(
        walls=(Wall(id="m", a=(0.0, 0.0), b=(6.0, 0.0)),),
        openings=(Opening(id="f", wall_id="m", s=0.5, relative_width=0.9),),
    )
    for cls in IMPLEMENTATIONS:
        surrogate = cls()
        assert np.array_equal(
            surrogate.evaluate_rooms(x, orientation),
            surrogate.evaluate_rooms(x, orientation, glazing=glazing),
        )
