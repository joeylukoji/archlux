"""Jeton de calibration — `MILESTONE-4.md` §2. Sans jeton, le jeu reste fermé."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from archlux.errors import CalibrationLocked, ModelModified
from archlux.uq.gestion import (
    DataManagement,
    freeze_and_issue,
    issue_token,
    open_calibration,
)


def test_emettre_jeton_est_deterministe() -> None:
    a = issue_token("abc", "2026-01-01T00:00:00Z")
    b = issue_token("abc", "2026-01-01T00:00:00Z")
    assert a == b
    assert a.signature != issue_token("abc", "2026-01-02T00:00:00Z").signature


def test_ouvrir_calibration_sans_jeton_valide_leve(tmp_path: Path) -> None:
    (tmp_path / "calibration").mkdir()
    faux = issue_token("poids", "2026-01-01T00:00:00Z")
    from dataclasses import replace

    with pytest.raises(CalibrationLocked):
        open_calibration(tmp_path, replace(faux, signature="0" * 16))


def test_pour_entrainement_ne_voit_pas_la_calibration(tmp_path: Path) -> None:
    (tmp_path / "train").mkdir()
    (tmp_path / "train" / "a.json").write_text("{}", encoding="utf-8")
    (tmp_path / "calibration").mkdir()
    (tmp_path / "calibration" / "secret.json").write_text("{}", encoding="utf-8")
    (tmp_path / "test").mkdir()
    gestion = DataManagement(tmp_path)
    noms = {p.name for p in gestion.for_training().iterdir()}
    assert noms == {"a.json"}
    assert "secret.json" not in noms


def test_calibration_s_ouvre_apres_gel(tmp_path: Path) -> None:
    (tmp_path / "calibration").mkdir()
    (tmp_path / "calibration" / "c.json").write_text("{}", encoding="utf-8")
    token = issue_token("sha256:poids", "2026-09-09T10:00:00Z")
    dossier = DataManagement(tmp_path).for_calibration(token)
    assert (dossier / "c.json").is_file()


class _Boite:
    def __init__(self, weights: np.ndarray) -> None:
        self.weights = weights


def test_calibration_refuse_un_modele_modifie(tmp_path: Path) -> None:
    """Après le gel, un poids touché invalide le jeton (`MILESTONE-5.md` §2)."""
    (tmp_path / "calibration").mkdir()
    model = _Boite(np.array([1.0, 2.0, 3.0]))
    token = freeze_and_issue(model, timestamp="2026-09-09T12:00:00Z")
    DataManagement(tmp_path).for_calibration(token, model)
    model.weights = model.weights + 0.01
    with pytest.raises(ModelModified):
        DataManagement(tmp_path).for_calibration(token, model)


def test_a_learned_surrogate_can_be_frozen(tmp_path: Path) -> None:
    """Review of the stack (#14): the fingerprint looked up ``weights_fingerprint`` only,
    while LearnedSurrogate exposes ``empreinte_poids``: freezing it raised."""
    from archlux.light.appris import LearnedSurrogate

    model = LearnedSurrogate(tmp_path / "w.npz", "abc123", gele=True)
    token = freeze_and_issue(model, timestamp="2026-09-09T12:00:00Z")
    assert token.weights_fingerprint == "abc123"
