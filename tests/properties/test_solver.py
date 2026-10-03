"""Properties of the linear oracle: `MILESTONE-2.md` §4."""

from __future__ import annotations

import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st

from archlux.geom.graph import RelativeOrder
from archlux.geom.polytope import build_polytope
from archlux.lmo.solver import solve
from archlux.types import Context
from tests.properties.strategies import contexts, objective_vectors, valid_orders


@given(order=valid_orders(), ctx=contexts(), draws=st.data())
@settings(max_examples=150, deadline=None)
def test_the_solution_is_feasible(order: RelativeOrder, ctx: Context, draws: st.DataObject) -> None:
    """Every solution returned as optimal belongs to the polytope.

    The check goes through ``Polytope.contains``, which borrows nothing from the solver:
    if GLOP is wrong, the check catches it.
    """
    poly = build_polytope(order, ctx)
    c = draws.draw(objective_vectors(len(poly.index)))
    sol = solve(poly, c)
    if sol.status == "optimal":
        assert poly.contains(sol.x, tol=1e-7)


@given(order=valid_orders(), ctx=contexts(), draws=st.data())
@settings(max_examples=100, deadline=None)
def test_warm_start_does_not_change_the_solution(
    order: RelativeOrder, ctx: Context, draws: st.DataObject
) -> None:
    """The warm start speeds things up; it must decide nothing.

    If it changed the solution, it would change the certificate, and two runs of the
    same plan would stop being reproducible, which the README forbids.
    """
    poly = build_polytope(order, ctx)
    c = draws.draw(objective_vectors(len(poly.index)))
    cold = solve(poly, c)
    warm = solve(poly, c, start=np.zeros(len(poly.index)))
    assert cold.status == warm.status
    if cold.status == "optimal":
        assert cold.value == np.float64(warm.value) or abs(cold.value - warm.value) < 1e-6


@given(order=valid_orders(), ctx=contexts())
@settings(max_examples=100, deadline=None)
def test_a_zero_objective_returns_a_feasible_point(order: RelativeOrder, ctx: Context) -> None:
    """With ``c = 0``, the LP reduces to a feasibility question.

    That is the mode ``certify`` uses to tell "impossible programme" from "badly chosen
    objective".
    """
    poly = build_polytope(order, ctx)
    sol = solve(poly, np.zeros(len(poly.index)))
    assert sol.status in ("optimal", "infaisable")  # lang-ok: solver status value
    if sol.status == "optimal":
        assert poly.contains(sol.x, tol=1e-7)
    else:
        assert sol.farkas_certificate is not None
