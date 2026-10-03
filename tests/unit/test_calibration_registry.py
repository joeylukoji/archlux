"""Calibration token: `MILESTONE-4.md` §2. Without a token, the set stays closed."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from archlux.errors import CalibrationLocked, ModelModified
from archlux.uq.registry import (
    DataManagement,
    freeze_and_issue,
    issue_token,
    open_calibration,
)


def test_issuing_a_token_is_deterministic() -> None:
    a = issue_token("abc", "2026-01-01T00:00:00Z")
    b = issue_token("abc", "2026-01-01T00:00:00Z")
    assert a == b
    assert a.signature != issue_token("abc", "2026-01-02T00:00:00Z").signature


def test_opening_calibration_without_a_valid_token_raises(tmp_path: Path) -> None:
    (tmp_path / "calibration").mkdir()
    forged = issue_token("poids", "2026-01-01T00:00:00Z")
    from dataclasses import replace

    with pytest.raises(CalibrationLocked):
        open_calibration(tmp_path, replace(forged, signature="0" * 16))


def test_for_training_does_not_see_the_calibration(tmp_path: Path) -> None:
    (tmp_path / "train").mkdir()
    (tmp_path / "train" / "a.json").write_text("{}", encoding="utf-8")
    (tmp_path / "calibration").mkdir()
    (tmp_path / "calibration" / "secret.json").write_text("{}", encoding="utf-8")
    (tmp_path / "test").mkdir()
    management = DataManagement(tmp_path)
    names = {p.name for p in management.for_training().iterdir()}
    assert names == {"a.json"}
    assert "secret.json" not in names


def test_calibration_opens_after_the_freeze(tmp_path: Path) -> None:
    (tmp_path / "calibration").mkdir()
    (tmp_path / "calibration" / "c.json").write_text("{}", encoding="utf-8")
    token = issue_token("sha256:poids", "2026-09-09T10:00:00Z")
    folder = DataManagement(tmp_path).for_calibration(token)
    assert (folder / "c.json").is_file()


class _Box:
    def __init__(self, weights: np.ndarray) -> None:
        self.weights = weights


def test_calibration_refuses_a_modified_model(tmp_path: Path) -> None:
    """After the freeze, a touched weight invalidates the token (`MILESTONE-5.md` §2)."""
    (tmp_path / "calibration").mkdir()
    model = _Box(np.array([1.0, 2.0, 3.0]))
    token = freeze_and_issue(model, timestamp="2026-09-09T12:00:00Z")
    DataManagement(tmp_path).for_calibration(token, model)
    model.weights = model.weights + 0.01
    with pytest.raises(ModelModified):
        DataManagement(tmp_path).for_calibration(token, model)


def test_a_learned_surrogate_can_be_frozen(tmp_path: Path) -> None:
    """Review of the stack (#14): the fingerprint looked up ``weights_fingerprint`` only,
    while LearnedSurrogate exposes ``empreinte_poids``: freezing it raised."""
    from archlux.light.learned import LearnedSurrogate

    model = LearnedSurrogate(tmp_path / "w.npz", "abc123", frozen=True)
    token = freeze_and_issue(model, timestamp="2026-09-09T12:00:00Z")
    assert token.weights_fingerprint == "abc123"
