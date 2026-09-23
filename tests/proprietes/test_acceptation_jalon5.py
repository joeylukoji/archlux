"""Critère d'acceptation du jalon 5 : couverture sur le jeu de TEST.

L'oracle est ``SimulateurExact`` (split-flux), pas un moteur de lancer de rayons.
La garantie porte sur cet oracle gelé (`ARCHITECTURE.md` §2).
"""

from __future__ import annotations

import numpy as np

from archlux.light.analytique import SubstitutAnalytique
from archlux.light.simulateur import SimulateurExact
from archlux.types import Orientation
from archlux.uq.conforme import CalibrateurConforme
from archlux.uq.fiabilite import stratifier_par_orientation


def _tirer(
    rng: np.random.Generator, n: int
) -> tuple[list[np.ndarray], list[Orientation]]:
    xs: list[np.ndarray] = []
    os_: list[Orientation] = []
    for _ in range(n):
        largeur = float(rng.uniform(4.0, 8.0))
        xs.append(np.array([0.0, 0.0, largeur, 4.5, largeur, 0.0, 12.0 - largeur, 4.5]))
        os_.append(Orientation(deg=float(rng.uniform(0.0, 360.0))))
    return xs, os_


def _evaluer(
    modele: SubstitutAnalytique,
    oracle: SimulateurExact,
    xs: list[np.ndarray],
    os_: list[Orientation],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    pred = np.array([modele.evaluer(x, o) for x, o in zip(xs, os_, strict=True)])
    verite = np.array([oracle.evaluer(x, o) for x, o in zip(xs, os_, strict=True)])
    sigma = np.array([modele.incertitude(x, o) for x, o in zip(xs, os_, strict=True)])
    return pred, verite, sigma


def test_couverture_empirique() -> None:
    """Sur le jeu de TEST, jamais sur celui de calibration. Visée 0,90 ± 4 pts."""
    rng = np.random.default_rng(17)
    modele = SubstitutAnalytique()
    oracle = SimulateurExact()
    xs_cal, os_cal = _tirer(rng, 220)
    xs_test, os_test = _tirer(rng, 280)
    p_cal, v_cal, s_cal = _evaluer(modele, oracle, xs_cal, os_cal)
    calibrateur = CalibrateurConforme()
    calibrateur.ajuster(p_cal, v_cal, s_cal, alpha=0.10)
    p_test, v_test, s_test = _evaluer(modele, oracle, xs_test, os_test)
    # Couverture d'intervalle (les deux côtés) : « la borne haute compte autant ».
    ok = []
    for pred, verite, sigma in zip(p_test, v_test, s_test, strict=True):
        borne = calibrateur.borne(float(pred), float(sigma), ">=")
        ok.append(borne.borne_inf <= verite <= borne.borne_sup)
    couv = float(np.mean(ok))
    assert 0.86 <= couv <= 0.94, f"couverture test = {couv:.3f}"


def test_calibration_tient_par_orientation() -> None:
    """Huit secteurs : la couverture ne doit pas s'effondrer au nord seulement."""
    rng = np.random.default_rng(21)
    n = 1600
    mu = rng.normal(40.0, 2.0, n)
    sigma = np.full(n, 1.5)
    y = mu + sigma * rng.normal(0.0, 1.0, n)
    degres = rng.uniform(0.0, 360.0, n)
    cal = slice(0, 800)
    test = slice(800, 1600)
    calibrateur = CalibrateurConforme()
    calibrateur.ajuster(mu[cal], y[cal], sigma[cal], alpha=0.10)
    bacs = stratifier_par_orientation(degres[test])
    for secteur, idx_rel in bacs.items():
        if idx_rel.size < 40:
            continue
        idx = idx_rel + 800
        ok = []
        for i in idx:
            borne = calibrateur.borne(float(mu[i]), float(sigma[i]), ">=")
            ok.append(borne.borne_inf <= y[i] <= borne.borne_sup)
        couv = float(np.mean(ok))
        assert 0.84 <= couv <= 0.96, f"secteur {secteur} : {couv:.3f}"


def test_derive_bornee_sur_oracle_gelé() -> None:
    """L'analytique ne dérive pas de façon explosive contre le split-flux i.i.d."""
    from archlux.uq.derive import mesurer_derive

    rng = np.random.default_rng(9)
    modele = SubstitutAnalytique()
    oracle = SimulateurExact()
    xs, os_ = _tirer(rng, 40)
    pred, verite, _sigma = _evaluer(modele, oracle, xs, os_)
    rapport = mesurer_derive(pred, verite, seed=9)
    amplitude = float(np.std(verite) + 1e-9)
    assert abs(rapport.derive_moyenne) < 3.0 * amplitude
    assert rapport.tendance_pvalue > 0.05 or rapport.tendance_pente <= 0.0
