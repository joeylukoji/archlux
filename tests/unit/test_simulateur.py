"""Oracle gelé split-flux (`SplitFluxOracle`) — `MILESTONE-4.md` §3."""

from __future__ import annotations

import numpy as np
import pytest

from archlux.light.protocol import Surrogate
from archlux.light.split_flux import SplitFluxOracle, daylight_factor
from archlux.light.validation import validate_gradient
from archlux.types import Orientation


def test_simulateur_respecte_le_protocole() -> None:
    assert isinstance(SplitFluxOracle(), Surrogate)


def test_simulation_deterministe() -> None:
    radiance = SplitFluxOracle()
    x = np.array([0.0, 0.0, 6.0, 4.5, 6.0, 0.0, 6.0, 4.5])
    ctx = Orientation(deg=40.0)
    assert radiance.evaluate(x, ctx) == radiance.evaluate(x, ctx)


def test_ase_est_l_oppose_du_sda() -> None:
    """ASE nie le score complet une fois, pas l'analytique puis le total."""
    x = np.array([0.0, 0.0, 6.0, 4.5, 6.0, 0.0, 6.0, 4.5])
    ctx = Orientation(deg=40.0)
    sda = SplitFluxOracle(indicateur_vise="sDA").evaluate(x, ctx)
    ase = SplitFluxOracle(indicateur_vise="ASE").evaluate(x, ctx)
    assert ase == pytest.approx(-sda)


def test_df_piece_canonique_dans_la_plage_bre() -> None:
    """Pièce 6 m × 4 m, WWR 30 %, sud, ciel dégagé : DF moyen typique 1–5 %."""
    df = daylight_factor(6.0, 4.0, Orientation(deg=180.0), wwr=0.30)
    assert 0.008 <= df <= 0.05


def test_df_baisse_si_la_piece_s_approfondit() -> None:
    sud = Orientation(deg=180.0)
    peu = daylight_factor(6.0, 4.0, sud, wwr=0.30)
    beaucoup = daylight_factor(6.0, 8.0, sud, wwr=0.30)
    assert beaucoup < peu


def test_df_sud_vaut_mieux_que_nord() -> None:
    x_w, y_d = 6.0, 4.0
    assert daylight_factor(x_w, y_d, Orientation(deg=180.0)) > daylight_factor(
        x_w, y_d, Orientation(deg=0.0)
    )


def test_df_augmente_avec_le_wwr() -> None:
    sud = Orientation(deg=180.0)
    etroit = daylight_factor(6.0, 4.0, sud, wwr=0.20)
    large = daylight_factor(6.0, 4.0, sud, wwr=0.40)
    assert large > etroit


def test_simulateur_suit_le_wwr() -> None:
    x = np.array([0.0, 0.0, 6.0, 4.0])
    sud = Orientation(deg=180.0)
    assert SplitFluxOracle(wwr=0.40).evaluate(x, sud) > SplitFluxOracle(wwr=0.20).evaluate(x, sud)


def test_gradient_coherent_avec_le_split_flux() -> None:
    rapport = validate_gradient(
        SplitFluxOracle(),
        np.array([[0.0, 0.0, 6.0, 4.0, 6.0, 0.0, 6.0, 4.5]]),
        Orientation(deg=180.0),
        seed=17,
    )
    assert rapport.conforme
