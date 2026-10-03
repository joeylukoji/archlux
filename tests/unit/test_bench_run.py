"""Test bench: `MILESTONE-6.md` §5: manifest, evaluate_by, raw rows before aggregates."""

from __future__ import annotations

from pathlib import Path

import pytest

from archlux.bench import compare, report, run
from archlux.bench.stats import paired_bootstrap, power, tost
from archlux.light.analytic import AnalyticSurrogate
from archlux.types import ModelTrace, Orientation, Plan, Room


def _plan() -> Plan:
    return Plan(
        rooms=(Room(id="a", type="living_room", x=0.0, y=0.0, w=6.0, h=9.0),),
        walls=(),
        openings=(),
        outline=((0.0, 0.0), (12.0, 0.0), (12.0, 9.0), (0.0, 9.0)),
    )


def _evaluator(plan: Plan, method: object) -> float:
    _ = method
    return float(sum(p.w * p.h for p in plan.rooms))


def test_complete_manifest(tmp_path: Path) -> None:
    """`MILESTONE-6.md` §5: run writes a manifest with weights and calibration_n."""
    model = ModelTrace(weights_fingerprint="sha256:abc", calibration_n=40, alpha=0.10)
    result = run(
        plans=(_plan(), _plan()),
        orientations=(Orientation(0.0), Orientation(45.0)),
        methods=(AnalyticSurrogate(),),
        evaluate_by=_evaluator,
        seed=17,
        data_fingerprint="sha256:donnees",
        split="splits/v2",
        model=model,
        directory=tmp_path,
    )
    m = result.manifest
    assert m.model is not None
    assert m.model["weights_fingerprint"] and m.model["calibration_n"] > 0
    assert result.manifest_path.is_file()
    assert result.raw_path.is_file()
    # raw rows written before any aggregate: the file exists as soon as run returns
    assert len(result.rows) == 2


def test_evaluate_by_is_mandatory() -> None:
    """`MILESTONE-6.md` §5: compare refuses without an external evaluator."""
    with pytest.raises(TypeError):
        compare(plans=(_plan(),), methods=(AnalyticSurrogate(),))


def test_report_stratified_by_orientation(tmp_path: Path) -> None:
    model = ModelTrace(weights_fingerprint="sha256:x", calibration_n=10, alpha=0.1)
    result = run(
        plans=(_plan(), _plan(), _plan(), _plan()),
        orientations=(
            Orientation(0.0),
            Orientation(10.0),
            Orientation(180.0),
            Orientation(190.0),
        ),
        methods=(AnalyticSurrogate(),),
        evaluate_by=_evaluator,
        seed=3,
        data_fingerprint="d",
        split="s",
        model=model,
        directory=tmp_path,
    )
    bench_report = report(result, seed=3)
    assert len(bench_report.strata) == 8
    assert sum(s.n for s in bench_report.strata) == 4


def test_bootstrap_tost_power() -> None:
    a = (1.0, 1.1, 0.9, 1.05)
    b = (0.95, 1.0, 0.85, 1.0)
    ic = paired_bootstrap(a, b, seed=17, n_replications=199)
    assert ic.low <= ic.value <= ic.high
    ok, p = tost(a, b, delta=0.5, alpha=0.05)
    assert isinstance(ok, bool)
    assert 0.0 <= p <= 1.0
    assert 0.0 <= power(0.5, 1.0, n=30, alpha=0.05) <= 1.0
