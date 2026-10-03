"""Circular statistics: `MILESTONE-3.md` §2."""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from archlux.errors import InvalidInput
from archlux.orient.circular import (
    angular_difference,
    circular_linear_regression,
    circular_mean,
    circular_variance,
    concentration,
    encode,
    encode_orientation,
    rayleigh,
    sector,
    stratify,
)
from archlux.types import Orientation
from archlux.uq.reliability import stratify_by_orientation


def test_circular_mean_crosses_zero() -> None:
    """The classic trap: the mean of 350° and 10° is 0°, not 180°."""
    assert circular_mean([350.0, 10.0]) == pytest.approx(0.0, abs=0.1)


def test_mean_of_identical_values() -> None:
    assert circular_mean([40.0, 40.0, 40.0]) == pytest.approx(40.0, abs=1e-6)


@given(deg=st.floats(-720.0, 720.0, allow_nan=False, allow_infinity=False))
@settings(max_examples=50)
def test_periodic_encode(deg: float) -> None:
    """``encode(θ)`` = ``encode(θ + 360)``: never the raw degree."""
    assert np.allclose(encode(deg), encode(deg + 360.0), atol=1e-9)


def test_encode_orientation_wraps_encode() -> None:
    assert np.allclose(
        encode_orientation(Orientation(deg=90.0), harmonics=1),
        encode(90.0, harmonics=1),
    )


def test_rayleigh_detects_concentration() -> None:
    _, p_value = rayleigh([10.0, 12.0, 11.0, 9.0, 13.0])
    assert p_value < 0.01


def test_uniform_rayleigh_does_not_reject() -> None:
    """Eight equally filled sectors: uniformity is not rejected."""
    rose = [0.0, 45.0, 90.0, 135.0, 180.0, 225.0, 270.0, 315.0]
    _, p_value = rayleigh(rose)
    assert p_value > 0.1


def test_zero_variance_if_identical() -> None:
    assert circular_variance([12.0, 12.0, 12.0]) == pytest.approx(0.0, abs=1e-9)


def test_concentration_in_zero_one() -> None:
    value = concentration([0.0, 180.0])
    assert 0.0 <= value <= 1.0


def test_signed_angular_difference() -> None:
    assert angular_difference(10.0, 350.0) == pytest.approx(20.0, abs=1e-9)
    assert angular_difference(350.0, 10.0) == pytest.approx(-20.0, abs=1e-9)


def test_regression_recovers_a_cosine() -> None:
    """y = 2 cos θ + 1, without noise: the coefficients can be read off."""
    theta = np.array([0.0, 90.0, 180.0, 270.0])
    y = 2.0 * np.cos(np.radians(theta)) + 1.0
    fit = circular_linear_regression(theta, y)
    assert fit.a == pytest.approx(2.0, abs=1e-9)
    assert fit.b == pytest.approx(0.0, abs=1e-9)
    assert fit.c == pytest.approx(1.0, abs=1e-9)


def test_stratify_eight_sectors() -> None:
    degrees = np.array([0.0, 10.0, 90.0, 180.0])
    groups = stratify(degrees)
    assert set(groups) == {"N", "NE", "E", "SE", "S", "SW", "W", "NW"}
    assert groups["N"].tolist() == pytest.approx([0.0, 10.0])
    assert groups["E"].tolist() == pytest.approx([90.0])
    assert groups["S"].tolist() == pytest.approx([180.0])


def test_sector_centered_matches_stratify() -> None:
    """PLAN.md phase 4, block 7, item 24: `stratify` names what `sector` indexes."""
    degrees = np.array([0.0, 10.0, 90.0, 180.0, 350.0])
    groups = stratify(degrees, n_sectors=8)
    names = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
    for angle in degrees:
        idx = int(sector(angle, 8))
        assert angle in groups[names[idx]]


def test_sector_edge_aligned_starts_at_zero() -> None:
    assert sector(0.0, 4, center=False).item() == 0
    assert sector(44.0, 4, center=False).item() == 0
    assert sector(90.0, 4, center=False).item() == 1
    assert sector(359.0, 4, center=False).item() == 3


def test_sector_wraps_negative_and_over_360_degrees() -> None:
    assert sector(-10.0, 8).item() == sector(350.0, 8).item()
    assert sector(370.0, 8).item() == sector(10.0, 8).item()


def test_sector_is_vectorized() -> None:
    result = sector(np.array([0.0, 90.0, 180.0, 270.0]), 4, center=False)
    assert result.tolist() == [0, 1, 2, 3]


@pytest.mark.parametrize("n_sectors", [0, -1, 2.5, True])
def test_sector_rejects_invalid_sector_count(n_sectors: object) -> None:
    with pytest.raises(InvalidInput, match="n_sectors"):
        sector(1.0, n_sectors)  # type: ignore[arg-type]


@pytest.mark.parametrize("n_sectors", [2, 4, 8, 12, 16])
def test_sector_edge_aligned_matches_uq_copy(n_sectors: int) -> None:
    """`uq` keeps its own edge-aligned copy (layering); both must partition alike."""
    degrees = np.linspace(0.0, 360.0, 7201, endpoint=False)
    expected = np.empty(degrees.size, dtype=int)
    for k, idx in stratify_by_orientation(degrees, n_sectors=n_sectors).items():
        expected[idx] = k
    assert sector(degrees, n_sectors=n_sectors, center=False).tolist() == expected.tolist()
