"""Frank-Wolfe invariants under random objectives, budgets and penalties (spec 1.2, 1.6).

Whatever the objective, the run returns a point of its domain, never moves further than
its budget from the reference, records one displacement per iterate, and never lets
its (penalised) objective decrease.
"""

from __future__ import annotations

from itertools import pairwise

import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st

from archlux.solve.frank_wolfe import frank_wolfe
from tests.unit.test_frank_wolfe import NORTH, POLY, LinearObjective, _feasible_start

_COEFFICIENT = st.floats(min_value=-5.0, max_value=5.0, allow_nan=False)


@settings(max_examples=60, deadline=None, derandomize=True)
@given(
    c=st.lists(_COEFFICIENT, min_size=4, max_size=4),
    budget=st.one_of(st.none(), st.floats(min_value=0.0, max_value=6.0)),
    penalty=st.sampled_from((0.0, 0.1, 1.0, 10.0)),
    max_iter=st.integers(min_value=0, max_value=30),
)
def test_a_run_stays_in_its_domain_and_within_its_budget(
    c: list[float], budget: float | None, penalty: float, max_iter: int
) -> None:
    start = _feasible_start()
    result = frank_wolfe(
        POLY,
        LinearObjective(c=np.array(c)),
        NORTH,
        start,
        max_iter=max_iter,
        budget=budget,
        penalty=penalty,
    )
    assert POLY.contains(result.x, tol=1e-6)
    assert result.iterations <= max_iter
    assert len(result.trace.displacements) == len(result.trace.iterations)
    if budget is not None:
        assert max(result.trace.displacements) <= budget + 1e-6
        if max(result.trace.displacements) < budget - 1e-6:
            assert result.trace.budget_active == ()
    for before, after in pairwise(result.trace.objectives):
        assert after >= before - 1e-9
    assert result.converged == (result.status == "converged")
