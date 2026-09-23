"""Jeton de calibration — `MILESTONE-4.md` §2. Sans jeton, le jeu reste fermé."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from archlux.erreurs import CalibrationVerrouillee, ModeleModifie
from archlux.uq.gestion import (
    GestionDonnees,
    emettre_jeton,
    geler_et_emettre,
    ouvrir_calibration,
)


def test_emettre_jeton_est_deterministe() -> None:
    a = emettre_jeton("abc", "2026-01-01T00:00:00Z")
    b = emettre_jeton("abc", "2026-01-01T00:00:00Z")
    assert a == b
    assert a.signature != emettre_jeton("abc", "2026-01-02T00:00:00Z").signature


def test_ouvrir_calibration_sans_jeton_valide_leve(tmp_path: Path) -> None:
    (tmp_path / "calibration").mkdir()
    faux = emettre_jeton("poids", "2026-01-01T00:00:00Z")
    from dataclasses import replace

    with pytest.raises(CalibrationVerrouillee):
        ouvrir_calibration(tmp_path, replace(faux, signature="0" * 16))


def test_pour_entrainement_ne_voit_pas_la_calibration(tmp_path: Path) -> None:
    (tmp_path / "train").mkdir()
    (tmp_path / "train" / "a.json").write_text("{}", encoding="utf-8")
    (tmp_path / "calibration").mkdir()
    (tmp_path / "calibration" / "secret.json").write_text("{}", encoding="utf-8")
    (tmp_path / "test").mkdir()
    gestion = GestionDonnees(tmp_path)
    noms = {p.name for p in gestion.pour_entrainement().iterdir()}
    assert noms == {"a.json"}
    assert "secret.json" not in noms


def test_calibration_s_ouvre_apres_gel(tmp_path: Path) -> None:
    (tmp_path / "calibration").mkdir()
    (tmp_path / "calibration" / "c.json").write_text("{}", encoding="utf-8")
    jeton = emettre_jeton("sha256:poids", "2026-09-09T10:00:00Z")
    dossier = GestionDonnees(tmp_path).pour_calibration(jeton)
    assert (dossier / "c.json").is_file()


class _Boite:
    def __init__(self, poids: np.ndarray) -> None:
        self.poids = poids


def test_calibration_refuse_un_modele_modifie(tmp_path: Path) -> None:
    """Après le gel, un poids touché invalide le jeton (`MILESTONE-5.md` §2)."""
    (tmp_path / "calibration").mkdir()
    modele = _Boite(np.array([1.0, 2.0, 3.0]))
    jeton = geler_et_emettre(modele, horodatage="2026-09-09T12:00:00Z")
    GestionDonnees(tmp_path).pour_calibration(jeton, modele)
    modele.poids = modele.poids + 0.01
    with pytest.raises(ModeleModifie):
        GestionDonnees(tmp_path).pour_calibration(jeton, modele)
