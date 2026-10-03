"""Frank-Wolfe: `MILESTONE-3.md` §5. The oracle is ``lmo.solve``."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise

import numpy as np
import pytest

from archlux.geom.graph import RelativeOrder
from archlux.geom.polytope import build_polytope
from archlux.lmo.solver import solve
from archlux.solve.frank_wolfe import AwayStepStrategy, frank_wolfe
from archlux.types import Context, Orientation, Regulation, Structure

CTX = Context(
    structure=Structure(load_bearing_walls=()),
    orientation=Orientation(deg=0.0),
    outline=((0.0, 0.0), (10.0, 0.0), (10.0, 8.0), (0.0, 8.0)),
    regulation=Regulation(min_areas=(), min_width=1.5),
)
POLY = build_polytope(RelativeOrder(horizontal=(), vertical=(), rooms=("A",)), CTX)
NORTH = Orientation(deg=0.0)


@dataclass(frozen=True, slots=True)
class LinearObjective:
    """Affine surrogate: the maximum over a polytope is a vertex."""

    c: np.ndarray
    indicator: str = "sDA"

    def evaluate(self, x: np.ndarray, orientation: Orientation, *, glazing: object = None) -> float:
        del orientation, glazing
        return float(self.c @ x)

    def gradient(
        self, x: np.ndarray, orientation: Orientation, *, glazing: object = None
    ) -> np.ndarray:
        del x, orientation, glazing
        return self.c

    def uncertainty(
        self, x: np.ndarray, orientation: Orientation, *, glazing: object = None
    ) -> float:
        del x, orientation, glazing
        return 0.08


def _feasible_start() -> np.ndarray:
    """An interior point: a 4×4 room in the corner, min width 1.5."""
    x = np.zeros(4)
    x[POLY.index["A.x"]] = 0.0
    x[POLY.index["A.y"]] = 0.0
    x[POLY.index["A.w"]] = 4.0
    x[POLY.index["A.h"]] = 4.0
    assert POLY.contains(x)
    return x


def test_every_iterate_is_in_the_polytope() -> None:
    objective = LinearObjective(c=np.array([0.0, 0.0, 1.0, 1.0]))
    result = frank_wolfe(POLY, objective, NORTH, _feasible_start(), max_iter=8)
    assert result.trace.iterates
    assert all(POLY.contains(point, tol=1e-7) for point in result.trace.iterates)


def test_non_decreasing_objective() -> None:
    objective = LinearObjective(c=np.array([0.0, 0.0, 1.0, 1.0]))
    values = frank_wolfe(POLY, objective, NORTH, _feasible_start(), max_iter=8).trace.values
    for before, after in pairwise(values):
        assert after >= before - 1e-9


def test_gap_bounds_the_distance_to_the_linear_optimum() -> None:
    """On a linear objective, the LMO gives the optimum: the gap bounds the distance."""
    c = np.array([0.0, 0.0, 1.0, 0.0])
    objective = LinearObjective(c=c)
    x0 = _feasible_start()
    result = frank_wolfe(POLY, objective, NORTH, x0, max_iter=10, away_steps=False)
    optimum = solve(POLY, -c, start=x0)
    assert optimum.status == "optimal"
    distance = float(c @ optimum.x) - result.value
    assert distance <= result.gap + 1e-6


def test_small_final_duality_on_linear() -> None:
    """On a linear objective, the LMO is exact: the gap falls below the tolerance."""
    result = frank_wolfe(
        POLY,
        LinearObjective(c=np.array([0.0, 0.0, 1.0, 0.0])),
        NORTH,
        _feasible_start(),
        max_iter=12,
        away_steps=False,
    )
    assert result.gap <= 1e-4 + 1e-9


def test_warm_start_always_passes_start(monkeypatch: pytest.MonkeyPatch) -> None:
    """ARCHITECTURE.md §10: omitting ``start=`` costs a factor of 3 to 5."""
    calls: list[np.ndarray | None] = []
    original = solve

    def tracer(poly, c, *, start=None, cuts=None, duals=False):
        calls.append(start)
        return original(poly, c, start=start, cuts=cuts, duals=duals)

    monkeypatch.setattr("archlux.solve.frank_wolfe.solve", tracer)
    frank_wolfe(
        POLY,
        LinearObjective(c=np.array([0.0, 0.0, 1.0, 0.0])),
        NORTH,
        _feasible_start(),
        max_iter=4,
        away_steps=False,
    )
    assert calls
    assert all(start is not None for start in calls)


@pytest.mark.parametrize("enabled", [False, True])
def test_a_strategy_replaces_away_steps(enabled: bool) -> None:
    """PLAN.md phase 4, block 5: injecting ``AwayStepStrategy`` matches ``away_steps=``."""
    objective = LinearObjective(c=np.array([0.0, 0.0, 1.0, 0.0]))
    x0 = _feasible_start()
    via_flag = frank_wolfe(POLY, objective, NORTH, x0, max_iter=8, away_steps=enabled)
    via_strategy = frank_wolfe(
        POLY, objective, NORTH, x0, max_iter=8, strategy=AwayStepStrategy(enabled=enabled)
    )
    np.testing.assert_array_equal(via_flag.x, via_strategy.x)
    assert via_flag.value == via_strategy.value
    assert via_flag.gap == via_strategy.gap
    assert via_flag.status == via_strategy.status
    assert via_flag.iterations == via_strategy.iterations
    assert via_flag.trace.values == via_strategy.trace.values
    assert via_flag.trace.gaps == via_strategy.trace.gaps
    assert via_flag.trace.status == via_strategy.trace.status
    assert via_flag.trace.final_gap == via_strategy.trace.final_gap
    flags = [(it.k, it.step, it.away_step) for it in via_flag.trace.iterations]
    injected = [(it.k, it.step, it.away_step) for it in via_strategy.trace.iterations]
    assert flags == injected
    assert len(via_flag.trace.iterates) == len(via_strategy.trace.iterates)
    for a, b in zip(via_flag.trace.iterates, via_strategy.trace.iterates, strict=True):
        np.testing.assert_array_equal(a, b)


def test_a_custom_strategy_is_consulted_every_iteration() -> None:
    """A new step rule plugs in without editing :func:`frank_wolfe` (item 20)."""
    calls: list[int] = []

    class CountingStrategy:
        def propose(
            self,
            gradient: np.ndarray,
            x: np.ndarray,
            fw_vertex: np.ndarray,
            vertices: list[np.ndarray],
            weights: list[float],
        ) -> tuple[np.ndarray, float, bool, int | None]:
            calls.append(len(calls))
            return fw_vertex - x, 1.0, False, None

    result = frank_wolfe(
        POLY,
        LinearObjective(c=np.array([0.0, 0.0, 1.0, 0.0])),
        NORTH,
        _feasible_start(),
        max_iter=5,
        strategy=CountingStrategy(),
    )
    assert calls
    assert len(calls) <= result.iterations + 1


def test_strategy_with_away_steps_false_warns() -> None:
    """``away_steps=False`` is ignored when ``strategy`` is given: say so."""
    with pytest.warns(UserWarning, match="away_steps"):
        frank_wolfe(
            POLY,
            LinearObjective(c=np.array([0.0, 0.0, 1.0, 0.0])),
            NORTH,
            _feasible_start(),
            max_iter=2,
            away_steps=False,
            strategy=AwayStepStrategy(),
        )
