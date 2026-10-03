"""Linear oracle: `MILESTONE-2.md` §4.

The module under test **does not know where ``c`` comes from**. Neither do these tests:
they pass it arbitrary cost vectors, never a "distance gradient".
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest
from scipy import sparse

from archlux.geom.graph import RelativeOrder
from archlux.geom.polytope import build_polytope
from archlux.lmo.cuts import Cut
from archlux.lmo.solver import solve
from archlux.types import Context, Orientation, Regulation, Structure

CTX = Context(
    structure=Structure(load_bearing_walls=()),
    orientation=Orientation(deg=0.0),
    outline=((0.0, 0.0), (10.0, 0.0), (10.0, 8.0), (0.0, 8.0)),
    regulation=Regulation(min_areas=(), min_width=1.5),
)

ORDER_1 = RelativeOrder(horizontal=(), vertical=(), rooms=("A",))
ORDER_AB = RelativeOrder(horizontal=(("A", "B"),), vertical=(), rooms=("A", "B"))

POLY_1 = build_polytope(ORDER_1, CTX)
POLY_AB = build_polytope(ORDER_AB, CTX)


class TestSimpleSolve:
    """Cases where the optimum can be read by hand."""

    def test_lp_trivial(self) -> None:
        """A single room, minimize ``x``: the solution is the lower bound."""
        sol = solve(POLY_1, c=np.array([1.0, 0.0, 0.0, 0.0]))
        assert sol.status == "optimal"
        assert sol.x[POLY_1.index["A.x"]] == pytest.approx(0.0)

    def test_maximizing_is_minimizing_the_opposite(self) -> None:
        """``c = −e_x`` pushes ``x`` to its upper bound, without the solver knowing why."""
        c = np.zeros(4)
        c[POLY_1.index["A.x"]] = -1.0
        sol = solve(POLY_1, c=c)
        # x + w <= 10 and w >= 1.5: the maximum of x is 8.5.
        assert sol.x[POLY_1.index["A.x"]] == pytest.approx(8.5)

    def test_the_solution_is_in_the_polytope(self) -> None:
        """Checked by ``Polytope.contains``, which borrows nothing from the solver."""
        c = np.array([1.0, 1.0, -1.0, -1.0, 1.0, 1.0, -1.0, -1.0])
        sol = solve(POLY_AB, c=c)
        assert sol.status == "optimal"
        assert POLY_AB.contains(sol.x, tol=1e-7)

    def test_the_diagnostics_are_filled_in(self) -> None:
        """``time_ms`` and ``iterations`` are not decorative: §9 measures them."""
        sol = solve(POLY_AB, c=np.zeros(8))
        assert sol.time_ms > 0.0
        assert sol.iterations >= 0


class TestDuals:
    """Dual prices are extracted only when asked for."""

    def test_absent_by_default(self) -> None:
        """Extracting them costs; not asking for them must mean not paying for them."""
        assert solve(POLY_AB, c=np.zeros(8)).duals is None

    def test_present_on_request(self) -> None:
        """One dual per row of ``A``: the matching with ``origins`` depends on it."""
        c = np.zeros(8)
        c[POLY_AB.index["A.w"]] = -1.0
        sol = solve(POLY_AB, c=c, duals=True)
        assert sol.duals is not None
        assert sol.duals.shape == (POLY_AB.A.shape[0],)

    def test_an_active_constraint_has_a_non_zero_price(self) -> None:
        """Widening ``A`` hits the outline: that row must cost something."""
        c = np.zeros(8)
        c[POLY_AB.index["A.w"]] = -1.0
        sol = solve(POLY_AB, c=c, duals=True)
        assert sol.duals is not None
        actives = {POLY_AB.origins[i] for i, price in enumerate(sol.duals) if abs(price) > 1e-9}
        assert actives, "no active constraint although the optimum is on a face"


class TestInfeasible:
    """An infeasibility carries its proof, never a mere message."""

    @staticmethod
    def _overconstrained_polytope() -> object:
        """Two rooms of at least 2 m side by side in a 3 m outline."""
        ctx = Context(
            structure=Structure(load_bearing_walls=()),
            orientation=Orientation(deg=0.0),
            outline=((0.0, 0.0), (3.0, 0.0), (3.0, 8.0), (0.0, 8.0)),
            regulation=Regulation(min_areas=(), min_width=2.0),
        )
        return build_polytope(ORDER_AB, ctx)

    def test_infeasible_produces_a_certificate(self) -> None:
        """The programme does not fit in the envelope: it must be proved, not claimed."""
        poly = self._overconstrained_polytope()
        sol = solve(poly, c=np.zeros(8))  # type: ignore[arg-type]
        assert sol.status == "infaisable"
        assert sol.farkas_certificate is not None
        assert sol.farkas_certificate.shape == (poly.A.shape[0],)

    def test_the_certificate_points_at_real_constraints(self) -> None:
        """A non-zero Farkas certificate, otherwise it explains nothing."""
        poly = self._overconstrained_polytope()
        sol = solve(poly, c=np.zeros(8))  # type: ignore[arg-type]
        assert sol.farkas_certificate is not None
        assert np.any(np.abs(sol.farkas_certificate) > 1e-9)
        assert np.all(sol.farkas_certificate >= -1e-9), "the multipliers are non-negative"


class TestWarmStart:
    """`ARCHITECTURE.md` §10: an LP without ``start=`` in a loop costs ×3 to ×5."""

    def test_the_result_is_identical_cold_and_warm(self) -> None:
        """**The property that matters.**

        The warm start is a time optimization; if it changed the solution, it would
        change the certificate, and two runs of the same plan would diverge.
        """
        c1 = np.array([1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0])
        c2 = np.array([0.0, 1.0, -1.0, 0.0, 0.0, 1.0, 0.0, -1.0])
        cold = solve(POLY_AB, c=c2)
        warm = solve(POLY_AB, c=c2, start=solve(POLY_AB, c=c1).x)
        assert warm.status == cold.status
        assert np.allclose(warm.x, cold.x, atol=1e-7)

    def test_a_start_of_the_wrong_dimension_is_refused(self) -> None:
        """A mismatched vector is a calling bug, not data."""
        from archlux.errors import InvariantViolation

        with pytest.raises(InvariantViolation, match="start has shape"):
            solve(POLY_AB, c=np.zeros(8), start=np.zeros(3))


class TestRareStatuses:
    """A status other than optimal covers three situations, not one."""

    def test_an_unbounded_domain_is_reported(self) -> None:
        """Without an upper bound, minimizing ``x`` has no finite solution.

        The polytope of the project is always bounded by its outline; this status exists
        so that ``solve`` can tell "open domain" from "impossible programme" instead of
        merging both into a boolean.
        """
        unbounded = replace(POLY_1, bounds=tuple((-np.inf, np.inf) for _ in POLY_1.bounds))
        sol = solve(unbounded, c=np.array([1.0, 0.0, 0.0, 0.0]))
        assert sol.status in ("non_borne", "limite")

    def test_the_equalities_are_honoured(self) -> None:
        """``A_eq`` is empty today, but will carry the load-bearing structure (ADR-7).

        Leaving it untested until then would mean discovering its translation to GLOP
        the day it decides the position of a load-bearing wall.
        """
        with_equality = replace(
            POLY_1,
            A_eq=sparse.csr_matrix(
                ([1.0], ([0], [POLY_1.index["A.x"]])), shape=(1, len(POLY_1.index))
            ),
            b_eq=np.array([2.5]),
        )
        sol = solve(with_equality, c=np.array([1.0, 0.0, 0.0, 0.0]))
        assert sol.status == "optimal"
        assert sol.x[POLY_1.index["A.x"]] == pytest.approx(2.5)

    def test_an_objective_of_the_wrong_dimension_is_refused(self) -> None:
        """A mismatched cost vector is a calling bug."""
        from archlux.errors import InvariantViolation

        with pytest.raises(InvariantViolation, match="objective has shape"):
            solve(POLY_1, c=np.zeros(99))


class TestCuts:
    """The cuts given are added to the system, with their origin."""

    def test_a_cut_constrains_the_solution(self) -> None:
        """``w_A ≥ 4`` forbids the solution the LP would choose without it."""
        c = np.zeros(8)
        c[POLY_AB.index["A.w"]] = 1.0  # minimize w_A → it would go to 1.5
        without_cut = solve(POLY_AB, c=c)
        with_cut = solve(
            POLY_AB,
            c=c,
            cuts=[Cut(coefficients=(("A.w", 1.0),), lower_bound=4.0, origin="trial")],
        )
        assert without_cut.x[POLY_AB.index["A.w"]] == pytest.approx(1.5)
        assert with_cut.x[POLY_AB.index["A.w"]] == pytest.approx(4.0)

    def test_an_infeasible_cut_is_reported(self) -> None:
        """An impossible cut makes the system infeasible; it is not silently ignored."""
        cut = Cut(coefficients=(("A.w", 1.0),), lower_bound=99.0, origin="impossible")
        sol = solve(POLY_AB, c=np.zeros(8), cuts=[cut])
        assert sol.status == "infaisable"
