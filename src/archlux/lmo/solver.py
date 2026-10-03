"""Linear oracle: solve ``min <c, x>`` over the polytope.

**This module does not know where ``c`` comes from.** This ignorance is deliberate and
is the heart of the architecture: the same solver serves classical legalisation (``c`` =
distance gradient) and performance-driven legalisation (``c`` = −illuminance gradient),
without a single line of difference. Making ``lmo`` aware of light breaks this reuse
(`ARCHITECTURE.md` §10).

Allowed dependencies: ``types``, ``errors``, ``geom``. **Never ``light``.**

Duality, phase I and Farkas: ``docs/formules/farkas.md``.
"""

from __future__ import annotations

import math
import threading
import time
import warnings
from collections import OrderedDict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

import numpy as np

from archlux._deprecation import Alias, lazy_aliases, renamed_parameters

# OR-Tools' SWIG bindings emit DeprecationWarnings while they import; with
# ``python -W error::DeprecationWarning`` the interpreter then crashes inside the C
# extension. The warnings are the vendor's, not ours: shield the import.
with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    from ortools.linear_solver import pywraplp

from archlux.arrays import FloatVector
from archlux.errors import InvalidInput, InvariantViolation

if TYPE_CHECKING:
    from archlux.geom.polytope import Polytope
    from archlux.lmo.cuts import Cut

__all__ = ["CacheLP", "LPSolution", "clear_cache", "solve"]

_CACHE_SIZE = 4
"""Number of models kept for the warm start, in the default cache.

A Frank-Wolfe loop works on **one** polytope; four is plenty, and bounds the memory
footprint of this cache.
"""


class CacheLP:
    """GLOP models already built, keyed by a polytope's ``id()``. Injectable, thread-safe.

    PLAN.md phase 4, block 4: replaces a module-global dict. A global mutable is harder
    to test in isolation (state silently leaks between tests unless every one remembers
    :func:`clear_cache`) and unsafe if two threads ever solve on different polytopes at
    once. An instance is safe on its own; :func:`solve` still defaults to one shared
    instance, so existing callers need no change.

    The key stays ``id(poly)`` (``Polytope`` is not hashable by value, and hashing its
    arrays on every call would cost more than the warm start saves). This is safe
    because the polytope is kept **by strong reference** in each entry: as long as it
    is there, its ``id()`` cannot be reassigned to another object, so the key stays
    correct.

    Thread-safety guarantee: every method holds an internal lock, and :func:`solve`
    checks a model **out** (:meth:`take`) for the whole set-objective / ``Solve()`` /
    read-solution sequence and puts it back afterwards. No two threads ever hold the
    same OR-Tools model at once; a thread that finds the model checked out simply
    builds its own (a cold solve, same answer). Concurrent :func:`solve` calls on one
    shared cache — same or different polytopes — are therefore safe.

    This cache changes no result, only the time: same inputs, same solution. The purity
    that `ARCHITECTURE.md` §3 demands of ``lmo`` — determinism, nothing learned — is
    preserved, and a property test checks it on every run.

    Parameters
    ----------
    maxsize : int, optional
        Number of models kept; the oldest is evicted first. Default 4.

    Raises
    ------
    InvalidInput
        ``maxsize`` below 1 (also a ``ValueError``).
    """

    def __init__(self, *, maxsize: int = _CACHE_SIZE) -> None:
        if maxsize < 1:
            raise InvalidInput("maxsize", f"must be at least 1, got {maxsize}")
        self._maxsize = maxsize
        self._lock = threading.Lock()
        self._entries: OrderedDict[int, tuple[Polytope, Any, list[Any], list[Any]]] = OrderedDict()

    def get(self, poly: Polytope) -> tuple[Any, list[Any], list[Any]] | None:
        """The ``(solver, variables, constraints)`` built for ``poly``, or ``None``."""
        with self._lock:
            entry = self._entries.get(id(poly))
            if entry is None:
                return None
            self._entries.move_to_end(id(poly))
            _, solver, variables, constraints = entry
            return solver, variables, constraints

    @renamed_parameters({"solveur": "solver", "contraintes": "constraints"})
    def put(
        self,
        poly: Polytope,
        solver: Any,  # noqa: ANN401 - an untyped OR-Tools model, no stubs
        variables: list[Any],
        constraints: list[Any],
    ) -> None:
        """Store the model built for ``poly``, evicting the oldest beyond ``maxsize``."""
        with self._lock:
            self._entries[id(poly)] = (poly, solver, variables, constraints)
            self._entries.move_to_end(id(poly))
            while len(self._entries) > self._maxsize:
                self._entries.popitem(last=False)

    def take(self, poly: Polytope) -> tuple[Any, list[Any], list[Any]] | None:
        """Remove and return the model built for ``poly`` (check it out), or ``None``.

        While checked out, no other thread can obtain that model: it either builds its
        own or waits for nothing. :func:`solve` hands it back with :meth:`put` once the
        solution is read.
        """
        with self._lock:
            entry = self._entries.pop(id(poly), None)
            if entry is None:
                return None
            _, solver, variables, constraints = entry
            return solver, variables, constraints

    def clear(self) -> None:
        """Forget every cached model."""
        with self._lock:
            self._entries.clear()


_DEFAULT_CACHE = CacheLP()
"""The cache :func:`solve` uses when its caller passes no ``cache``."""


@dataclass(frozen=True, slots=True)
class LPSolution:
    """Result of a call to the oracle.

    Attributes
    ----------
    status : {"optimal", "infaisable", "non_borne", "limite"}
        Never a boolean: "not optimal" covers three situations that call for three
        different reactions.
    duals : numpy.ndarray or None
        Dual prices, set only if ``duaux=True``. Translated into domain language by
        :mod:`archlux.certify.dual` via ``Polytope.origins``.
    farkas_certificate : numpy.ndarray or None
        Proof of infeasibility, set only if ``status == "infaisable"``.
    """

    x: FloatVector
    value: float
    status: Literal["optimal", "infaisable", "non_borne", "limite"]
    duals: FloatVector | None = None
    farkas_certificate: FloatVector | None = None
    farkas_certificate_eq: FloatVector | None = None
    """Farkas multipliers of the rows of ``A_eq`` (free sign, same convention as
    ``farkas_certificate``), set only when ``status == "infaisable"``."""
    iterations: int = 0
    time_ms: float = 0.0


def clear_cache() -> None:
    """Forget the models kept for the warm start, in the default cache.

    Useful for performance measurements, which must be able to guarantee a cold start.
    A caller with its own :class:`CacheLP` clears it directly, via :meth:`CacheLP.clear`.
    """
    _DEFAULT_CACHE.clear()


def _status(code: int) -> Literal["optimal", "infaisable", "non_borne", "limite"]:
    """Translate the OR-Tools return code into the project's status.

    Warning: **GLOP returns ``INFEASIBLE`` for an unbounded problem**, conflating two
    opposite situations — "the programme does not fit in the envelope" and "the
    objective has no finite optimum". The status returned here is therefore provisional:
    :func:`_is_feasible` settles it.
    """
    if code == pywraplp.Solver.OPTIMAL:
        return "optimal"
    if code == pywraplp.Solver.INFEASIBLE:
        return "infaisable"
    if code == pywraplp.Solver.UNBOUNDED:
        return "non_borne"
    return "limite"


def _glop_bound(solver: object, value: float, *, upper: bool) -> float:
    """Translate a Python bound (possibly infinite) into a GLOP bound."""
    if math.isfinite(value):
        return float(value)
    infinite = float(solver.infinity())  # type: ignore[attr-defined]
    return infinite if upper else -infinite


def _build_model(poly: Polytope, cuts: list[Cut] | None) -> tuple[Any, list[Any], list[Any]]:
    """Translate a polytope into a GLOP model.

    Returns
    -------
    tuple
        The solver, its variables in column order, and its constraints in the row
        order of ``A`` — this order is what makes the duals pairable with ``origins``.
    """
    solver = pywraplp.Solver.CreateSolver("GLOP")
    if solver is None:  # pragma: no cover - depends on the OR-Tools installation
        raise InvariantViolation(("GLOP backend unavailable",))

    names = sorted(poly.index, key=lambda name: poly.index[name])
    variables = [
        solver.NumVar(
            _glop_bound(solver, poly.bounds[i][0], upper=False),
            _glop_bound(solver, poly.bounds[i][1], upper=True),
            name,
        )
        for i, name in enumerate(names)
    ]

    constraints: list[Any] = []
    matrix = poly.A.tocsr()
    for row in range(matrix.shape[0]):
        t_start, end = matrix.indptr[row], matrix.indptr[row + 1]
        constraint = solver.RowConstraint(-solver.infinity(), float(poly.b[row]))
        for column, value in zip(
            matrix.indices[t_start:end], matrix.data[t_start:end], strict=True
        ):
            constraint.SetCoefficient(variables[column], float(value))
        constraints.append(constraint)

    eq_constraints = poly.A_eq.tocsr()
    for row in range(eq_constraints.shape[0]):
        t_start, end = eq_constraints.indptr[row], eq_constraints.indptr[row + 1]
        bound = float(poly.b_eq[row])
        constraint = solver.RowConstraint(bound, bound)
        for column, value in zip(
            eq_constraints.indices[t_start:end], eq_constraints.data[t_start:end], strict=True
        ):
            constraint.SetCoefficient(variables[column], float(value))

    for cut in cuts or ():
        # A cut is written ``Σ coeffs·v ≥ lower_bound``; GLOP takes the bound as is.
        constraint = solver.RowConstraint(cut.lower_bound, solver.infinity())
        for name, coefficient in cut.coefficients:
            constraint.SetCoefficient(variables[poly.index[name]], float(coefficient))

    return solver, variables, constraints


def _is_feasible(poly: Polytope, cuts: list[Cut] | None) -> bool:
    """Say whether the constraints admit at least one point, objective set aside.

    **The discriminant between "infeasible" and "unbounded"**, which GLOP returns under
    the same code. An LP with a zero objective cannot be unbounded: if it finds a point,
    the failure of the original problem came from its objective, not its programme.

    The model is identical to that of the real problem — cuts, equalities and bounds
    included — so that the verdict bears on the same system.
    """
    solver, _, _ = _build_model(poly, cuts)
    solver.Objective().SetMinimization()
    return _status(solver.Solve()) == "optimal"


def _farkas_certificate(poly: Polytope, cuts: list[Cut] | None) -> tuple[FloatVector, FloatVector]:
    """Extract a proof of infeasibility through the **auxiliary problem**.

    Each inequality ``a_i x ≤ b_i`` is relaxed by a slack variable ``s_i ≥ 0``, then
    ``Σ s_i`` is minimised. The auxiliary problem is always feasible; if its optimum is
    strictly positive, the original is not, and the dual prices of its constraints form
    a Farkas certificate — positive multipliers that make the system contradictory.

    Cuts are relaxed too. Without that, an impossible cut makes the auxiliary problem
    itself infeasible, and its duals no longer mean anything.

    Equalities of ``A_eq`` (tiling, fusions, frozen contacts) are relaxed too, by two
    slacks each; otherwise a conflict among them left the auxiliary problem without an
    optimum and the certificate empty ("origins not filled in": 68 of 200 noisy
    benchmark plans before batch 1.5c).

    Returns
    -------
    tuple of numpy.ndarray
        ``(y, z)``: one **non-negative** multiplier per row of ``A``, and one free
        multiplier per row of ``A_eq``, in the same sign convention.

        ``y``: one **positive** multiplier per row of ``A``. Crossed with ``origins``, it
        says **which constraints exclude each other**, which a bare "infeasible" does
        not. Real example: ``horizontal separation A|B`` and ``right outline B`` equal 1,
        the others 0 — two rooms of at least 2 m do not fit in 3 m.

        **Zero vector** if the auxiliary problem itself has no optimum. The rows of
        ``A`` and of ``A_eq`` are relaxed, not the variable bounds, so a conflict
        between bounds alone makes it unsolvable and its duals then mean nothing. An
        empty certificate reads "conflict not attributable to a row"; a wrong one
        cannot happen unnoticed, :func:`archlux.certify.farkas.verify_infeasibility`
        checks it exactly.

    Notes
    -----
    OR-Tools returns the duals of a ``≤`` constraint with the sign opposite to the Farkas
    convention. The multipliers are therefore negated here to be returned in the
    canonical form ``y ≥ 0``, the only one :mod:`archlux.certify.dual` can use without
    every reader having to know the backend's internal convention.
    """
    solver, variables, constraints = _build_model(poly, cuts)
    objective = solver.Objective()

    slacks = [solver.NumVar(0.0, solver.infinity(), f"ecart_{i}") for i in range(len(constraints))]
    for constraint, gap in zip(constraints, slacks, strict=True):
        constraint.SetCoefficient(gap, -1.0)
        objective.SetCoefficient(gap, 1.0)

    # Equality rows were created right after the rows of A (see _construire_modele).
    n_rows = len(constraints)
    equalities = solver.constraints()[n_rows : n_rows + poly.A_eq.shape[0]]
    for rank, equality in enumerate(equalities):
        above = solver.NumVar(0.0, solver.infinity(), f"eq_plus_{rank}")
        below = solver.NumVar(0.0, solver.infinity(), f"eq_minus_{rank}")
        equality.SetCoefficient(above, 1.0)
        equality.SetCoefficient(below, -1.0)
        objective.SetCoefficient(above, 1.0)
        objective.SetCoefficient(below, 1.0)

    # Cuts are relaxed the other way round: they are written ``≥``.
    for position, cut in enumerate(cuts or ()):
        slack = solver.NumVar(0.0, solver.infinity(), f"ecart_coupe_{position}")
        constraint = solver.RowConstraint(cut.lower_bound, solver.infinity())
        for name, coefficient in cut.coefficients:
            constraint.SetCoefficient(variables[poly.index[name]], float(coefficient))
        constraint.SetCoefficient(slack, 1.0)
        objective.SetCoefficient(slack, 1.0)

    objective.SetMinimization()
    if _status(solver.Solve()) != "optimal":
        return np.zeros(len(constraints), dtype=float), np.zeros(len(equalities), dtype=float)
    return (
        -np.array([c.dual_value() for c in constraints], dtype=float),
        -np.array([c.dual_value() for c in equalities], dtype=float),
    )


def _infeasible_solution(
    poly: Polytope,
    cuts: list[Cut] | None,
    n_var: int,
    solver: Any,  # noqa: ANN401 - an untyped OR-Tools model, no stubs
    lp_status: Literal["optimal", "infaisable", "non_borne", "limite"],
    t_start: float,
) -> LPSolution:
    """The unbounded or Farkas-certified result of a GLOP-reported infeasibility.

    Extracted from :func:`solve` (PLAN.md phase 4, block 4). GLOP conflates
    "infeasible" and "unbounded". The auxiliary problem settles it: a zero optimum
    means the constraints are satisfiable, hence the failure came from the objective.
    Without this distinction, ``api.legalize`` would raise "the programme does not fit
    in the envelope" on an open domain.
    """
    if _is_feasible(poly, cuts):
        return LPSolution(
            x=np.zeros(n_var),
            value=float("-inf"),
            status="non_borne",
            iterations=solver.iterations(),
            time_ms=(time.perf_counter() - t_start) * 1000.0,
        )
    farkas, farkas_eq = _farkas_certificate(poly, cuts)
    return LPSolution(
        x=np.zeros(n_var),
        value=float("inf"),
        status=lp_status,
        farkas_certificate=farkas,
        farkas_certificate_eq=farkas_eq,
        iterations=solver.iterations(),
        time_ms=(time.perf_counter() - t_start) * 1000.0,
    )


def _cached_model(
    poly: Polytope, cuts: list[Cut] | None, start: FloatVector | None, cache: CacheLP
) -> tuple[Any, list[Any], list[Any]]:
    """The GLOP model for ``poly``: reused from ``cache`` if warm-startable, else built.

    Extracted from :func:`solve` (PLAN.md phase 4, block 4). A model is reusable only
    with a ``start`` (the caller wants a warm start) and with no ``cuts``: a cut
    invalidates the cached model, since it changes the system, not just the objective.
    The model is **checked out** of ``cache`` (removed from it); the caller puts it back
    with :meth:`CacheLP.put` once done, so no two threads ever share it.
    A cold solve (no ``start``) without cuts builds a fresh model, which the caller then
    stores in place of any cached one: same answer, a refreshed entry.
    """
    if start is not None and not cuts:
        cached = cache.take(poly)
        if cached is not None:
            return cached
    return _build_model(poly, cuts)


@renamed_parameters({"depart": "start", "coupes": "cuts", "duaux": "duals"})
def solve(
    poly: Polytope,
    c: FloatVector,
    *,
    start: FloatVector | None = None,
    cuts: list[Cut] | None = None,
    duals: bool = False,
    cache: CacheLP | None = None,
) -> LPSolution:
    """Minimise ``<c, x>`` over the polytope, with the supplied cuts.

    OR-Tools GLOP backend.

    Parameters
    ----------
    poly : Polytope
        Feasible domain.
    c : numpy.ndarray
        Cost vector. **Its origin does not matter here**: geometric distance or
        illuminance gradient, the solver makes no difference.
    start : numpy.ndarray or None, optional
        Warm-start point. **Only its presence is used**: the values are not passed to
        GLOP, which restarts from its own current basis. What it allows is reuse of the
        model already built for this polytope — only the objective coefficients change.
        In a Frank-Wolfe loop, omitting it costs a factor of 3 to 5 (`ARCHITECTURE.md`
        §10). Its dimension is nevertheless validated: a malformed ``start`` signals a
        caller that picked the wrong polytope, and letting it through would return a
        correct result for the wrong reason.
    cuts : list of Cut or None, optional
        Accumulated cuts, fed back between two calls. They invalidate the cached model:
        their number changes the system, not just the objective.
    duals : bool, optional
        Extract the dual prices, in the row order of ``poly.A`` — this order is what
        makes them pairable with ``poly.origins``. **The rows of ``poly.A_eq`` and the
        cuts do not appear in it**: they have no label in ``origins``. A consequence to
        know: after :func:`archlux.geom.polytope.freeze_contacts`, the saturated
        constraints — the most informative ones — are moved into ``A_eq`` and their
        price therefore disappears from the diagnosis.
    cache : CacheLP or None, optional
        Where a built model is kept for the warm start. Defaults to one shared
        instance; pass an own :class:`CacheLP` for isolation (e.g. a test). Either
        way, concurrent calls are safe: the model is checked out of the cache for the
        whole solve, so two threads never share one OR-Tools model.

    Returns
    -------
    LPSolution
        Solution, status and diagnostics.

    Raises
    ------
    InvariantViolation
        Dimension of ``c`` or of ``start`` incompatible with the polytope.

    Guarantees
    ----------
    - Geometric: **exact** if ``status == "optimal"`` — the solution belongs to the
      polytope within the solver's tolerance. This membership is **independently
      rechecked** by :mod:`archlux.certify.proof` before anything is returned to the
      user: the solver is never taken at its word.
    - **The warm start does not change the solution**, only the time. Without that, a
      certificate would depend on the order of calls.
    - No light-performance guarantee is produced here.

    Complexity
    ----------
    Simplex. Budget: < 10 ms cold, < 3 ms warm, 15 rooms (`ARCHITECTURE.md` §9).

    Notes
    -----
    **Do not simplify this signature.** ``start`` and ``duals`` look useless at
    milestone 2; they are indispensable at milestones 3 and 5. Adding them afterwards
    forces the interface to be restructured to carry the state (`MILESTONE-2.md` §4).
    """
    t_start = time.perf_counter()
    n_var = len(poly.index)
    if c.shape != (n_var,):
        raise InvariantViolation((f"objective has shape {c.shape}, expected ({n_var},)",))
    if start is not None and start.shape != (n_var,):
        raise InvariantViolation((f"start has shape {start.shape}, expected ({n_var},)",))

    cache = cache if cache is not None else _DEFAULT_CACHE
    solver, variables, constraints = _cached_model(poly, cuts, start, cache)
    try:
        return _solve_model(poly, c, cuts, duals, solver, variables, constraints, t_start)
    finally:
        if not cuts:
            cache.put(poly, solver, variables, constraints)


def _solve_model(
    poly: Polytope,
    c: FloatVector,
    cuts: list[Cut] | None,
    duals: bool,
    solver: Any,  # noqa: ANN401 - an untyped OR-Tools model, no stubs
    variables: list[Any],
    constraints: list[Any],
    t_start: float,
) -> LPSolution:
    """Set the objective on a model this thread holds exclusively, solve, read back."""
    n_var = len(poly.index)

    objective = solver.Objective()
    for variable, coefficient in zip(variables, c, strict=True):
        objective.SetCoefficient(variable, float(coefficient))
    objective.SetMinimization()

    code = solver.Solve()
    lp_status = _status(code)
    elapsed_ms = (time.perf_counter() - t_start) * 1000.0

    if lp_status == "infaisable":
        return _infeasible_solution(poly, cuts, n_var, solver, lp_status, t_start)

    x = np.array([v.solution_value() for v in variables], dtype=float)
    return LPSolution(
        x=x,
        value=float(objective.Value()),
        status=lp_status,
        duals=(
            np.array([constraint.dual_value() for constraint in constraints], dtype=float)
            if duals
            else None
        ),
        iterations=solver.iterations(),
        time_ms=elapsed_ms,
    )


__getattr__ = lazy_aliases(
    __name__,
    {
        "SolutionLP": Alias(LPSolution, "archlux.lmo.solver.LPSolution"),
        "resoudre": Alias(solve, "archlux.lmo.solver.solve"),
        "vider_cache": Alias(clear_cache, "archlux.lmo.solver.clear_cache"),
    },
)
