"""Certificat jalon 5 : borne, duaux lisibles, rapport à deux natures."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pytest
from scipy import sparse

from archlux.certify.borne import construire_borne
from archlux.certify.dual import traduire_duaux
from archlux.geom.polytope import Polytope
from archlux.light.objectif import Daylight
from archlux.light.protocole import Substitut
from archlux.types import (
    BornePerformance,
    Certificat,
    Manifeste,
    Orientation,
    PreuveGeometrique,
)
from archlux.uq.conforme import Calibration
from archlux.uq.derive import DiagnosticDerive, controler_derive, mesurer_derive
from archlux.uq.fiabilite import crps, diagramme_fiabilite, stratifier_par_orientation


def _poly() -> Polytope:
    return Polytope(
        A=sparse.csr_matrix(np.eye(3)),
        b=np.ones(3),
        A_eq=sparse.csr_matrix((0, 3)),
        b_eq=np.zeros(0),
        bornes=((0.0, 1.0),) * 3,
        index={"a.x": 0, "a.y": 1, "a.w": 2},
        origines=(
            "mur porteur axe 3",
            "surface minimale cuisine",
            "largeur de passage",
        ),
    )


def _preuve() -> PreuveGeometrique:
    return PreuveGeometrique(
        valide=True,
        chevauchement=False,
        jours=False,
        surfaces_ok=True,
        structure_preservee=True,
        deplacement_max=0.18,
    )


def test_le_diagnostic_est_lisible() -> None:
    duaux = np.array([-4.1, -1.7, 0.0])
    phrases = traduire_duaux(duaux, _poly())
    assert all(len(libelle) > 20 for libelle, _prix in phrases)
    assert all("validité locale" in libelle for libelle, _prix in phrases)


def test_prix_nul_pour_contrainte_non_active() -> None:
    duaux = np.array([-4.1, 0.0, 1e-9])
    phrases = traduire_duaux(duaux, _poly())
    assert all(prix != 0.0 for _libelle, prix in phrases)
    assert len(phrases) == 1


def test_duaux_tries_par_cout_absolu() -> None:
    duaux = np.array([-1.0, 5.0, -3.0])
    phrases = traduire_duaux(duaux, _poly())
    assert [abs(p) for _, p in phrases] == [5.0, 3.0, 1.0]


def test_certificat_separe_les_natures() -> None:
    borne = BornePerformance(
        indicateur="sDA",
        valeur=56.2,
        borne_inf=51.4,
        borne_sup=61.0,
        couverture=0.90,
        n_calibration=1284,
    )
    texte = Certificat(
        geometrie=_preuve(),
        performance=borne,
        duaux=(("mur porteur axe 3 : relâchement", -4.1),),
        manifeste=Manifeste(version="0.4.0", horodatage="2026-09-09T00:00:00Z", graine=17),
    ).rapport()
    assert "[EXACT]" in texte and "[PREDICTION" in texte
    assert "1284" in texte
    assert "NON EVALUABLE" in texte


def test_non_evaluable_toujours_present() -> None:
    texte = Certificat(geometrie=_preuve()).rapport()
    assert "NON EVALUABLE" in texte
    assert "[PREDICTION" in texte


def test_construire_borne_refuse_la_derive() -> None:
    scores = np.abs(np.random.default_rng(0).normal(0.0, 1.0, 40))
    calibration = Calibration(scores, 0.10, "sDA", "abc")
    derive = DiagnosticDerive(
        echangeable=False,
        statistique=0.4,
        seuil=0.05,
        n_observations=20,
        message="dérive",
    )
    assert construire_borne(50.0, calibration, derive) is None
    ok = DiagnosticDerive(True, 0.05, 0.05, 20, "ok")
    borne = construire_borne(50.0, calibration, ok)
    assert borne is not None
    assert borne.n_calibration == 40


def test_controler_derive_detecte_un_decalage() -> None:
    rng = np.random.default_rng(4)
    cal = Calibration(np.abs(rng.normal(0.0, 1.0, 80)), 0.10, "sDA", "c")
    memes = np.abs(rng.normal(0.0, 1.0, 80))
    assert controler_derive(memes, cal, seed=17).echangeable
    decales = np.abs(rng.normal(3.0, 1.0, 80))
    assert not controler_derive(decales, cal, seed=17).echangeable


def test_mesurer_derive_positive_si_surestimation() -> None:
    pred = np.array([10.0, 11.0, 12.0, 13.0])
    verite = np.array([9.0, 10.0, 11.0, 12.0])
    rapport = mesurer_derive(pred, verite, seed=1)
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
    grille = diagramme_fiabilite(mu, y, sigma, niveaux=np.array([0.80, 0.90]))
    assert grille.shape == (2, 2)
    assert grille[0, 0] == pytest.approx(0.80)


def test_stratifier_huit_secteurs() -> None:
    degres = np.array([0.0, 45.0, 90.0, 180.0, 359.0])
    bacs = stratifier_par_orientation(degres)
    assert set(bacs) == set(range(8))
    assert 0 in bacs[0]
    assert 4 in bacs[7]


@dataclass
class _FauxSubstitut:
    mu: float
    sigma: float
    indicateur: str = "sDA"

    def evaluer(self, x: np.ndarray, orientation: Orientation, *, baies: object = None) -> float:
        return self.mu

    def gradient(
        self, x: np.ndarray, orientation: Orientation, *, baies: object = None
    ) -> np.ndarray:
        return np.zeros_like(x, dtype=float)

    def incertitude(
        self, x: np.ndarray, orientation: Orientation, *, baies: object = None
    ) -> float:
        return self.sigma


def test_pessimiste_penalise_l_incertitude() -> None:
    """À prédiction égale, le plan le plus incertain a un objectif plus bas."""
    orientation = Orientation(deg=180.0)
    x = np.ones(4)
    certain = Daylight(_FauxSubstitut(50.0, 0.2), q_chapeau=1.64, pessimiste=True)
    incertain = Daylight(_FauxSubstitut(50.0, 2.0), q_chapeau=1.64, pessimiste=True)
    assert certain.evaluer(x, orientation) > incertain.evaluer(x, orientation)
    assert isinstance(certain, Substitut)


def test_daylight_sans_pessimisme_ignore_sigma() -> None:
    orientation = Orientation(deg=0.0)
    x = np.ones(2)
    j = Daylight(_FauxSubstitut(40.0, 9.0), q_chapeau=2.0, pessimiste=False)
    assert j.evaluer(x, orientation) == pytest.approx(40.0)
