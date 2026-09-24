"""Oracle gelé split-flux (`OracleSplitFlux`) — `MILESTONE-4.md` §3."""

from __future__ import annotations

import numpy as np
import pytest

from archlux.light.protocole import Substitut
from archlux.light.simulateur import OracleSplitFlux, facteur_lumiere_jour
from archlux.light.validation import valider_gradient
from archlux.types import Orientation


def test_simulateur_respecte_le_protocole() -> None:
    assert isinstance(OracleSplitFlux(), Substitut)


def test_simulation_deterministe() -> None:
    radiance = OracleSplitFlux()
    x = np.array([0.0, 0.0, 6.0, 4.5, 6.0, 0.0, 6.0, 4.5])
    ctx = Orientation(deg=40.0)
    assert radiance.evaluer(x, ctx) == radiance.evaluer(x, ctx)


def test_ase_est_l_oppose_du_sda() -> None:
    """ASE nie le score complet une fois, pas l'analytique puis le total."""
    x = np.array([0.0, 0.0, 6.0, 4.5, 6.0, 0.0, 6.0, 4.5])
    ctx = Orientation(deg=40.0)
    sda = OracleSplitFlux(indicateur_vise="sDA").evaluer(x, ctx)
    ase = OracleSplitFlux(indicateur_vise="ASE").evaluer(x, ctx)
    assert ase == pytest.approx(-sda)


def test_df_piece_canonique_dans_la_plage_bre() -> None:
    """Pièce 6 m × 4 m, WWR 30 %, sud, ciel dégagé : DF moyen typique 1–5 %."""
    df = facteur_lumiere_jour(6.0, 4.0, Orientation(deg=180.0), wwr=0.30)
    assert 0.008 <= df <= 0.05


def test_df_baisse_si_la_piece_s_approfondit() -> None:
    sud = Orientation(deg=180.0)
    peu = facteur_lumiere_jour(6.0, 4.0, sud, wwr=0.30)
    beaucoup = facteur_lumiere_jour(6.0, 8.0, sud, wwr=0.30)
    assert beaucoup < peu


def test_df_sud_vaut_mieux_que_nord() -> None:
    x_w, y_d = 6.0, 4.0
    assert facteur_lumiere_jour(x_w, y_d, Orientation(deg=180.0)) > facteur_lumiere_jour(
        x_w, y_d, Orientation(deg=0.0)
    )


def test_df_augmente_avec_le_wwr() -> None:
    sud = Orientation(deg=180.0)
    etroit = facteur_lumiere_jour(6.0, 4.0, sud, wwr=0.20)
    large = facteur_lumiere_jour(6.0, 4.0, sud, wwr=0.40)
    assert large > etroit


def test_simulateur_suit_le_wwr() -> None:
    x = np.array([0.0, 0.0, 6.0, 4.0])
    sud = Orientation(deg=180.0)
    assert OracleSplitFlux(wwr=0.40).evaluer(x, sud) > OracleSplitFlux(wwr=0.20).evaluer(x, sud)


def test_gradient_coherent_avec_le_split_flux() -> None:
    rapport = valider_gradient(
        OracleSplitFlux(),
        np.array([[0.0, 0.0, 6.0, 4.0, 6.0, 0.0, 6.0, 4.5]]),
        Orientation(deg=180.0),
        seed=17,
    )
    assert rapport.conforme
