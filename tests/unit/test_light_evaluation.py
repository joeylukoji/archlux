"""Held-out evaluation and before/after comparison of a surrogate (spec 1.3)."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pytest

from archlux.errors import InvalidInput
from archlux.light.analytic import AnalyticSurrogate
from archlux.light.evaluation import (
    EvaluationCase,
    compare_before_after,
    evaluate_surrogate,
    orientation_sector,
    summarize_gains,
)
from archlux.light.reference import ClosedFormReference, ReferenceMeasure, ReferenceUnavailable
from archlux.light.split_flux import SplitFluxOracle
from archlux.types import Orientation


def _plan(c: float) -> np.ndarray:
    return np.array([0.0, 0.0, c, 4.5, c, 0.0, 12.0 - c, 4.5])


CASES = tuple(
    EvaluationCase(
        id=f"p{k}",
        x=_plan(4.0 + 0.25 * k),
        orientation=Orientation(deg=45.0 * k),
        room_type="living" if k % 2 else "bedroom",
        window_config="none",
    )
    for k in range(12)
)
ORACLE = SplitFluxOracle()


@dataclass(frozen=True)
class FakePhysical:
    """A 'physical' reference whose value is a fixed multiple of the oracle."""

    factor: float = 1.0
    unit: str = "lux"
    kind: str = "physical"
    fail: bool = False

    def measure(self, x, orientation, *, glazing=None):  # type: ignore[no-untyped-def]
        if self.fail:
            raise ReferenceUnavailable("engine missing")
        value = self.factor * ORACLE.evaluate(x, orientation)
        return ReferenceMeasure(value, self.unit, "physical", "fake")


def test_a_case_used_for_training_is_refused() -> None:
    with pytest.raises(InvalidInput, match="not held out"):
        evaluate_surrogate(ORACLE, CASES, ClosedFormReference(ORACLE), seed=1, training_ids={"p3"})


def test_duplicate_ids_are_refused() -> None:
    with pytest.raises(InvalidInput, match="share an id"):
        evaluate_surrogate(
            ORACLE, CASES + CASES[:1], ClosedFormReference(ORACLE), seed=1, training_ids=()
        )


def test_the_oracle_against_itself_has_zero_error_and_unit_correlation() -> None:
    result = evaluate_surrogate(ORACLE, CASES, ClosedFormReference(ORACLE), seed=1, training_ids=())
    assert result.reference_kind == "closed_form"
    assert result.overall.n == 12 and result.overall.same_unit
    assert result.overall.mae.value == pytest.approx(0.0, abs=1e-12)
    assert result.overall.pearson.value == pytest.approx(1.0)
    assert result.overall.spearman.value == pytest.approx(1.0)
    assert [label for label, _ in result.by_room_type] == ["bedroom", "living"]
    assert {label for label, _ in result.by_orientation} == {"0", "90", "180", "270"}


def test_errors_are_reported_with_an_interval() -> None:
    result = evaluate_surrogate(
        AnalyticSurrogate(), CASES, ClosedFormReference(ORACLE), seed=1, training_ids=()
    )
    mae = result.overall.mae
    assert mae.low <= mae.value <= mae.high and mae.value > 0.0
    assert result.overall.bias.value < 0.0  # the analytic part misses the split flux


def test_different_units_give_correlations_only() -> None:
    result = evaluate_surrogate(ORACLE, CASES, FakePhysical(factor=3.0), seed=1, training_ids=())
    assert not result.overall.same_unit
    assert math.isnan(result.overall.mae.value) and math.isnan(result.overall.bias.value)
    assert result.overall.pearson.value == pytest.approx(1.0)


def test_unmeasured_cases_are_counted_not_scored() -> None:
    result = evaluate_surrogate(ORACLE, CASES, FakePhysical(fail=True), seed=1, training_ids=())
    assert result.n_unmeasured == 12 and result.overall.n == 0
    assert math.isnan(result.overall.mae.value)


def test_sectors_are_circular() -> None:
    assert orientation_sector(359.0) == "0"
    assert orientation_sector(100.0) == "90"
    assert orientation_sector(46.0, 45.0) == "45"


def _pairs(before: float, after: float) -> list[tuple]:  # type: ignore[type-arg]
    return [("a", _plan(before), _plan(after), Orientation(deg=180.0), None)]


def test_a_closed_form_reference_never_confirms_a_gain() -> None:
    rows = compare_before_after(ORACLE, ClosedFormReference(ORACLE), _pairs(5.0, 6.0))
    assert rows[0].status == "closed_form_only"
    assert rows[0].gap_pct == pytest.approx(0.0, abs=1e-9)
    assert rows[0].displacement_l1 == pytest.approx(3.0)  # c moves w0, x1 and w1
    assert summarize_gains(rows).claim == "predicted"


def test_a_physical_reference_confirms_or_contradicts() -> None:
    probe = compare_before_after(ORACLE, FakePhysical(), _pairs(5.0, 6.0))
    pairs = _pairs(5.0, 6.0) if probe[0].predicted_gain_pct > 0.0 else _pairs(6.0, 5.0)
    rows = compare_before_after(ORACLE, FakePhysical(), pairs)
    assert rows[0].status == "confirmed"
    assert summarize_gains(rows).claim == "confirmed"
    contradicted = compare_before_after(ORACLE, FakePhysical(factor=-1.0), pairs)
    assert contradicted[0].status == "contradicted"
    assert summarize_gains(contradicted).claim == "predicted"


def test_an_unavailable_reference_leaves_the_gain_predicted_only() -> None:
    rows = compare_before_after(ORACLE, FakePhysical(fail=True), _pairs(5.0, 6.0))
    assert rows[0].status == "predicted_only" and math.isnan(rows[0].reference_gain_pct)
    summary = summarize_gains(rows)
    assert summary.claim == "predicted" and summary.n_measured == 0
