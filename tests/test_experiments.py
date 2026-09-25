"""Every experiment script runs (PLAN.md phase 2: `experiences/` was outside the tests).

Synthetic scripts run in full into a temporary directory. Corpus scripts (MSD) run on a
small MSD-format CSV built here, as ``tests/unites/test_chargeurs.py`` does: the real
corpus is not redistributed, but a script that no longer runs is caught before anyone
spends an afternoon on the corpus. Byte-for-byte reproduction of ``resultats/`` is
checked by ``make check-resultats``, not here: floating-point output may differ in the
last digits across platforms.
"""

from __future__ import annotations

import csv
import runpy
import sys
from pathlib import Path

import pytest
from shapely.geometry import box

from tests.unites.test_chargeurs import _ecrire_csv

ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC = {
    "j2_validity.py": ("j2_validity_raw.csv",),
    "j3_orientation.py": ("j3_orientation.csv", "j3_orientation_min12.svg"),
    "j4_gradient.py": ("j4_gradient.csv",),
    "j5_coverage.py": ("j5_coverage.csv",),
    "j6_active.py": ("j6_active.csv",),
    "j6_ifc.py": ("j6_ifc.csv",),
}


def _run(script: str, *args: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", [script, *args])
    runpy.run_path(str(ROOT / "experiences" / script), run_name="__main__")


@pytest.mark.parametrize("script", sorted(SYNTHETIC))
def test_a_synthetic_experiment_runs(
    script: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if script == "j6_ifc.py":
        pytest.importorskip("ifcopenshell")
    args = (str(tmp_path), "3") if script == "j6_ifc.py" else (str(tmp_path),)  # 2.8 s a file
    _run(script, *args, monkeypatch=monkeypatch)
    for name in SYNTHETIC[script]:
        assert (tmp_path / name).stat().st_size > 0, name


def _mini_msd(path: Path) -> None:
    rows = []
    for k in range(3):  # three two-room apartments, rotated as in MSD
        rows += [
            (f"a{k}", "area", "LIVING_ROOM", box(0.0, 0.0, 3.9, 5.0)),
            (f"a{k}", "area", "BEDROOM", box(4.1, 0.0, 8.0 + k, 5.0)),
            (f"a{k}", "separator", "WALL", box(3.9, 0.0, 4.1, 5.0)),
        ]
    _ecrire_csv(path, rows)


def test_the_msd_experiments_run_on_a_mini_corpus(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    msd = tmp_path / "msd.csv"
    _mini_msd(msd)
    _run("j7_msd_repair.py", str(msd), "3", str(tmp_path), monkeypatch=monkeypatch)
    with (tmp_path / "j7_repair_raw.csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert {r["plan_id"] for r in rows} == {"a0", "a1", "a2"}
    assert {r["pavage"] for r in rows} == {"False", "True"}
    summary = tmp_path / "j7_repair.md"
    _run(
        "j7_msd_summary.py",
        str(tmp_path / "j7_repair_raw.csv"),
        str(summary),
        monkeypatch=monkeypatch,
    )
    assert "| all faults |" in summary.read_text(encoding="utf-8")
    _run("j7_msd_idempotence.py", str(msd), "3", str(tmp_path), monkeypatch=monkeypatch)
    assert "valid after legalize: 3/3" in (tmp_path / "j7_msd_idempotence.md").read_text()
