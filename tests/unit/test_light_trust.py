"""Gradient reliability, run-time refusal and gradient-free baseline (spec 1.5)."""

from __future__ import annotations

import math

import numpy as np
import pytest

import archlux as ax
from archlux.light.analytic import AnalyticSurrogate
from archlux.light.evaluation import EvaluationCase
from archlux.light.split_flux import SplitFluxOracle
from archlux.light.trust import (
    FiniteDifferenceSurrogate,
    GuardedSurrogate,
    UntrustedGradient,
    gradient_agreement,
    gradient_reliability,
    gradient_trust,
    step_gain_audit,
)
from archlux.types import Orientation

ORACLE = SplitFluxOracle()
X = np.array([0.0, 0.0, 5.5, 4.5, 5.5, 0.0, 6.5, 4.5])
SOUTH = Orientation(deg=180.0)


class Negated(SplitFluxOracle):
    """The oracle with its gradient flipped: right values, wrong direction."""

    def gradient(self, x, orientation, *, glazing=None):  # type: ignore[no-untyped-def]
        return -super().gradient(x, orientation, glazing=glazing)


def test_the_oracle_agrees_with_its_own_finite_differences() -> None:
    agreement = gradient_agreement(ORACLE, ORACLE, [X], [SOUTH], step=0.01)
    assert agreement.sign_agreement == 1.0 and agreement.mean_cosine > 0.99
    assert agreement.n_coordinates > 0


def test_a_flipped_gradient_has_zero_agreement() -> None:
    agreement = gradient_agreement(Negated(), ORACLE, [X], [SOUTH], step=0.01)
    assert agreement.sign_agreement == 0.0 and agreement.mean_cosine < -0.99


def test_trust_refuses_without_raising() -> None:
    assert gradient_trust(ORACLE, ORACLE, X, SOUTH).status == "ok"
    verdict = gradient_trust(Negated(), ORACLE, X, SOUTH)
    assert verdict.status == "refuse" and "0.000 < 0.8" in verdict.reason


def test_a_flat_reference_is_refused() -> None:
    class Flat:
        def evaluate(self, x, orientation, *, glazing=None):  # type: ignore[no-untyped-def]
            return 1.0

    verdict = gradient_trust(ORACLE, Flat(), X, SOUTH)
    assert verdict.status == "refuse" and math.isnan(verdict.sign_agreement)


def test_the_guard_stops_with_a_zero_gradient_or_raises() -> None:
    stop = GuardedSurrogate(Negated(), ORACLE)
    assert not np.any(stop.gradient(X, SOUTH)) and stop.refusals == 1
    assert stop.evaluate(X, SOUTH) == ORACLE.evaluate(X, SOUTH)
    loud = GuardedSurrogate(Negated(), ORACLE, on_refuse="raise")
    with pytest.raises(UntrustedGradient) as caught:
        loud.gradient(X, SOUTH)
    assert caught.value.report.status == "refuse"
    good = GuardedSurrogate(ORACLE, ORACLE)
    assert np.allclose(good.gradient(X, SOUTH), ORACLE.gradient(X, SOUTH))


def _context(deg: float) -> tuple[ax.Plan, ax.Context]:
    outline = ((0.0, 0.0), (12.0, 0.0), (12.0, 9.0), (0.0, 9.0))
    rooms = tuple(
        ax.Room(id=i, type=t, x=x, y=y, w=6.0, h=4.5)
        for i, t, x, y in (
            ("sw", "living_room", 0, 0),
            ("se", "bedroom", 6, 0),
            ("nw", "living_room", 0, 4.5),
            ("ne", "bedroom", 6, 4.5),
        )
    )
    ctx = ax.Context(
        structure=ax.Structure(()),
        orientation=ax.Orientation(deg),
        outline=outline,
        regulation=ax.Regulation((), 1.0),
    )
    return ax.Plan(rooms, (), (), outline), ctx


def test_legalize_with_a_refused_gradient_keeps_the_l1_plan() -> None:
    """Integration: the guard is an ordinary objective, ``solve`` is unchanged."""
    plan, ctx = _context(45.0)
    guard = GuardedSurrogate(Negated(), ORACLE)
    out = ax.legalize(plan, ctx, objective=guard)
    l1 = ax.legalize(plan, ctx)
    assert guard.refusals >= 1
    assert [(r.w, r.h) for r in out.rooms] == pytest.approx([(r.w, r.h) for r in l1.rooms])
    assert out.certificate is not None and out.certificate.geometry.valid


def test_the_gradient_free_baseline_matches_the_analytic_gradient() -> None:
    fd = FiniteDifferenceSurrogate(ORACLE, step=1e-4)
    assert np.allclose(fd.gradient(X, SOUTH), ORACLE.gradient(X, SOUTH), atol=1e-4)
    assert fd.evaluate(X, SOUTH) == ORACLE.evaluate(X, SOUTH)
    plan, ctx = _context(45.0)
    by_fd = ax.legalize(plan, ctx, objective=FiniteDifferenceSurrogate(ORACLE))
    by_oracle = ax.legalize(plan, ctx, objective=ORACLE)
    assert [(r.w, r.h) for r in by_fd.rooms] == pytest.approx(
        [(r.w, r.h) for r in by_oracle.rooms], abs=1e-3
    )


def test_reliability_is_broken_down_by_group_and_amplitude() -> None:
    cases = [
        EvaluationCase(
            id=f"c{k}",
            x=np.array([0.0, 0.0, c, 4.5, c, 0.0, 12.0 - c, 4.5]),
            orientation=Orientation(deg=90.0 * k),
            room_type="a" if k < 2 else "b",
        )
        for k, c in enumerate((5.0, 5.5, 6.0, 6.5))
    ]
    rows = gradient_reliability(AnalyticSurrogate(), ORACLE, cases, steps=(0.02, 0.5))
    groupings = {(r.grouping, r.group, r.agreement.step) for r in rows}
    assert ("all", "all", 0.02) in groupings and ("azimuth", "270", 0.5) in groupings
    assert ("room_type", "b", 0.02) in groupings
    assert all(r.passed == (r.agreement.sign_agreement >= 0.8) for r in rows)


def test_the_step_audit_compares_predicted_and_realised_gains() -> None:
    plan, ctx = _context(180.0)
    _, trace = ax.legalize_trace(plan, ctx, objective=AnalyticSurrogate())
    assert trace is not None
    iterates = [it.x for it in trace.iterations]
    rows = step_gain_audit(AnalyticSurrogate(), ORACLE, iterates, ax.Orientation(180.0))
    assert len(rows) == len(iterates) - 1
    for row in rows:
        assert row.displacement_l1 >= 0.0
        assert row.sign_agrees == (np.sign(row.predicted_gain) == np.sign(row.realised_gain) != 0)
