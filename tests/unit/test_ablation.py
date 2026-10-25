"""Ablations run every configuration on the same inputs (spec 1.9); records trace a run."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import archlux as ax
from archlux.bench import ablation as ab
from archlux.bench import repro
from archlux.data.synthetic import generate_corpus, two_room_vectors
from archlux.light.analytic import AnalyticSurrogate
from archlux.light.split_flux import SplitFluxOracle


def _context(plan: ax.Plan, orientation: ax.Orientation) -> ax.Context:
    return ax.Context(ax.Structure(()), orientation, ax.Regulation((), 1.0), outline=plan.outline)


@pytest.fixture(scope="module")
def rows():  # type: ignore[no-untyped-def]
    model, reference = AnalyticSurrogate(), SplitFluxOracle()
    q = ab.calibrate_q(model, reference, list(zip(*two_room_vectors(20, seed=2), strict=True)))
    cases = ab.make_cases(generate_corpus(3, seed=17), _context, seed=17, n_inits=2)
    configs = ab.configurations(model, reference, q, budgets=(0.05,), gradient_free=True)
    return ab.run_ablations(
        cases, configs, legalize_trace=ax.legalize_trace, model=model, reference=reference
    )


def test_every_configuration_sees_the_same_cases(rows) -> None:  # type: ignore[no-untyped-def]
    by_config: dict[str, list[tuple[str, int, float]]] = {}
    for r in rows:
        by_config.setdefault(r.config, []).append((r.source, r.init, r.azimuth))
    cases = list(by_config.values())
    assert len(cases[0]) == 6
    assert all(c == cases[0] for c in cases)


def test_corrupted_inputs_are_invalid_and_refusals_are_kept(rows) -> None:  # type: ignore[no-untyped-def]
    assert not any(r.valid for r in rows if r.config == "initial")
    assert all(r.valid for r in rows if r.config == "repair")
    tight = [r for r in rows if r.config == "fw_surrogate_budget_0.05"]
    assert all(r.status == "ok" or not r.valid for r in tight)  # refused, never fake-valid


def test_summary_pairs_against_repair_and_writes(rows, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    table = ab.summarize_ablations(rows, seed=1)
    assert table.count("\n") == 2 + len({r.config for r in rows})
    assert "| fw_reference | 6 | 6 |" in table
    out = tmp_path / "raw.csv"
    ab.write_ablation_rows(out, rows)
    assert out.read_text(encoding="utf-8").count("\n") == len(rows) + 1


def test_record_hashes_files_and_flags_restricted_inputs(tmp_path: Path) -> None:
    data, result = tmp_path / "corpus.csv", tmp_path / "out.csv"
    data.write_text("a\n", encoding="utf-8")
    result.write_text("b\n", encoding="utf-8")
    run = repro.record(
        seed=17,
        command="python x.py",
        parameters={"n": 3},
        outputs=[result],
        restricted=[data],
        root=tmp_path,
    )
    assert run["git"] == {"commit": None, "dirty": None}  # tmp_path is not a repository
    files = {Path(f["path"]).name: f for f in run["files"]}  # type: ignore[union-attr]
    assert files["corpus.csv"]["redistributable"] is False
    assert files["out.csv"]["sha256"] == repro.file_sha256(result)
    repro.write_record(tmp_path / "run.json", run)
    assert json.loads((tmp_path / "run.json").read_text())["seed"] == 17


def test_gradient_free_row_runs_on_the_same_cases(rows) -> None:  # type: ignore[no-untyped-def]
    fd = [r for r in rows if r.config == "fw_finite_difference"]
    assert len(fd) == 6
    assert all(r.valid for r in fd)
    assert all(r.fw_status != "-" for r in fd)  # it did run Frank-Wolfe


def test_git_state_of_this_repository() -> None:
    state = repro.git_state(Path(__file__).parent)
    assert state["commit"] is None or len(str(state["commit"])) == 40
