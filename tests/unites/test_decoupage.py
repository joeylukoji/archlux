"""Découpage en trois jeux — `MILESTONE-4.md` §2. Dédupliquer avant de découper."""

from __future__ import annotations

from pathlib import Path

import pytest

from archlux.bench.protocole import charger_decoupage
from archlux.erreurs import InvariantViole

SPLITS = Path(__file__).resolve().parents[2] / "splits" / "v1"


def test_aucun_identifiant_partage() -> None:
    decoupage = charger_decoupage(SPLITS)
    train, calib, test = (
        set(decoupage.entrainement),
        set(decoupage.calibration),
        set(decoupage.test),
    )
    assert not (train & calib)
    assert not (train & test)
    assert not (calib & test)


def test_proportions_soixante_vingt_vingt() -> None:
    decoupage = charger_decoupage(SPLITS)
    total = len(decoupage.entrainement) + len(decoupage.calibration) + len(decoupage.test)
    assert total == 90
    assert len(decoupage.entrainement) == 54
    assert len(decoupage.calibration) == 18
    assert len(decoupage.test) == 18


def test_identifiant_duplique_leve(tmp_path: Path) -> None:
    (tmp_path / "train.txt").write_text("a\nb\n", encoding="utf-8")
    (tmp_path / "calibration.txt").write_text("b\nc\n", encoding="utf-8")
    (tmp_path / "test.txt").write_text("d\n", encoding="utf-8")
    with pytest.raises(InvariantViole):
        charger_decoupage(tmp_path)
