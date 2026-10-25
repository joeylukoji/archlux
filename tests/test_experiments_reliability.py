"""``experiments/j4_reliability.py`` runs and labels its reference (spec 1.3 / 1.5)."""

from __future__ import annotations

import csv
import runpy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_the_reliability_experiment_runs_and_never_claims_a_physical_gain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "argv", ["j4_reliability.py", str(tmp_path)])
    runpy.run_path(str(ROOT / "experiments" / "j4_reliability.py"), run_name="__main__")
    with (tmp_path / "j4_before_after.csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 16
    assert {r["status"] for r in rows} == {"closed_form_only"}
    with (tmp_path / "j4_reliability.csv").open(encoding="utf-8") as handle:
        plans = {r["plans"] for r in csv.DictReader(handle)}
    assert plans == {"held_out", "optimized", "fw_steps"}


def test_the_published_reliability_tables_are_reproduced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "argv", ["j4_reliability.py", str(tmp_path)])
    runpy.run_path(str(ROOT / "experiments" / "j4_reliability.py"), run_name="__main__")
    for name in ("j4_reliability.csv", "j4_before_after.csv"):
        published = (ROOT / "results" / name).read_text(encoding="utf-8")
        assert (tmp_path / name).read_text(encoding="utf-8") == published, name
