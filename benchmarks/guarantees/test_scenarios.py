"""The benchmark generator must produce valid, constrained, reproducible inputs."""

from __future__ import annotations

import pytest
from benchmarks.guarantees.scenarios import MIN_SIDE_M, generate, perturb
from tests import checkers


@pytest.mark.parametrize("index", range(200))
def test_every_scenario_is_valid_under_its_own_context(index: int) -> None:
    """Any violation measured later is introduced by legalize, not by the input."""
    scenario = generate(seed=17, index=index)
    assert checkers.violations(scenario.plan, scenario.context) == []
    assert len(scenario.plan.pieces) >= 2
    assert min(min(r.w, r.h) for r in scenario.plan.pieces) >= MIN_SIDE_M - 1e-9


def test_the_load_bearing_wall_spans_the_building() -> None:
    """The first cut is a full-span bearing partition present in the plan."""
    for index in range(50):
        scenario = generate(seed=17, index=index)
        (wall,) = scenario.context.structure.murs_porteurs
        xs = [x for x, _ in scenario.context.contour]
        ys = [y for _, y in scenario.context.contour]
        span = abs(wall.a[0] - wall.b[0]) + abs(wall.a[1] - wall.b[1])
        assert span in (max(xs) - min(xs), max(ys) - min(ys))
        assert wall in scenario.plan.murs


def test_generation_is_deterministic() -> None:
    """Same seed and index, same scenario; another seed, another one."""
    assert generate(seed=17, index=3) == generate(seed=17, index=3)
    assert generate(seed=17, index=3) != generate(seed=18, index=3)


def test_perturbation_is_small_and_reproducible() -> None:
    """Noise of a few centimetres, identical for the same seed."""
    plan = generate(seed=17, index=0).plan
    noisy = perturb(plan, seed=1)
    assert noisy == perturb(plan, seed=1)
    moved = [abs(a.x - b.x) for a, b in zip(plan.pieces, noisy.pieces, strict=True)]
    assert 0 < max(moved) <= 0.03
