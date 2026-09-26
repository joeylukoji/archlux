"""Shared type aliases and the typing of the lazy packages (PLAN.md 3.8).

``Literal["sDA", "ASE", "UDI", "vue"]`` was written in seven places, and ``Surrogate``
declared its indicator as a bare ``str`` while ``PerformanceBound`` used the literal.
"""

from __future__ import annotations

import subprocess
import sys
import typing
from pathlib import Path

import numpy as np
import pytest

from archlux.types import Indicateur, PerformanceBound

SRC = Path(__file__).resolve().parents[2] / "src" / "archlux"


def test_the_indicator_alias_lists_the_four_indicators() -> None:
    assert typing.get_args(Indicateur) == ("sDA", "ASE", "UDI", "vue")


def test_the_indicator_literal_is_written_once() -> None:
    """Every other module imports the alias instead of repeating the four names."""
    repeated = [
        path.relative_to(SRC).as_posix()
        for path in sorted(SRC.rglob("*.py"))
        if 'Literal["sDA", "ASE", "UDI", "vue"]' in path.read_text(encoding="utf-8")
    ]
    assert repeated == ["types.py"]


def test_the_bound_and_the_protocol_share_the_alias() -> None:
    from archlux.light.protocole import Surrogate

    assert typing.get_type_hints(PerformanceBound)["indicator"] == Indicateur
    assert typing.get_type_hints(Surrogate.indicator.fget)["return"] == Indicateur  # type: ignore[attr-defined]


def test_the_float_vector_alias_is_a_float64_array() -> None:
    from archlux.arrays import VecteurF

    dtype = typing.get_args(VecteurF)[1]
    assert typing.get_args(dtype) == (np.float64,)


SNIPPET = """import archlux as ax
reveal_type(ax.light)
reveal_type(ax.feasibility.is_feasible)
"""


def test_mypy_sees_the_lazy_packages(tmp_path: Path) -> None:
    """``archlux.light`` must be a module for type checkers, not ``object`` or ``Any``."""
    probe = [sys.executable, "-m", "mypy", "--version"]
    if subprocess.run(probe, capture_output=True, check=False).returncode:
        pytest.skip("mypy is not installed")
    snippet = tmp_path / "snippet.py"
    snippet.write_text(SNIPPET, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "mypy", "--strict", str(snippet)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert "error" not in result.stdout, result.stdout
    assert "def (program: archlux.types.Plan" in result.stdout, result.stdout
