"""The 10-minute notebook runs as shipped (PLAN.md 5.6).

Its code cells run in order, in one namespace, in a temporary directory holding the
example plan it reads: what it writes never touches the repository. No Jupyter
dependency: the notebook is JSON, and a cell is Python source.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

EXAMPLES = Path(__file__).parents[2] / "examples"
NOTEBOOK = EXAMPLES / "ten_minutes.ipynb"


def _cells() -> list[dict[str, object]]:
    return json.loads(NOTEBOOK.read_text(encoding="utf-8"))["cells"]


def test_the_notebook_is_committed_without_outputs() -> None:
    """Outputs in git drift from the code; CI produces them instead."""
    for cell in _cells():
        if cell["cell_type"] == "code":
            assert cell["outputs"] == [] and cell["execution_count"] is None


def test_the_notebook_runs_and_writes_its_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    shutil.copy(EXAMPLES / "t3_load_bearing.json", tmp_path)
    monkeypatch.chdir(tmp_path)
    namespace: dict[str, object] = {}
    for rank, cell in enumerate(_cells()):
        if cell["cell_type"] == "code":
            source = str(cell["source"])
            exec(compile(source, f"{NOTEBOOK.name}[cell {rank}]", "exec"), namespace)
    out = capsys.readouterr().out
    assert "valid: True" in out and "CORRECTION DU PLAN" in out
    for name in ("compare.svg", "fixed.json", "fixed.dxf", "fixed.ifc"):
        assert (tmp_path / name).stat().st_size > 0
