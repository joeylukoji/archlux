"""Displacement metrics and budget sweeps (article revision, spec 1.6 and 1.7)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from archlux.errors import InvalidInput
from archlux.solve.displacement import (
    count_saturated,
    measure_displacement,
    summarize,
)
from archlux.solve.sweep import success_rate, sweep
from archlux.types import Opening, Plan, Room, Wall
from tests.unit.test_frank_wolfe import NORTH, POLY, LinearObjective, _feasible_start


def _plan(*rooms: Room, walls: tuple[Wall, ...] = (), openings: tuple[Opening, ...] = ()) -> Plan:
    return Plan(rooms=rooms, walls=walls, openings=openings)


def _room(identifier: str, x: float, y: float, w: float, h: float) -> Room:
    return Room(id=identifier, type="living_room", x=x, y=y, w=w, h=h)


# --- measure_displacement --------------------------------------------------------------


def test_an_unchanged_plan_has_no_displacement() -> None:
    plan = _plan(_room("a", 0, 0, 4, 3), _room("b", 4, 0, 2, 3))
    moved = measure_displacement(plan, plan)
    assert moved.max_wall_shift == 0.0
    assert moved.max_area_change == 0.0
    assert moved.max_opening_shift == 0.0
    assert moved.combined() == 0.0


def test_a_partition_moved_shifts_the_two_rooms_that_share_it() -> None:
    before = _plan(_room("a", 0, 0, 4, 3), _room("b", 4, 0, 2, 3))
    after = _plan(_room("a", 0, 0, 4.5, 3), _room("b", 4.5, 0, 1.5, 3))
    moved = measure_displacement(before, after)
    shifts = {room.room_id: room for room in moved.rooms}
    assert shifts["a"].wall_shift == pytest.approx(0.5)
    assert shifts["b"].wall_shift == pytest.approx(0.5)
    assert shifts["a"].area_change == pytest.approx(1.5)
    assert shifts["b"].area_change == pytest.approx(-1.5)
    assert shifts["b"].relative_area_change == pytest.approx(-0.25)
    assert moved.max_wall_shift == pytest.approx(0.5)
    assert moved.max_relative_area_change == pytest.approx(0.25)


def test_a_translated_room_shifts_all_its_walls() -> None:
    before = _plan(_room("a", 0, 0, 4, 3))
    after = _plan(_room("a", 0.2, 0.7, 4, 3))
    moved = measure_displacement(before, after)
    assert moved.max_wall_shift == pytest.approx(0.7)
    assert moved.max_area_change == pytest.approx(0.0)


def test_an_opening_follows_its_wall() -> None:
    window = Opening(id="w1", wall_id="south", s=0.5, relative_width=0.4)
    before = _plan(
        _room("a", 0, 0, 4, 3),
        walls=(Wall(id="south", a=(0.0, 0.0), b=(4.0, 0.0)),),
        openings=(window,),
    )
    after = _plan(
        _room("a", 0, 0, 5, 3),
        walls=(Wall(id="south", a=(0.0, 0.0), b=(5.0, 0.0)),),
        openings=(window,),
    )
    moved = measure_displacement(before, after)
    assert dict(moved.openings)["w1"] == pytest.approx(0.5)  # centre from x=2 to x=2.5
    assert moved.max_opening_shift == pytest.approx(0.5)


def test_the_combined_cost_weights_its_three_terms() -> None:
    before = _plan(_room("a", 0, 0, 4, 3), _room("b", 4, 0, 2, 3))
    after = _plan(_room("a", 0, 0, 4.5, 3), _room("b", 4.5, 0, 1.5, 3))
    moved = measure_displacement(before, after)
    assert moved.combined(wall=1.0, area=0.0, opening=0.0) == pytest.approx(0.5)
    assert moved.combined(wall=0.0, area=2.0, opening=0.0) == pytest.approx(0.5)
    assert moved.combined(wall=1.0, area=1.0, opening=1.0) == pytest.approx(0.75)


def test_plans_with_different_rooms_cannot_be_compared() -> None:
    with pytest.raises(InvalidInput):
        measure_displacement(_plan(_room("a", 0, 0, 4, 3)), _plan(_room("b", 0, 0, 4, 3)))


# --- distributions ------------------------------------------------------------------------


def test_a_summary_reports_centre_spread_and_extremes() -> None:
    summary = summarize([0.0, 1.0, 2.0, 3.0, 3.0], bins=3)
    assert summary.n == 5
    assert summary.mean == pytest.approx(1.8)
    assert summary.median == pytest.approx(2.0)
    assert summary.minimum == 0.0
    assert summary.maximum == 3.0
    assert summary.p10 <= summary.median <= summary.p90
    assert sum(summary.counts) == 5
    assert len(summary.edges) == len(summary.counts) + 1


def test_an_empty_summary_is_refused() -> None:
    with pytest.raises(InvalidInput):
        summarize([])


def test_a_non_finite_value_is_refused() -> None:
    with pytest.raises(InvalidInput):
        summarize([1.0, math.nan])


def test_saturated_variants_are_counted_against_the_budget() -> None:
    """Milestone 9 reads "36 of 48 at the budget": this is that count."""
    assert count_saturated([3.0, 2.9999999, 2.04, 3.0], budget=3.0) == 3
    assert count_saturated([], budget=3.0) == 0


# --- sweeps --------------------------------------------------------------------------------


def _objective() -> LinearObjective:
    return LinearObjective(c=np.array([0.0, 0.0, 1.0, 0.5]))


def test_a_sweep_runs_every_combination_of_its_grid() -> None:
    rows = sweep(
        POLY,
        _objective(),
        NORTH,
        _feasible_start(),
        max_iters=(0, 1, 50),
        budgets=(None, 0.5),
        penalties=(0.0, 1.0),
    )
    assert len(rows) == 3 * 2 * 2
    assert {(row.max_iter, row.budget, row.penalty) for row in rows} == {
        (m, b, p) for m in (0, 1, 50) for b in (None, 0.5) for p in (0.0, 1.0)
    }
    for row in rows:
        assert row.iterations <= row.max_iter
        assert row.time_ms >= 0.0
        if row.budget is not None:
            assert row.displacement <= row.budget + 1e-9


def test_a_sweep_shows_when_the_budget_binds() -> None:
    rows = sweep(POLY, _objective(), NORTH, _feasible_start(), max_iters=(50,), budgets=(0.5, 20.0))
    by_budget = {row.budget: row for row in rows}
    assert by_budget[0.5].budget_bound
    assert not by_budget[20.0].budget_bound
    assert by_budget[20.0].gain > by_budget[0.5].gain


def test_success_rate_counts_converged_runs_only() -> None:
    rows = sweep(POLY, _objective(), NORTH, _feasible_start(), max_iters=(0, 1, 50))
    converged, total = success_rate(rows)
    assert total == 3
    assert converged == sum(row.status == "converged" for row in rows)
    assert converged >= 1
