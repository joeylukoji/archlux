"""Every experiment script runs (PLAN.md phase 2: `experiments/` was outside the tests).

Synthetic scripts run in full into a temporary directory. Corpus scripts (MSD) run on a
small MSD-format CSV built here, as ``tests/unit/test_loaders.py`` does: the real
corpus is not redistributed, but a script that no longer runs is caught before anyone
spends an afternoon on the corpus. Byte-for-byte reproduction of ``results/`` is
checked by ``make check-results``, not here: floating-point output may differ in the
last digits across platforms.
"""

from __future__ import annotations

import csv
import json
import runpy
import sys
from pathlib import Path

import pytest
from shapely.geometry import box

from tests.unit.test_bench_generation import RECORD
from tests.unit.test_loaders import _write_csv

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
    runpy.run_path(str(ROOT / "experiments" / script), run_name="__main__")


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
    _write_csv(path, rows)


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
    # Spec 1.7 / 1.10: every attempt carries its outcome and the independent verdict.
    assert {r["outcome"] for r in rows} <= {
        "repaired",
        "rejected",
        "infeasible",
        "computation_failure",
    }
    repaired = [r for r in rows if r["outcome"] == "repaired"]
    assert repaired and all(r["validator_valid"] == "True" for r in repaired)
    assert all(r["evidence"] in {"exact", "numeric"} and r["n_rooms_after"] for r in repaired)
    summary = tmp_path / "j7_repair.md"
    _run(
        "j7_msd_summary.py",
        str(tmp_path / "j7_repair_raw.csv"),
        str(summary),
        monkeypatch=monkeypatch,
    )
    assert "| all faults |" in summary.read_text(encoding="utf-8")
    _run("j7_msd_idempotence.py", str(msd), "3", str(tmp_path), monkeypatch=monkeypatch)
    idempotence = (tmp_path / "j7_msd_idempotence.md").read_text()
    assert "valid after legalize: 3/3" in idempotence
    assert "(apartment a" in idempotence  # the maximum displacement is attributed
    assert (tmp_path / "j7_msd_idempotence_raw.csv").read_text().count("\n") == 4


def test_the_msd_summary_rebuilds_the_published_table(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``results/j7_repair.md`` had no script: rebuilt from its raw rows (J7 review)."""
    out = tmp_path / "summary.md"
    raw = ROOT / "results" / "j7_repair_raw.csv"
    _run("j7_msd_summary.py", str(raw), str(out), monkeypatch=monkeypatch)
    table = out.read_text(encoding="utf-8")
    assert "| all faults | 4796 | 35.9 % | 93.0 % | **93.9 %** | [93.2, 94.5] |" in table
    assert "| fault retrecir | 1196 | 10.0 % | 97.6 % | **98.0 %** | [97.0, 98.6] |" in table
    # The whole published page is generated, the outcome table included (no "no
    # infeasible program" sentence typed by hand next to 270 infeasible rows).
    assert table == (ROOT / "results" / "j7_repair.md").read_text(encoding="utf-8")
    assert "| infeasible (Farkas) | 0 | 270 |" in table


def test_the_pooled_generation_summary_is_reproduced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``results/j8_pooled.md`` names mode, budget and width of every rate (B8)."""
    for name in ("etoile", "plausible", "divers"):
        raw = f"j8_{name}_raw.csv"
        (tmp_path / raw).write_bytes((ROOT / "results" / raw).read_bytes())
    _run("j8_summary.py", str(tmp_path), monkeypatch=monkeypatch)
    page = (tmp_path / "j8_pooled.md").read_text(encoding="utf-8")
    assert page == (ROOT / "results" / "j8_pooled.md").read_text(encoding="utf-8")
    assert "| `pavage` | 0 | 0.50 m | 740 | **7** (0.9 %) |" in page
    assert "| `pavage` | 16 | 0.50 m | 740 | **145** (19.6 %) |" in page


def test_the_generation_experiment_runs_on_a_mini_jsonl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``j8_generation.py`` end to end: JSONL in, raw CSV and summary out."""
    plans = tmp_path / "plans.jsonl"
    degenerate = {**RECORD, "id": "g1", "pieces": []}
    plans.write_text(f"{json.dumps(RECORD)}\n{json.dumps(degenerate)}\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)  # the script writes under ./results
    _run("j8_generation.py", str(plans), "2", "mini", monkeypatch=monkeypatch)
    with (tmp_path / "results" / "j8_mini_raw.csv").open(encoding="utf-8") as handle:
        assert {row["plan_id"] for row in csv.DictReader(handle)} == {"g0"}
    summary = (tmp_path / "results" / "j8_mini.md").read_text(encoding="utf-8")
    assert summary.startswith("# Milestone 8")
    assert "{'empty union': 1}" in summary


def test_the_closed_form_b7_breakdown_runs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Spec 1.3 / P14: errors by orientation and room type, raw rows published."""
    _run("j7_sd_groups.py", str(tmp_path), "20", monkeypatch=monkeypatch)
    summary = (tmp_path / "j7_sd_groups.md").read_text(encoding="utf-8")
    assert "| room_type | kitchen |" in summary
    assert "not against simulations" in summary
    assert (tmp_path / "j7_sd_groups_rooms_raw.csv").stat().st_size > 0


def test_the_selection_and_reconciliation_experiments_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Spec 1.4 / 1.8: small enough for the suite, same code path as the published run."""
    _run("j5_selection.py", str(tmp_path), "80", "1", monkeypatch=monkeypatch)
    assert "| policy | all |" in (tmp_path / "j5_selection.md").read_text(encoding="utf-8")
    assert json.loads((tmp_path / "j5_selection_manifest.json").read_text())["runs"]
    _run("reconcile.py", str(ROOT / "results"), monkeypatch=monkeypatch)
