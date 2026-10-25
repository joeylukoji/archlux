"""Errors by group with cluster intervals (B7, spec 1.3), and the clean-tree flag of runs."""

from __future__ import annotations

import csv
import subprocess
from pathlib import Path

import pytest

from archlux.bench import repro
from archlux.bench.breakdown import breakdown, to_markdown, write_breakdown_rows
from archlux.errors import InvariantViolation


def test_breakdown_by_hand() -> None:
    pred = [1.0, 2.0, 4.0, 4.0]
    truth = [0.0, 2.0, 5.0, 5.0]
    groups = breakdown(pred, truth, ["a", "a", "b", "c"], {"kind": ["x", "x", "y", "y"]}, seed=1)
    every, x, y = groups
    assert (every.grouping, every.n, every.n_clusters) == ("all", 4, 3)
    assert every.mae == pytest.approx(0.75)
    assert every.bias == pytest.approx(-0.25)  # errors +1, 0, -1, -1
    assert every.relative_mae == pytest.approx(0.75 / 3.0)
    assert (x.group, x.n, x.n_clusters, x.mae, x.bias) == ("x", 2, 1, 0.5, 0.5)
    assert x.mae_low != x.mae_low  # one cluster: no interval (nan)
    assert (y.mae, y.bias) == (1.0, -1.0)
    assert y.mae_low == y.mae_high == pytest.approx(1.0)
    table = to_markdown(groups, unit="lx")
    assert table.count("\n") == 2 + 3
    assert "MAE (lx)" in table


def test_breakdown_refuses_ragged_columns() -> None:
    with pytest.raises(InvariantViolation):
        breakdown([1.0], [1.0, 2.0], ["a"], {}, seed=1)
    with pytest.raises(InvariantViolation):
        breakdown([], [], [], {}, seed=1)


def test_raw_rows_can_recompute_the_table(tmp_path: Path) -> None:
    out = tmp_path / "rows.csv"
    write_breakdown_rows(
        out, ["p1", "p2"], ["s", "t"], {"m": [1.0, 2.0]}, [1.5, 2.0], {"g": ["u", "v"]}
    )
    with out.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert [r["id"] for r in rows] == ["p1", "p2"]
    assert rows[0]["g"] == "u" and float(rows[0]["truth"]) == 1.5 and float(rows[1]["m"]) == 2.0


def test_a_run_that_rewrites_its_own_tracked_output_is_not_dirty(tmp_path: Path) -> None:
    def git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    try:
        git("init", "-q")
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("git unavailable")
    git("config", "user.email", "t@example.org")
    git("config", "user.name", "t")
    code, result = tmp_path / "code.py", tmp_path / "result.csv"
    code.write_text("x = 1\n", encoding="utf-8")
    result.write_text("old\n", encoding="utf-8")
    git("add", ".")
    git("commit", "-q", "-m", "init")
    result.write_text("new\n", encoding="utf-8")
    assert repro.git_state(tmp_path)["dirty"] is True
    assert repro.git_state(tmp_path, ignore=[result])["dirty"] is False
    code.write_text("x = 2\n", encoding="utf-8")
    assert repro.git_state(tmp_path, ignore=[result])["dirty"] is True
