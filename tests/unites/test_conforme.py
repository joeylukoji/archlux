"""Prédiction conforme — `MILESTONE-5.md` §3. Le quantile naïf à 0,90 est interdit."""

from __future__ import annotations

import math

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from archlux.erreurs import InvariantViole
from archlux.types import BornePerformance
from archlux.uq.conforme import CalibrateurConforme, Calibration, borner, quantile_conforme


def _scores(n: int, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return np.abs(rng.normal(0.0, 1.0, size=n))


def test_correction_echantillon_fini() -> None:
    """``ceil((n+1)(1−α))`` est strictement plus large que le quantile empirique 0,90."""
    n = 100
    rng = np.random.default_rng(7)
    predictions = rng.normal(50.0, 1.0, n)
    verites = predictions + rng.normal(0.0, 1.0, n)
    incertitudes = np.ones(n)
    scores = np.abs(verites - predictions) / incertitudes
    calibrateur = CalibrateurConforme()
    calibrateur.ajuster(predictions, verites, incertitudes, alpha=0.10)
    assert calibrateur.q > float(np.quantile(scores, 0.90))
    rang = math.ceil((n + 1) * 0.90)
    assert calibrateur.q == pytest.approx(float(np.sort(scores)[rang - 1]))


def test_quantile_refuse_un_jeu_trop_petit() -> None:
    """n trop petit pour 1−α : échec explicite, pas une borne infinie."""
    with pytest.raises(InvariantViole, match="trop petit"):
        quantile_conforme(_scores(8), alpha=0.10)


def test_pas_de_borne_sans_calibration() -> None:
    """Une borne sans jeu de calibration est invérifiable."""
    with pytest.raises(InvariantViole, match="n_calibration"):
        BornePerformance(
            indicateur="sDA",
            valeur=56.2,
            borne_inf=51.4,
            borne_sup=61.0,
            couverture=0.90,
            n_calibration=0,
            regime="exchangeable",
        )


def test_sens_ase_inverse() -> None:
    """ASE publie une borne supérieure : au-dessus de la prédiction."""
    n = 80
    rng = np.random.default_rng(3)
    predictions = rng.normal(6.0, 0.4, n)
    verites = predictions + rng.normal(0.0, 0.5, n)
    incertitudes = np.ones(n)
    calibrateur = CalibrateurConforme(indicateur="ASE")
    calibrateur.ajuster(predictions, verites, incertitudes, alpha=0.10)
    borne = calibrateur.borne(6.1, 1.0, "<=", regime="exchangeable")
    assert borne.borne_sup > borne.valeur
    assert borne.indicateur == "ASE"


def test_borner_reproduit_le_quantile() -> None:
    """``borner`` s'appuie sur le même rang conforme, pas sur ``np.quantile``."""
    scores = _scores(60, seed=11)
    calibration = Calibration(
        scores=scores,
        alpha=0.10,
        indicateur="sDA",
        empreinte_jeu="test",
    )
    borne = borner(50.0, calibration, incertitude=1.0, regime="exchangeable")
    q = quantile_conforme(scores, 0.10)
    assert borne.borne_inf == pytest.approx(50.0 - q)
    assert borne.n_calibration == 60
    assert borne.couverture == pytest.approx(0.90)


@given(alpha=st.floats(min_value=0.05, max_value=0.20, allow_nan=False))
@settings(max_examples=8, deadline=None)
def test_couverture_sur_donnees_synthetiques(alpha: float) -> None:
    """Sur des données i.i.d., la couverture unilatérale tient à 1−α près 3 points."""
    rng = np.random.default_rng(17)
    n_cal, n_test = 250, 400
    pred_cal = rng.normal(40.0, 2.0, n_cal)
    sig_cal = np.full(n_cal, 1.5)
    ver_cal = pred_cal + sig_cal * rng.normal(0.0, 1.0, n_cal)
    calibrateur = CalibrateurConforme()
    calibrateur.ajuster(pred_cal, ver_cal, sig_cal, alpha=alpha)
    pred = rng.normal(40.0, 2.0, n_test)
    sig = np.full(n_test, 1.5)
    ver = pred + sig * rng.normal(0.0, 1.0, n_test)
    couvert = [
        v >= calibrateur.borne(float(p), float(s), ">=", regime="exchangeable").borne_inf
        for p, v, s in zip(pred, ver, sig, strict=True)
    ]
    assert float(np.mean(couvert)) >= 1.0 - alpha - 0.03
