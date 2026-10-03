"""Certificat jalon 5 : borne, duaux lisibles, rapport à deux natures."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pytest
from scipy import sparse

from archlux.certify.bound import build_bound
from archlux.certify.dual import translate_duals
from archlux.errors import InvariantViolation
from archlux.geom.polytope import Polytope
from archlux.light.objective import Daylight
from archlux.light.protocol import Surrogate
from archlux.types import (
    Certificate,
    GeometricProof,
    Manifest,
    Orientation,
    PerformanceBound,
)
from archlux.uq.conformal import Calibration
from archlux.uq.drift import DriftDiagnostic, check_drift, measure_drift
from archlux.uq.reliability import crps, reliability_diagram, stratify_by_orientation


def _poly() -> Polytope:
    return Polytope(
        A=sparse.csr_matrix(np.eye(3)),
        b=np.ones(3),
        A_eq=sparse.csr_matrix((0, 3)),
        b_eq=np.zeros(0),
        bounds=((0.0, 1.0),) * 3,
        index={"a.x": 0, "a.y": 1, "a.w": 2},
        origins=(
            "mur porteur axe 3",
            "surface minimale cuisine",
            "largeur de passage",
        ),
    )


def _preuve() -> GeometricProof:
    return GeometricProof(
        valid=True,
        overlap=False,
        gaps=False,
        areas_ok=True,
        structure_kept=True,
        max_displacement=0.18,
    )


def test_le_diagnostic_est_lisible() -> None:
    duaux = np.array([-4.1, -1.7, 0.0])
    phrases = translate_duals(duaux, _poly())
    assert all(len(libelle) > 20 for libelle, _prix in phrases)
    assert all("small changes" in libelle for libelle, _prix in phrases)


def test_prix_nul_pour_contrainte_non_active() -> None:
    duaux = np.array([-4.1, 0.0, 1e-9])
    phrases = translate_duals(duaux, _poly())
    assert all(prix != 0.0 for _libelle, prix in phrases)
    assert len(phrases) == 1


def test_duaux_tries_par_cout_absolu() -> None:
    duaux = np.array([-1.0, 5.0, -3.0])
    phrases = translate_duals(duaux, _poly())
    assert [abs(p) for _, p in phrases] == [5.0, 3.0, 1.0]


def test_certificat_separe_les_natures() -> None:
    borne = PerformanceBound(
        indicator="sDA",
        value=56.2,
        lower=51.4,
        upper=61.0,
        coverage=0.90,
        n_calibration=1284,
        regime="exchangeable",
    )
    texte = Certificate(
        geometry=_preuve(),
        performance=borne,
        duals=(("mur porteur axe 3 : relâchement", -4.1),),
        manifest=Manifest(version="0.4.0", timestamp="2026-09-09T00:00:00Z", seed=17),
    ).report()
    assert "[EXACT]" in texte and "[PREDICTION" in texte
    assert "1284" in texte
    assert "NOT EVALUABLE" in texte


def test_non_evaluable_toujours_present() -> None:
    texte = Certificate(geometry=_preuve()).report()
    assert "NOT EVALUABLE" in texte
    assert "[PREDICTION" in texte


def test_construire_borne_refuse_la_derive() -> None:
    scores = np.abs(np.random.default_rng(0).normal(0.0, 1.0, 40))
    calibration = Calibration(scores, 0.10, "sDA", "abc")
    derive = DriftDiagnostic(
        echangeable=False,
        statistique=0.4,
        threshold=0.05,
        n_observations=20,
        message="dérive",
    )
    assert build_bound(50.0, calibration, derive, uncertainty=1.0, regime="exchangeable") is None
    ok = DriftDiagnostic(True, 0.05, 0.05, 20, "ok")
    borne = build_bound(50.0, calibration, ok, uncertainty=1.0, regime="exchangeable")
    assert borne is not None
    assert borne.n_calibration == 40


def test_controler_derive_detecte_un_decalage() -> None:
    rng = np.random.default_rng(4)
    cal = Calibration(np.abs(rng.normal(0.0, 1.0, 80)), 0.10, "sDA", "c")
    memes = np.abs(rng.normal(0.0, 1.0, 80))
    assert check_drift(memes, cal, seed=17).echangeable
    decales = np.abs(rng.normal(3.0, 1.0, 80))
    assert not check_drift(decales, cal, seed=17).echangeable


def test_mesurer_derive_positive_si_surestimation() -> None:
    pred = np.array([10.0, 11.0, 12.0, 13.0])
    verite = np.array([9.0, 10.0, 11.0, 12.0])
    rapport = measure_drift(pred, verite, seed=1)
    assert rapport.derive_moyenne == pytest.approx(1.0)
    assert rapport.n_echantillons == 4


def test_crps_parfait_est_petit() -> None:
    y = np.array([0.0, 0.0, 0.0, 0.0])
    mu = y.copy()
    sigma = np.ones(4)
    assert crps(mu, y, sigma) < crps(mu + 2.0, y, sigma)


def test_diagramme_fiabilite_est_un_tableau() -> None:
    rng = np.random.default_rng(2)
    mu = rng.normal(0.0, 1.0, 80)
    y = mu + rng.normal(0.0, 1.0, 80)
    sigma = np.ones(80)
    grille = reliability_diagram(mu, y, sigma, niveaux=np.array([0.80, 0.90]))
    assert grille.shape == (2, 2)
    assert grille[0, 0] == pytest.approx(0.80)


def test_stratifier_huit_secteurs() -> None:
    degres = np.array([0.0, 45.0, 90.0, 180.0, 359.0])
    bacs = stratify_by_orientation(degres)
    assert set(bacs) == set(range(8))
    assert 0 in bacs[0]
    assert 4 in bacs[7]


@dataclass
class _FauxSubstitut:
    mu: float
    sigma: float
    indicator: str = "sDA"

    def evaluate(self, x: np.ndarray, orientation: Orientation, *, glazing: object = None) -> float:
        return self.mu

    def gradient(
        self, x: np.ndarray, orientation: Orientation, *, glazing: object = None
    ) -> np.ndarray:
        return np.zeros_like(x, dtype=float)

    def uncertainty(
        self, x: np.ndarray, orientation: Orientation, *, glazing: object = None
    ) -> float:
        return self.sigma


def test_pessimiste_penalise_l_incertitude() -> None:
    """À prédiction égale, le plan le plus incertain a un objectif plus bas."""
    orientation = Orientation(deg=180.0)
    x = np.ones(4)
    certain = Daylight(_FauxSubstitut(50.0, 0.2), q_chapeau=1.64, pessimiste=True)
    incertain = Daylight(_FauxSubstitut(50.0, 2.0), q_chapeau=1.64, pessimiste=True)
    assert certain.evaluate(x, orientation) > incertain.evaluate(x, orientation)
    assert isinstance(certain, Surrogate)


def test_daylight_sans_pessimisme_ignore_sigma() -> None:
    orientation = Orientation(deg=0.0)
    x = np.ones(2)
    j = Daylight(_FauxSubstitut(40.0, 9.0), q_chapeau=2.0, pessimiste=False)
    assert j.evaluate(x, orientation) == pytest.approx(40.0)


def test_reliability_diagram_rejects_levels_outside_unit_interval() -> None:
    """A level outside ]0, 1[ is a caller error, not a ``nan`` row."""
    mu, y, sigma = np.zeros(50), np.linspace(-1.0, 1.0, 50), np.ones(50)
    with pytest.raises(InvariantViolation):
        reliability_diagram(mu, y, sigma, niveaux=np.array([1.5, -0.2]))


def test_reliability_diagram_rejects_non_finite_truths() -> None:
    """A ``nan`` truth makes the reference scores non-finite: raise, never a ``nan`` grid."""
    mu, y, sigma = np.zeros(50), np.linspace(-1.0, 1.0, 50), np.ones(50)
    y[3] = np.nan
    with pytest.raises(InvariantViolation):
        reliability_diagram(mu, y, sigma, niveaux=np.array([0.8]))


def test_reliability_diagram_keeps_nan_only_for_too_small_n() -> None:
    """The documented sentinel survives: a level too demanding for ``n`` gives ``nan``."""
    mu, y, sigma = np.zeros(5), np.linspace(-1.0, 1.0, 5), np.ones(5)
    grille = reliability_diagram(mu, y, sigma, niveaux=np.array([0.5, 0.99]))
    assert np.isfinite(grille[0, 1])
    assert np.isnan(grille[1, 1])
