"""Frank-Wolfe: maximize a surrogate over the polytope, never leaving the valid set.

The algorithm is chosen for a structural reason, not for convenience: its linear oracle
**is** the legalization solver. Each iteration solves exactly the LP of a classic
legalization, with another cost vector. There is therefore a single solver in the whole
project, and every iterate is a valid plan: no projection, no illegal intermediate step.

Dependencies: ``types``, ``geom``, ``lmo``, and the **protocol** ``light.protocole``.
Never a concrete surrogate implementation.

Formulas: ``docs/formules/frank-wolfe.md``.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

import numpy as np

from archlux.erreurs import Infaisable, InvariantViole
from archlux.geom.polytope import Polytope
from archlux.lmo.coupes import MAX_COUPES_PAR_PIECE, Coupe, coupe_surface, surfaces_violees
from archlux.lmo.solveur import resoudre
from archlux.solve.trace import Iteration, StopStatus, Trace

if TYPE_CHECKING:
    from collections.abc import Sequence

    from archlux.light.protocole import Baies, Substitut
    from archlux.types import Contexte, Orientation, Piece

__all__ = ["FrankWolfeResult", "frank_wolfe", "restrict_to_budget"]

_MIN_WEIGHT = 1e-12


@dataclass(frozen=True, slots=True)
class FrankWolfeResult:
    """Final iterate, optimality diagnostics and trace.

    Attributes
    ----------
    gap : float
        Frank-Wolfe gap ``<grad f(x), s - x>`` **at the returned x**, ``inf`` if no LP
        succeeded. It is a first-order **stationarity** measure. It bounds the distance
        to the optimum only for a concave surrogate, and none of the shipped surrogates
        is concave (AUDIT.md §5.1): never read it as an optimality certificate.
    status : StopStatus
        Why the run stopped (see :data:`archlux.solve.trace.StopStatus`).
    iterations : int
        Number of Frank-Wolfe iterations run (the initial entry ``k = -1`` of the trace
        is not counted).
    duals : numpy.ndarray or None
        Dual prices of the last LP, aligned with the rows of ``poly.A``. Equalities made
        by :func:`archlux.geom.polytope.figer_contacts` are not included, so the dual
        diagnosis of a performance run is often empty.
    """

    x: np.ndarray
    value: float
    gap: float
    status: StopStatus
    iterations: int
    trace: Trace
    duals: np.ndarray | None = None


def restrict_to_budget(
    poly: Polytope, centre: np.ndarray, radius: float, *, keep: np.ndarray | None = None
) -> Polytope:
    """Intersection of the polytope with the box ``‖x − centre‖_∞ ≤ radius``.

    ``centre`` must be the **proposed** plan, so that the budget is spent once over the
    whole legalization, not once per pass.

    ``keep`` is a point the box must contain even if it exceeds the radius by a solver
    tolerance: the result of a previous pass, which met the same budget only up to the
    LP tolerance (a saturated budget). Without it, that point could fall outside the box
    and make the domain empty for no real reason.

    Raises
    ------
    Infaisable
        The box does not intersect the bounds of some variable: the budget is too small
        for this plan. An input problem, not an internal error.
    """
    names = {column: name for name, column in poly.index.items()}
    bounds: list[tuple[float, float]] = []
    for i, (lo, hi) in enumerate(poly.bornes):
        low = max(lo, float(centre[i]) - radius)
        high = min(hi, float(centre[i]) + radius)
        if keep is not None:
            low, high = min(low, float(keep[i])), max(high, float(keep[i]))
        if low > high + 1e-12:
            label = names.get(i, f"column {i}")
            raise Infaisable(
                certificat_farkas=None,
                origines=(f"budget {radius} m cannot reach the bounds of {label}",),
            )
        bounds.append((low, high))
    return replace(poly, bornes=tuple(bounds))


def _vertex_index(vertices: list[np.ndarray], candidate: np.ndarray) -> int | None:
    """Index of an already stored vertex, up to tolerance."""
    for rank, vertex in enumerate(vertices):
        if np.allclose(vertex, candidate, atol=1e-9, rtol=0.0):
            return rank
    return None


def _add_cuts(
    cuts: list[Coupe],
    x: np.ndarray,
    domain: Polytope,
    ctx: Contexte | None,
    rooms: tuple[Piece, ...] | None,
) -> None:
    """Add AM-GM tangents when a room goes below ``a_min`` (legacy path)."""
    if ctx is None or not rooms:
        return
    if len(cuts) >= MAX_COUPES_PAR_PIECE * len(rooms):
        return
    for room_id in surfaces_violees(x, domain, ctx, pieces=rooms):
        width = float(x[domain.index[f"{room_id}.w"]])
        height = float(x[domain.index[f"{room_id}.h"]])
        a_min = ctx.referentiel.a_min(next(r.type for r in rooms if r.id == room_id))
        if width > 0.0 and height > 0.0 and a_min > 0.0:
            cuts.append(coupe_surface(width, height, a_min, piece=room_id))


def _normalize(weights: list[float]) -> None:
    """Scale the weights so that they sum to 1, in place.

    Numerically null masses are filtered **before** the call, by the caller, which alone
    can drop the matching vertex at the same time: pruning weights here would
    desynchronize the two lists.
    """
    total = sum(weights)
    if total <= 0.0:
        return
    for rank, mass in enumerate(weights):
        weights[rank] = mass / total


def frank_wolfe(
    poly: Polytope,
    surrogate: Substitut,
    orientation: Orientation,
    start: np.ndarray,
    *,
    max_iter: int = 50,
    tol: float = 1e-4,
    budget: float | None = None,
    away_steps: bool = True,
    cuts: Sequence[Coupe] | None = None,
    rooms: tuple[Piece, ...] | None = None,
    ctx: Contexte | None = None,
    glazing: Baies | None = None,
) -> FrankWolfeResult:
    """Maximize ``surrogate`` over the polytope, starting from ``start``.

    Parameters
    ----------
    poly : Polytope
        Admissible domain; every iterate stays in it.
    surrogate : Substitut
        Objective. The solver does not know whether it is analytic, learned or simulated.
    orientation : Orientation
        Azimuth of the plan.
    start : numpy.ndarray
        Initial iterate, typically the result of the classic legalization.
    max_iter : int, optional
        Maximum number of iterations.
    tol : float, optional
        Stop when the Frank-Wolfe gap falls below this threshold.
    budget : float or None, optional
        Maximum displacement allowed, in metres, relative to ``start``. When ``start``
        is not the proposed plan, restrict ``poly`` with :func:`restrict_to_budget`
        around the proposal instead, as :func:`archlux.api.legalize` does.
    away_steps : bool, optional
        Away steps: speed up convergence when the optimum lies on a face.
    cuts : sequence of Coupe or None, optional
        **Legacy, no caller since 0.10.** Outer tangent cuts; they do not guarantee
        minimum areas and disable the LP warm start. Pass a domain built with
        :func:`archlux.lmo.coupes.inner_area_constraints` instead. Removal planned in
        PLAN.md phase 4.
    rooms, ctx : optional
        **Legacy**, same status: with them, Kelley cuts are added when a minimum area
        is broken on the way.
    glazing : Baies or None, optional
        Windows, constant during optimization; passed to the surrogate as ``baies``.

    Returns
    -------
    FrankWolfeResult
        Final iterate and gap.

    Guarantees
    ----------
    - Geometric: **exact** at every iteration with respect to ``poly``: every iterate is
      a convex combination of ``start`` and vertices of the polytope, hence without
      overlap or gap.
    - Optimization: ``gap`` is a stationarity measure at the returned point; it bounds
      the distance to the optimum of the surrogate only if the surrogate is concave,
      which no shipped surrogate is. ``status`` says why the run stopped.
    - Daylight performance: **none here**. It is produced by :mod:`archlux.uq` and is
      only probabilistic.

    Warnings
    --------
    Minimum areas are guaranteed **only if** ``poly`` already contains an inner
    approximation of them (:func:`archlux.lmo.coupes.inner_area_constraints`), which is
    what :func:`archlux.api.legalize` passes: every point of such a domain keeps every
    minimum area, hence every iterate does. The legacy ``cuts``/``rooms``/``ctx`` path
    adds *outer* tangent cuts on the way; a cut added mid-run is violated by the current
    iterate, ``gap`` may turn negative and ``x`` may stay below ``a_min``. That path is
    kept for compatibility and is no longer used by ``legalize``.

    Complexity
    ----------
    At most ``max_iter + 1`` LP calls (one per iteration, plus one at the returned point
    for its gap and duals), **all warm** via ``depart=``. Omitting it costs a factor 3
    to 5. Budget: < 500 ms for 15 rooms and 50 iterations.
    """
    domain = poly if budget is None else restrict_to_budget(poly, start, budget)
    x = np.asarray(start, dtype=float).copy()
    if x.shape != (len(domain.index),):
        raise InvariantViole((f"start of shape {x.shape}, expected ({len(domain.index)},)",))

    vertices = [x.copy()]
    weights = [1.0]
    active_cuts: list[Coupe] = list(cuts) if cuts else []
    n_cuts = len(active_cuts)
    gap = float("inf")  # no LP has succeeded yet: nothing is known
    status: StopStatus = "max_iter"
    value = float(surrogate.evaluer(x, orientation, baies=glazing))
    history: list[Iteration] = [
        Iteration(
            k=-1,
            value=value,
            gap=float("inf"),
            step=0.0,
            away_step=False,
            lp_ms=0.0,
            n_cuts=n_cuts,
            x=x.copy(),
        )
    ]
    last_oracle = None

    for k in range(max_iter):
        gradient = np.asarray(surrogate.gradient(x, orientation, baies=glazing), dtype=float)
        oracle = resoudre(
            domain,
            -gradient,
            depart=x,
            coupes=active_cuts or None,
            duaux=False,  # duals are computed once, at the returned point
        )
        last_oracle = oracle
        if oracle.statut != "optimal":
            status = "lp_not_optimal"
            if k > 0:
                gap = float("inf")  # x moved since the last successful LP: unknown
            break
        fw_vertex = oracle.x
        gap = float(gradient @ (fw_vertex - x))
        if gap <= tol:
            status = "converged"
            history.append(
                Iteration(
                    k=k,
                    value=value,
                    gap=gap,
                    step=0.0,
                    away_step=False,
                    lp_ms=oracle.temps_ms,
                    n_cuts=n_cuts,
                    x=x.copy(),
                )
            )
            break

        away = False
        direction = fw_vertex - x
        gamma_max = 1.0
        away_index: int | None = None
        if away_steps and len(vertices) > 1:
            scores = [float(gradient @ vertex) for vertex in vertices]
            away_index = int(np.argmin(scores))
            away_vertex = vertices[away_index]
            away_direction = x - away_vertex
            if (
                float(gradient @ away_direction) > float(gradient @ direction)
                and weights[away_index] < 1.0 - _MIN_WEIGHT
            ):
                direction = away_direction
                gamma_max = weights[away_index] / (1.0 - weights[away_index])
                away = True

        gamma = min(2.0 / (k + 2), gamma_max)
        for _ in range(12):
            candidate = x + gamma * direction
            new_value = float(surrogate.evaluer(candidate, orientation, baies=glazing))
            if new_value >= value - 1e-12:
                value = new_value
                x = candidate
                break
            gamma *= 0.5
        else:
            status = "line_search_failed"
            history.append(
                Iteration(
                    k=k,
                    value=value,
                    gap=gap,
                    step=0.0,
                    away_step=away,
                    lp_ms=oracle.temps_ms,
                    n_cuts=n_cuts,
                    x=x.copy(),
                )
            )
            break

        if away and away_index is not None:
            for rank in range(len(weights)):
                weights[rank] *= 1.0 + gamma
            weights[away_index] -= gamma
        else:
            for rank in range(len(weights)):
                weights[rank] *= 1.0 - gamma
            existing = _vertex_index(vertices, fw_vertex)
            if existing is None:
                vertices.append(fw_vertex.copy())
                weights.append(gamma)
            else:
                weights[existing] += gamma

        kept_vertices: list[np.ndarray] = []
        kept_weights: list[float] = []
        for vertex, mass in zip(vertices, weights, strict=True):
            if mass > _MIN_WEIGHT:
                kept_vertices.append(vertex)
                kept_weights.append(mass)
        vertices, weights = kept_vertices, kept_weights
        _normalize(weights)
        _add_cuts(active_cuts, x, domain, ctx, rooms)
        n_cuts = len(active_cuts)

        history.append(
            Iteration(
                k=k,
                value=value,
                gap=gap,
                step=gamma,
                away_step=away,
                lp_ms=oracle.temps_ms,
                n_cuts=n_cuts,
                x=x.copy(),
            )
        )

    duals = None
    if status == "max_iter" and last_oracle is not None:
        # The last step moved x after its LP: the gap and duals of that LP describe the
        # previous point. Solve once more at the returned x.
        final_gradient = np.asarray(surrogate.gradient(x, orientation, baies=glazing), dtype=float)
        final = resoudre(domain, -final_gradient, depart=x, coupes=active_cuts or None, duaux=True)
        if final.statut == "optimal":
            gap = float(final_gradient @ (final.x - x))
            duals = final.duaux
        else:
            gap = float("inf")  # the previous gap describes the previous point
    elif last_oracle is not None and last_oracle.statut == "optimal":
        extra = resoudre(
            domain,
            -np.asarray(surrogate.gradient(x, orientation, baies=glazing), dtype=float),
            depart=x,
            coupes=active_cuts or None,
            duaux=True,
        )
        if extra.statut == "optimal":
            duals = extra.duaux

    return FrankWolfeResult(
        x=x,
        value=value,
        gap=gap,
        status=status,
        iterations=len(history) - 1,
        trace=Trace(iterations=tuple(history), status=status, final_gap=gap),
        duals=duals,
    )
