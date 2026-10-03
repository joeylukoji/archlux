"""Statistiques circulaires — `MILESTONE-3.md` §2."""

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


def test_moyenne_circulaire_franchit_zero() -> None:
    """Le piège classique : la moyenne de 350° et 10° vaut 0°, pas 180°."""
    assert circular_mean([350.0, 10.0]) == pytest.approx(0.0, abs=0.1)


def test_moyenne_de_valeurs_identiques() -> None:
    assert circular_mean([40.0, 40.0, 40.0]) == pytest.approx(40.0, abs=1e-6)


@given(deg=st.floats(-720.0, 720.0, allow_nan=False, allow_infinity=False))
@settings(max_examples=50)
def test_encode_periodique(deg: float) -> None:
    """``encode(θ)`` = ``encode(θ + 360)`` : jamais le degré brut."""
    assert np.allclose(encode(deg), encode(deg + 360.0), atol=1e-9)


def test_encoder_enveloppe_orientation() -> None:
    assert np.allclose(
        encode_orientation(Orientation(deg=90.0), harmoniques=1),
        encode(90.0, harmoniques=1),
    )


def test_rayleigh_detecte_concentration() -> None:
    _, p_valeur = rayleigh([10.0, 12.0, 11.0, 9.0, 13.0])
    assert p_valeur < 0.01


def test_rayleigh_uniforme_ne_rejette_pas() -> None:
    """Huit secteurs également remplis : on ne rejette pas l'uniformité."""
    rose = [0.0, 45.0, 90.0, 135.0, 180.0, 225.0, 270.0, 315.0]
    _, p_valeur = rayleigh(rose)
    assert p_valeur > 0.1


def test_variance_nulle_si_identiques() -> None:
    assert circular_variance([12.0, 12.0, 12.0]) == pytest.approx(0.0, abs=1e-9)


def test_concentration_dans_zero_un() -> None:
    value = concentration([0.0, 180.0])
    assert 0.0 <= value <= 1.0


def test_difference_angulaire_signee() -> None:
    assert angular_difference(10.0, 350.0) == pytest.approx(20.0, abs=1e-9)
    assert angular_difference(350.0, 10.0) == pytest.approx(-20.0, abs=1e-9)


def test_regression_retrouve_un_cosinus() -> None:
    """y = 2 cos θ + 1, sans bruit : les coefficients se lisent."""
    theta = np.array([0.0, 90.0, 180.0, 270.0])
    y = 2.0 * np.cos(np.radians(theta)) + 1.0
    fit = circular_linear_regression(theta, y)
    assert fit.a == pytest.approx(2.0, abs=1e-9)
    assert fit.b == pytest.approx(0.0, abs=1e-9)
    assert fit.c == pytest.approx(1.0, abs=1e-9)


def test_stratifier_huit_secteurs() -> None:
    degres = np.array([0.0, 10.0, 90.0, 180.0])
    groupes = stratify(degres)
    assert set(groupes) == {"N", "NE", "E", "SE", "S", "SW", "W", "NW"}
    assert groupes["N"].tolist() == pytest.approx([0.0, 10.0])
    assert groupes["E"].tolist() == pytest.approx([90.0])
    assert groupes["S"].tolist() == pytest.approx([180.0])


def test_sector_centered_matches_stratify() -> None:
    """PLAN.md phase 4, block 7, item 24: `stratify` names what `sector` indexes."""
    degres = np.array([0.0, 10.0, 90.0, 180.0, 350.0])
    groupes = stratify(degres, n_secteurs=8)
    noms = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
    for angle in degres:
        idx = int(sector(angle, 8))
        assert angle in groupes[noms[idx]]


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
    degres = np.linspace(0.0, 360.0, 7201, endpoint=False)
    attendu = np.empty(degres.size, dtype=int)
    for k, idx in stratify_by_orientation(degres, n_secteurs=n_sectors).items():
        attendu[idx] = k
    assert sector(degres, n_sectors=n_sectors, center=False).tolist() == attendu.tolist()
