"""Substitut analytique — `MILESTONE-3.md` §4. Entrée vectorielle uniquement."""

from __future__ import annotations

import numpy as np
import pytest

from archlux.light.analytique import SubstitutAnalytique
from archlux.light.protocole import Substitut
from archlux.types import Orientation


def test_satisfait_le_protocole() -> None:
    assert isinstance(SubstitutAnalytique(), Substitut)


def test_piece_plus_au_sud_est_mieux_exposee() -> None:
    """À orientation 0° (axe y vers le nord), une pièce de plus petit y est plus au sud."""
    substitut = SubstitutAnalytique()
    nord = Orientation(deg=0.0)
    au_sud = np.array([0.0, 0.0, 4.0, 4.0])
    au_nord = np.array([0.0, 6.0, 4.0, 4.0])
    assert substitut.evaluer(au_sud, nord) > substitut.evaluer(au_nord, nord)


def test_sud_vaut_mieux_que_nord_a_geometrie_egale() -> None:
    """La règle de profondeur utile est modulée par le secteur (8 pas de 45°)."""
    substitut = SubstitutAnalytique()
    x = np.array([0.0, 0.0, 4.0, 5.0])
    assert substitut.evaluer(x, Orientation(deg=180.0)) > substitut.evaluer(x, Orientation(deg=0.0))


def test_gradient_coherent_avec_differences_finies() -> None:
    substitut = SubstitutAnalytique()
    x = np.array([1.0, 2.0, 4.0, 5.0, 5.0, 2.0, 3.0, 5.0])
    orientation = Orientation(deg=135.0)
    analytique = substitut.gradient(x, orientation)
    pas = 1e-6
    numerique = np.empty_like(x)
    for i in range(x.size):
        plus, moins = x.copy(), x.copy()
        plus[i] += pas
        moins[i] -= pas
        numerique[i] = (
            substitut.evaluer(plus, orientation) - substitut.evaluer(moins, orientation)
        ) / (2.0 * pas)
    assert np.allclose(analytique, numerique, rtol=1e-4, atol=1e-5)


def test_facade_plus_large_donne_plus_de_lumiere() -> None:
    """Analogie vectorielle de « plus de baie » : une façade sud plus large éclaire plus."""
    substitut = SubstitutAnalytique()
    sud = Orientation(deg=180.0)
    etroite = np.array([0.0, 0.0, 3.0, 4.0])
    large = np.array([0.0, 0.0, 6.0, 4.0])
    assert substitut.evaluer(large, sud) > substitut.evaluer(etroite, sud)


def test_piece_profonde_sature() -> None:
    """Au-delà de 2,5 fois le linteau au sud, approfondir n'ajoute plus de lumière."""
    substitut = SubstitutAnalytique()
    sud = Orientation(deg=180.0)
    peu_profond = np.array([0.0, 0.0, 4.0, 6.0])
    plus_profond = np.array([0.0, 0.0, 4.0, 9.0])
    assert substitut.evaluer(plus_profond, sud) <= substitut.evaluer(peu_profond, sud) + 1e-9


def test_incertitude_constante_documentee() -> None:
    substitut = SubstitutAnalytique(sigma_nominal=0.08)
    x = np.ones(4)
    assert substitut.incertitude(x, Orientation(deg=0.0)) == pytest.approx(0.08)


def test_indicateur_suit_le_viseur() -> None:
    assert SubstitutAnalytique(indicateur_vise="ASE").indicateur == "ASE"
