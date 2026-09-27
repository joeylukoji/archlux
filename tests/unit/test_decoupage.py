"""Découpage en trois jeux — `MILESTONE-4.md` §2. Dédupliquer avant de découper."""

from __future__ import annotations

from pathlib import Path

import pytest

from archlux.bench.protocole import load_split
from archlux.errors import InvariantViolation

SPLITS = Path(__file__).resolve().parents[2] / "splits" / "v1"


def test_aucun_identifiant_partage() -> None:
    split = load_split(SPLITS)
    train, calib, test = (
        set(split.train),
        set(split.calibration),
        set(split.test),
    )
    assert not (train & calib)
    assert not (train & test)
    assert not (calib & test)


def test_proportions_soixante_vingt_vingt() -> None:
    split = load_split(SPLITS)
    total = len(split.train) + len(split.calibration) + len(split.test)
    assert total == 90
    assert len(split.train) == 54
    assert len(split.calibration) == 18
    assert len(split.test) == 18


def test_identifiant_duplique_leve(tmp_path: Path) -> None:
    (tmp_path / "train.txt").write_text("a\nb\n", encoding="utf-8")
    (tmp_path / "calibration.txt").write_text("b\nc\n", encoding="utf-8")
    (tmp_path / "test.txt").write_text("d\n", encoding="utf-8")
    with pytest.raises(InvariantViolation):
        load_split(tmp_path)
