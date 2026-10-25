"""The reviewed B9 experiment runs, and never calls its scores a physical measure."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_the_b9_review_runs_in_quick_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(ROOT)  # the inputs are read from results/j9_inputs.json
    monkeypatch.setattr(sys, "argv", ["j9_review.py", str(tmp_path), "--quick"])
    runpy.run_path(str(ROOT / "experiments" / "j9_review.py"), run_name="__main__")
    for name in ("j9_variants_raw.csv", "j9_timing_raw.csv", "j9_review.md"):
        assert (tmp_path / name).stat().st_size > 0, name
    page = (tmp_path / "j9_review.md").read_text(encoding="utf-8")
    assert "not a physical simulation" in page
    assert "partly by construction" in page


def test_the_rebuilt_inputs_are_published() -> None:
    assert (ROOT / "results" / "j9_inputs.json").stat().st_size > 0
