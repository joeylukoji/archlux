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
import time
import warnings
from collections import OrderedDict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

import numpy as np

from archlux._deprecation import Alias, lazy_aliases

# OR-Tools' SWIG bindings emit DeprecationWarnings while they import; with
# ``python -W error::DeprecationWarning`` the interpreter then crashes inside the C
# extension. The warnings are the vendor's, not ours: shield the import.
with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    from ortools.linear_solver import pywraplp

from archlux.arrays import VecteurF
from archlux.errors import InvariantViolation

if TYPE_CHECKING:
    from archlux.geom.polytope import Polytope
    from archlux.lmo.cuts import Cut

__all__ = ["LPSolution", "clear_cache", "solve"]

_TAILLE_CACHE = 4
"""Number of models kept for the warm start.

A Frank-Wolfe loop works on **one** polytope; four is plenty, and bounds the memory
footprint of this cache.
"""

_CACHE: OrderedDict[int, tuple[Polytope, Any, list[Any], list[Any]]] = OrderedDict()
"""GLOP models already built, keyed by the polytope's ``id``.

The polytope is kept **by strong reference** in the value: as long as it is there, its
``id`` cannot be reassigned to another object, and the key stays correct.

This cache changes no result, only the time: same inputs, same solution. The purity
that `ARCHITECTURE.md` §3 demands of ``lmo`` — determinism, nothing learned — is
preserved, and a property test checks it on every run.
"""


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

    x: VecteurF
    value: float
    status: Literal["optimal", "infaisable", "non_borne", "limite"]
    duals: VecteurF | None = None
    farkas_certificate: VecteurF | None = None
    farkas_certificate_eq: VecteurF | None = None
    """Farkas multipliers of the rows of ``A_eq`` (free sign, same convention as
    ``farkas_certificate``), set only when ``status == "infaisable"``."""
    iterations: int = 0
    time_ms: float = 0.0


def clear_cache() -> None:
    """Forget the models kept for the warm start.

    Useful for performance measurements, which must be able to guarantee a cold start.
    """
    _CACHE.clear()


def _statut(code: int) -> Literal["optimal", "infaisable", "non_borne", "limite"]:
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


def _borne_glop(solveur: object, value: float, *, superieure: bool) -> float:
    """Translate a Python bound (possibly infinite) into a GLOP bound."""
    if math.isfinite(value):
        return float(value)
    infini = float(solveur.infinity())  # type: ignore[attr-defined]
    return infini if superieure else -infini


def _construire_modele(poly: Polytope, cuts: list[Cut] | None) -> tuple[Any, list[Any], list[Any]]:
    """Translate a polytope into a GLOP model.

    Returns
    -------
    tuple
        The solver, its variables in column order, and its constraints in the row
        order of ``A`` — this order is what makes the duals pairable with ``origins``.
    """
    solveur = pywraplp.Solver.CreateSolver("GLOP")
    if solveur is None:  # pragma: no cover - depends on the OR-Tools installation
        raise InvariantViolation(("GLOP backend unavailable",))

    noms = sorted(poly.index, key=lambda nom: poly.index[nom])
    variables = [
        solveur.NumVar(
            _borne_glop(solveur, poly.bounds[i][0], superieure=False),
            _borne_glop(solveur, poly.bounds[i][1], superieure=True),
            nom,
        )
        for i, nom in enumerate(noms)
    ]

    contraintes: list[Any] = []
    matrice = poly.A.tocsr()
    for ligne in range(matrice.shape[0]):
        debut, fin = matrice.indptr[ligne], matrice.indptr[ligne + 1]
        contrainte = solveur.RowConstraint(-solveur.infinity(), float(poly.b[ligne]))
        for colonne, value in zip(matrice.indices[debut:fin], matrice.data[debut:fin], strict=True):
            contrainte.SetCoefficient(variables[colonne], float(value))
        contraintes.append(contrainte)

    egalites = poly.A_eq.tocsr()
    for ligne in range(egalites.shape[0]):
        debut, fin = egalites.indptr[ligne], egalites.indptr[ligne + 1]
        borne = float(poly.b_eq[ligne])
        contrainte = solveur.RowConstraint(borne, borne)
        for colonne, value in zip(
            egalites.indices[debut:fin], egalites.data[debut:fin], strict=True
        ):
            contrainte.SetCoefficient(variables[colonne], float(value))

    for coupe in cuts or ():
        # A cut is written ``Σ coeffs·v ≥ lower_bound``; GLOP takes the bound as is.
        contrainte = solveur.RowConstraint(coupe.lower_bound, solveur.infinity())
        for nom, coefficient in coupe.coefficients:
            contrainte.SetCoefficient(variables[poly.index[nom]], float(coefficient))

    return solveur, variables, contraintes


def _is_feasible(poly: Polytope, cuts: list[Cut] | None) -> bool:
    """Say whether the constraints admit at least one point, objective set aside.

    **The discriminant between "infeasible" and "unbounded"**, which GLOP returns under
    the same code. An LP with a zero objective cannot be unbounded: if it finds a point,
    the failure of the original problem came from its objective, not its programme.

    The model is identical to that of the real problem — cuts, equalities and bounds
    included — so that the verdict bears on the same system.
    """
    solveur, _, _ = _construire_modele(poly, cuts)
    solveur.Objective().SetMinimization()
    return _statut(solveur.Solve()) == "optimal"


def _certificat_farkas(poly: Polytope, cuts: list[Cut] | None) -> tuple[VecteurF, VecteurF]:
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
    solveur, variables, contraintes = _construire_modele(poly, cuts)
    objective = solveur.Objective()

    slacks = [
        solveur.NumVar(0.0, solveur.infinity(), f"ecart_{i}") for i in range(len(contraintes))
    ]
    for contrainte, ecart in zip(contraintes, slacks, strict=True):
        contrainte.SetCoefficient(ecart, -1.0)
        objective.SetCoefficient(ecart, 1.0)

    # Equality rows were created right after the rows of A (see _construire_modele).
    n_rows = len(contraintes)
    equalities = solveur.constraints()[n_rows : n_rows + poly.A_eq.shape[0]]
    for rank, equality in enumerate(equalities):
        above = solveur.NumVar(0.0, solveur.infinity(), f"eq_plus_{rank}")
        below = solveur.NumVar(0.0, solveur.infinity(), f"eq_minus_{rank}")
        equality.SetCoefficient(above, 1.0)
        equality.SetCoefficient(below, -1.0)
        objective.SetCoefficient(above, 1.0)
        objective.SetCoefficient(below, 1.0)

    # Cuts are relaxed the other way round: they are written ``≥``.
    for rang, coupe in enumerate(cuts or ()):
        relache = solveur.NumVar(0.0, solveur.infinity(), f"ecart_coupe_{rang}")
        contrainte = solveur.RowConstraint(coupe.lower_bound, solveur.infinity())
        for nom, coefficient in coupe.coefficients:
            contrainte.SetCoefficient(variables[poly.index[nom]], float(coefficient))
        contrainte.SetCoefficient(relache, 1.0)
        objective.SetCoefficient(relache, 1.0)

    objective.SetMinimization()
    if _statut(solveur.Solve()) != "optimal":
        return np.zeros(len(contraintes), dtype=float), np.zeros(len(equalities), dtype=float)
    return (
        -np.array([c.dual_value() for c in contraintes], dtype=float),
        -np.array([c.dual_value() for c in equalities], dtype=float),
    )


def solve(
    poly: Polytope,
    c: VecteurF,
    *,
    start: VecteurF | None = None,
    cuts: list[Cut] | None = None,
    duals: bool = False,
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
    duaux : bool, optional
        Extract the dual prices, in the row order of ``poly.A`` — this order is what
        makes them pairable with ``poly.origins``. **The rows of ``poly.A_eq`` and the
        cuts do not appear in it**: they have no label in ``origins``. A consequence to
        know: after :func:`archlux.geom.polytope.figer_contacts`, the saturated
        constraints — the most informative ones — are moved into ``A_eq`` and their
        price therefore disappears from the diagnosis.

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
    **Do not simplify this signature.** ``start`` and ``duaux`` look useless at
    milestone 2; they are indispensable at milestones 3 and 5. Adding them afterwards
    forces the interface to be restructured to carry the state (`MILESTONE-2.md` §4).
    """
    debut = time.perf_counter()
    n_var = len(poly.index)
    if c.shape != (n_var,):
        raise InvariantViolation((f"objective has shape {c.shape}, expected ({n_var},)",))
    if start is not None and start.shape != (n_var,):
        raise InvariantViolation((f"start has shape {start.shape}, expected ({n_var},)",))

    cle = id(poly)
    en_cache = _CACHE.get(cle)
    reutilisable = start is not None and en_cache is not None and not cuts
    if reutilisable and en_cache is not None:
        _, solveur, variables, contraintes = en_cache
        _CACHE.move_to_end(cle)
    else:
        solveur, variables, contraintes = _construire_modele(poly, cuts)
        if not cuts:
            _CACHE[cle] = (poly, solveur, variables, contraintes)
            _CACHE.move_to_end(cle)
            while len(_CACHE) > _TAILLE_CACHE:
                _CACHE.popitem(last=False)

    objective = solveur.Objective()
    for variable, coefficient in zip(variables, c, strict=True):
        objective.SetCoefficient(variable, float(coefficient))
    objective.SetMinimization()

    code = solveur.Solve()
    statut = _statut(code)
    temps_ms = (time.perf_counter() - debut) * 1000.0

    if statut == "infaisable":
        # GLOP conflates "infeasible" and "unbounded". The auxiliary problem settles it:
        # a zero optimum means the constraints are satisfiable, hence the failure came
        # from the objective. Without this distinction, ``api.legalize`` would raise
        # "the programme does not fit in the envelope" on an open domain.
        if _is_feasible(poly, cuts):
            return LPSolution(
                x=np.zeros(n_var),
                value=float("-inf"),
                status="non_borne",
                iterations=solveur.iterations(),
                time_ms=(time.perf_counter() - debut) * 1000.0,
            )
        farkas, farkas_eq = _certificat_farkas(poly, cuts)
        return LPSolution(
            x=np.zeros(n_var),
            value=float("inf"),
            status=statut,
            farkas_certificate=farkas,
            farkas_certificate_eq=farkas_eq,
            iterations=solveur.iterations(),
            time_ms=(time.perf_counter() - debut) * 1000.0,
        )

    x = np.array([v.solution_value() for v in variables], dtype=float)
    return LPSolution(
        x=x,
        value=float(objective.Value()),
        status=statut,
        duals=(
            np.array([contrainte.dual_value() for contrainte in contraintes], dtype=float)
            if duals
            else None
        ),
        iterations=solveur.iterations(),
        time_ms=temps_ms,
    )


__getattr__ = lazy_aliases(
    __name__,
    {
        "SolutionLP": Alias(LPSolution, "archlux.lmo.solveur.LPSolution"),
        "resoudre": Alias(solve, "archlux.lmo.solveur.solve"),
        "vider_cache": Alias(clear_cache, "archlux.lmo.solveur.clear_cache"),
    },
)
