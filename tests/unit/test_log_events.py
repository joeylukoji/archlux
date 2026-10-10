"""Structured debug events (PLAN.md phase 4, block 17, item 47).

Events go to standard ``logging`` at ``DEBUG``: silent by default, visible when the
application enables the ``archlux`` loggers.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pytest

from archlux._log import event
from archlux.errors import InvariantViolation
from archlux.export.dxf import to_dxf
from archlux.export.ifc import to_ifc
from archlux.solve.frank_wolfe import frank_wolfe
from tests.unit.test_frank_wolfe import NORTH, POLY, LinearObjective, _feasible_start
from tests.unit.test_plan_exports import overlapping_plan


def _events(caplog: pytest.LogCaptureFixture, name: str) -> list[logging.LogRecord]:
    return [r for r in caplog.records if getattr(r, "event", None) == name]


def test_an_event_is_silent_without_debug(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING, logger="archlux")
    event("archlux.solve", "probe", value=1)
    assert caplog.records == []


def test_an_event_carries_its_name_and_fields(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="archlux")
    event("archlux.solve", "probe", value=1, label="a")
    (record,) = caplog.records
    assert record.levelno == logging.DEBUG
    assert record.event == "probe"  # type: ignore[attr-defined]
    assert record.fields == {"value": 1, "label": "a"}  # type: ignore[attr-defined]
    assert record.getMessage() == "probe label='a' value=1"


def test_frank_wolfe_reports_each_iteration_and_its_stop(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="archlux.solve")
    objective = LinearObjective(c=np.array([0.0, 0.0, 1.0, 1.0]))
    result = frank_wolfe(POLY, objective, NORTH, _feasible_start(), max_iter=4)
    (stop,) = _events(caplog, "frank_wolfe.stop")
    assert stop.fields["status"] == result.status  # type: ignore[attr-defined]
    stepped = sum(1 for it in result.trace.iterations if it.step > 0.0)
    assert len(_events(caplog, "frank_wolfe.iteration")) == stepped


def test_a_refused_export_is_reported(caplog: pytest.LogCaptureFixture, tmp_path: Path) -> None:
    caplog.set_level(logging.DEBUG, logger="archlux.export")
    assert not to_ifc(overlapping_plan(), tmp_path / "plan.ifc").valid
    with pytest.raises(InvariantViolation):
        to_dxf(overlapping_plan(), tmp_path / "plan.dxf")
    formats = [r.fields["format"] for r in _events(caplog, "export.refused")]  # type: ignore[attr-defined]
    assert formats == ["ifc", "dxf"]


def test_each_load_rejection_is_reported(caplog: pytest.LogCaptureFixture, tmp_path: Path) -> None:
    from shapely.geometry import Polygon

    from archlux.data.loaders import LoadStatistics, load_msd
    from tests.unit.test_loaders import _two_room_apartment, _write_csv

    caplog.set_level(logging.DEBUG, logger="archlux.data")
    oblique = Polygon([(0.0, 0.0), (4.0, 0.0), (4.0, 3.0), (2.0, 4.5), (0.0, 3.0)])
    csv = tmp_path / "msd.csv"
    _write_csv(csv, [*_two_room_apartment(), ("a2", "area", "ROOM", oblique)])
    stats = LoadStatistics()
    list(load_msd(csv, stats=stats))
    rejected = _events(caplog, "load.rejected")
    assert len(rejected) == stats.read - stats.kept
    assert {r.fields["reason"] for r in rejected} == set(stats.rejections)  # type: ignore[attr-defined]


def test_a_gap_refusal_is_reported(caplog: pytest.LogCaptureFixture) -> None:
    from archlux import GapNeedsTiling, legalize
    from tests.unit.test_hostile_inputs import gapped_plan, make_context

    caplog.set_level(logging.DEBUG, logger="archlux.api")
    with pytest.raises(GapNeedsTiling):
        legalize(gapped_plan(), make_context())
    (record,) = _events(caplog, "legalize.gap_needs_tiling")
    assert all(v.startswith("gap") for v in record.fields["violations"])  # type: ignore[attr-defined]


def test_a_missing_frank_wolfe_dual_falls_back_and_is_reported(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review of block 17: ``legalize.duals_fallback`` had no test."""
    from dataclasses import replace

    import archlux as ax
    import archlux.api
    from archlux.light.analytic import AnalyticSurrogate

    def without_duals(*args: object, **kwargs: object) -> object:
        return replace(frank_wolfe(*args, **kwargs), duals=None)  # type: ignore[arg-type]

    monkeypatch.setattr(archlux.api, "frank_wolfe", without_duals)
    caplog.set_level(logging.DEBUG, logger="archlux.api")
    outline = ((0.0, 0.0), (12.0, 0.0), (12.0, 9.0), (0.0, 9.0))
    plan = ax.Plan(
        rooms=(
            ax.Room(id="living_room", type="living_room", x=0.0, y=0.0, w=12.0, h=5.0),
            ax.Room(id="bedroom", type="bedroom", x=0.0, y=4.0, w=12.0, h=5.0),
        ),
        outline=outline,
    )
    ctx = ax.Context(
        structure=ax.Structure(()),
        orientation=ax.Orientation(0.0),
        outline=outline,
        regulation=ax.Regulation((), 1.0),
    )
    legalized = ax.legalize(plan, ctx, objective=AnalyticSurrogate())
    assert legalized.certificate is not None and legalized.certificate.geometry.valid
    (fallback,) = _events(caplog, "legalize.duals_fallback")
    assert fallback.fields == {"source": "l1_pass"}  # type: ignore[attr-defined]
