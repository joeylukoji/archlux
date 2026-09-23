"""Statistiques circulaires — `MILESTONE-3.md` §2."""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from archlux.orient.circulaire import (
    concentration,
    difference_angulaire,
    encode,
    encoder,
    moyenne_circulaire,
    rayleigh,
    regression_circulaire_lineaire,
    stratifier,
    variance_circulaire,
)
from archlux.types import Orientation


def test_moyenne_circulaire_franchit_zero() -> None:
    """Le piège classique : la moyenne de 350° et 10° vaut 0°, pas 180°."""
    assert moyenne_circulaire([350.0, 10.0]) == pytest.approx(0.0, abs=0.1)


def test_moyenne_de_valeurs_identiques() -> None:
    assert moyenne_circulaire([40.0, 40.0, 40.0]) == pytest.approx(40.0, abs=1e-6)


@given(deg=st.floats(-720.0, 720.0, allow_nan=False, allow_infinity=False))
@settings(max_examples=50)
def test_encode_periodique(deg: float) -> None:
    """``encode(θ)`` = ``encode(θ + 360)`` : jamais le degré brut."""
    assert np.allclose(encode(deg), encode(deg + 360.0), atol=1e-9)


def test_encoder_enveloppe_orientation() -> None:
    assert np.allclose(
        encoder(Orientation(deg=90.0), harmoniques=1),
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
    assert variance_circulaire([12.0, 12.0, 12.0]) == pytest.approx(0.0, abs=1e-9)


def test_concentration_dans_zero_un() -> None:
    valeur = concentration([0.0, 180.0])
    assert 0.0 <= valeur <= 1.0


def test_difference_angulaire_signee() -> None:
    assert difference_angulaire(10.0, 350.0) == pytest.approx(20.0, abs=1e-9)
    assert difference_angulaire(350.0, 10.0) == pytest.approx(-20.0, abs=1e-9)


def test_regression_retrouve_un_cosinus() -> None:
    """y = 2 cos θ + 1, sans bruit : les coefficients se lisent."""
    theta = np.array([0.0, 90.0, 180.0, 270.0])
    y = 2.0 * np.cos(np.radians(theta)) + 1.0
    fit = regression_circulaire_lineaire(theta, y)
    assert fit.a == pytest.approx(2.0, abs=1e-9)
    assert fit.b == pytest.approx(0.0, abs=1e-9)
    assert fit.c == pytest.approx(1.0, abs=1e-9)


def test_stratifier_huit_secteurs() -> None:
    degres = np.array([0.0, 10.0, 90.0, 180.0])
    groupes = stratifier(degres)
    assert set(groupes) == {"N", "NE", "E", "SE", "S", "SW", "W", "NW"}
    assert groupes["N"].tolist() == pytest.approx([0.0, 10.0])
    assert groupes["E"].tolist() == pytest.approx([90.0])
    assert groupes["S"].tolist() == pytest.approx([180.0])
