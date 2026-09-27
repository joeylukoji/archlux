r"""Public interface: one function, one parameter that changes everything.

``objective=None`` gives classic legalization; a ``Surrogate`` gives performance
legalization. **One function, one parameter.**

Classic pipeline
----------------
1. Deduce the order (the generator decides the order).
2. Build the polytope (linear separations).
3. Extend with the L1 epigraph (Bertsimas-Tsitsiklis §1.3).
4. Minimize :math:`\\sum e_i` under area cuts (Kelley / AM-GM).
5. Devectorize, re-verify **independently**, attach the certificate.

Full chain, assumptions and contra-indications: ``docs/formules/pipeline.md``.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import TYPE_CHECKING

import numpy as np

from archlux._deprecation import renamed_parameters
from archlux.arrays import VecteurF
from archlux.certify.borne import bound_selected_plan, check_calibration
from archlux.certify.dual import translate_duals
from archlux.certify.farkas import verify_infeasibility
from archlux.certify.proof import verify_exactly
from archlux.errors import GapNeedsTiling, Infeasible, InvalidInput, InvariantViolation
from archlux.geom.graphe import RelativeOrder, deduce_order
from archlux.geom.pavage import Grid, deduce_grid, extend_tiling, snap_to_grid
from archlux.geom.polytope import (
    Polytope,
    build_polytope,
    devectorize,
    extend_l1_slack,
    freeze_contacts,
    vectorize,
)
from archlux.geom.rectilineaire import (
    RectilinearRoom,
    extend_merges,
    minimum_area_shares,
)
from archlux.light.protocole import Glazing, Surrogate, point_prediction
from archlux.lmo.cuts import (
    inner_area_constraints,
    solve_with_areas,
)
from archlux.lmo.solveur import LPSolution
from archlux.solve.frank_wolfe import frank_wolfe, restrict_to_budget
from archlux.tolerances import SNAP_M
from archlux.types import Certificate, Context, GeometricProof, Plan
from archlux.validation import resolve_outline, validate_inputs

if TYPE_CHECKING:
    from collections.abc import Mapping

    from archlux.certify.borne import Calibration

__all__ = ["gradient_distance", "legalize"]

_DUAL_THRESHOLD = 1e-9


@renamed_parameters({"x_propose": "x_proposed"})
def gradient_distance(x_proposed: VecteurF) -> VecteurF:
    r"""Cost vector of the L1 epigraph: zeros on :math:`x`, ones on :math:`e`.

    .. math::

        c = (0,\\ldots,0, 1,\\ldots,1) \\in \\mathbb{R}^{2n},
        \\qquad \\min\\, c^\\top (x,e) = \\min \\sum_i e_i.

    ``x_proposed`` only fixes the dimension :math:`n`; the :math:`\\hat{x}_i` enter the
    constraints of :func:`extend_l1_slack`, not ``c``.

    Parameters
    ----------
    x_proposed : numpy.ndarray
        Proposed plan, vectorized, dimension n.

    Returns
    -------
    numpy.ndarray
        Vector ``c`` of dimension ``2n``.

    Notes
    -----
    Epigraph: ``docs/formules/epigraphe-l1.md``.
    """
    n_var = int(x_proposed.shape[0])
    couts = np.zeros(2 * n_var, dtype=float)
    couts[n_var:] = 1.0
    return couts


def _active_origins(sol: LPSolution, poly: Polytope) -> tuple[str, ...]:
    """Labels of the rows, inequalities and equalities, with a non-zero Farkas weight.

    Without a certificate nothing is identified; listing every constraint, as before
    batch 1.5c, wrongly presented all of them as conflicting.
    """
    labels: list[str] = []
    if sol.farkas_certificate is not None:
        labels += [
            label
            for label, weight in zip(poly.origins, sol.farkas_certificate, strict=True)
            if abs(float(weight)) > _DUAL_THRESHOLD
        ]
    if sol.farkas_certificate_eq is not None:
        labels += [
            label
            for label, weight in zip(poly.eq_labels(), sol.farkas_certificate_eq, strict=True)
            if abs(float(weight)) > _DUAL_THRESHOLD
        ]
    return tuple(labels)


def _translated_duals(
    duals: VecteurF | None, poly: Polytope, *, objective: str = "displacement"
) -> tuple[tuple[str, float], ...]:
    """Pair the duals of the rows of ``A`` with ``poly.origins``.

    ``duals`` must come from an LP solved on **this** polytope: the pairing is
    positional, and ``origins`` only covers ``A``, never ``A_eq`` nor the cuts.
    ``objective`` names the unit of the prices: ``"displacement"`` (L1 pass) or the
    indicator of the surrogate (Frank-Wolfe pass, a prediction).
    """
    if duals is None:
        return ()
    return translate_duals(duals, poly, threshold=_DUAL_THRESHOLD, objective=objective)


def _only_a_gap(preuve: GeometricProof, budget: float | None) -> bool:
    """The proof fails on a gap and on nothing else, read from its flags, never its text."""
    return (
        preuve.gaps
        and not preuve.overlap
        and preuve.areas_ok
        and preuve.structure_kept
        and (budget is None or preuve.max_displacement <= budget + SNAP_M)
    )


GRID_LABEL = "tiling grid"
"""Scope entry of the tiling equalities (``tiling=True``)."""


def budget_label(budget: float) -> str:
    """Scope entry of the displacement budget."""
    return f"budget {budget:g} m"


def _scope(
    ordre: RelativeOrder,
    merges: tuple[RectilinearRoom, ...],
    grid: bool,
    budget: float | None,
) -> tuple[str, ...]:
    """Restrictions of the solver's domain beyond the relative order, as built."""
    scope: list[str] = []
    if ordre.wall_sides:
        scope.append("load-bearing sides")
    if merges:
        scope.append("fused-room seams and area shares")
    if ordre.shared_sides:
        scope.append("one shared side per fused room straddling a wall")
    if grid:
        scope.append(GRID_LABEL)
    if budget is not None:
        scope.append(budget_label(budget))
    return tuple(scope)


@dataclass(frozen=True, slots=True)
class _Problem:
    """What one call of :func:`legalize` solves: the plan, its context and its domain.

    Built once by :func:`_build_problem`; the methods answer the three questions every
    stage asks: what is the domain, what does the LP say, does the exact proof accept it.
    """

    plan: Plan
    ctx: Context
    merges: tuple[RectilinearRoom, ...]
    budget: float | None
    grid: Grid | None
    order: RelativeOrder
    base: Polytope
    x_ref: VecteurF
    minima: Mapping[str, float]  # read-only: the frozen problem shares it

    def domain(self, *, grid: bool = True, bounded: bool = True) -> tuple[Polytope, Polytope]:
        """The solver's domain, optionally without the tiling grid or the budget."""
        geometric = extend_tiling(self.base, self.grid) if grid and self.grid else self.base
        l1 = extend_l1_slack(geometric, self.x_ref)
        if bounded and self.budget is not None:
            n_geo = len(geometric.index)
            bounds = tuple(l1.bounds[:n_geo]) + tuple(
                (0.0, float(self.budget)) for _ in range(n_geo)
            )
            l1 = replace(l1, bounds=bounds)
        return geometric, l1

    def solve(self, l1: Polytope) -> LPSolution:
        """Minimize the L1 displacement over ``l1``, with the area cuts."""
        return solve_with_areas(
            l1,
            gradient_distance(self.x_ref),
            self.ctx,
            self.plan.rooms,
            duals=True,
            minima=self.minima,
        )

    def decode(self, x: VecteurF, index: dict[str, int], template: Plan | None = None) -> Plan:
        """The plan of a decision vector, on the context's outline."""
        decoded = devectorize(x, template or self.plan, index)
        return replace(decoded, outline=self.ctx.outline)

    def prove(self, candidate: Plan, *, bounded: bool = True) -> GeometricProof:
        """The exact proof of ``candidate`` against the proposed plan (and the budget)."""
        return verify_exactly(
            candidate,
            self.ctx,
            reference=self.plan,
            budget=self.budget if bounded else None,
            merges=self.merges,
        )


def _check_calibration(objective: Surrogate | None, calibration: Calibration | None) -> None:
    """Refuse a calibration that cannot bound the objective."""
    if calibration is None:
        return
    if objective is None:
        raise InvalidInput(
            "calibration",
            "requires an objective: classic mode claims no performance",
            "pass objective=<surrogate> or drop calibration",
        )
    check_calibration(calibration)
    if calibration.indicator != objective.indicator:
        raise InvalidInput(
            "calibration",
            f"calibration of {calibration.indicator!r} cannot bound {objective.indicator!r}",
            "calibrate the same indicator as the objective",
        )


def _build_problem(
    plan: Plan,
    ctx: Context,
    *,
    merges: tuple[RectilinearRoom, ...],
    budget: float | None,
    tiling: bool,
    repair_budget: int,
) -> _Problem:
    """Derive the relative order, the polytope and the reference vector of a plan."""
    # Makes a gap unrepresentable: see ``geom.pavage``. Raises if the grid of the
    # proposed plan cannot be recovered: an explicit failure, not a silent one.
    grid = deduce_grid(plan, ctx, repair_budget=repair_budget) if tiling else None
    # With a grid, the order is read from the plan snapped onto it: the order read from
    # the faulty plan could contradict the tiling equalities (a room moved onto its
    # neighbour overlaps it on both axes).
    order = deduce_order(
        plan if grid is None else snap_to_grid(plan, grid),
        structure=ctx.structure,
        # A fused room keeps one side of every wall: never a wall on its seam.
        groups=tuple(tuple(r.id for r in piece_l.rectangles) for piece_l in merges),
    )
    base = build_polytope(order, ctx)
    for piece_l in merges:
        base = extend_merges(base, piece_l, min_contact=ctx.regulation.min_width)
    return _Problem(
        plan=plan,
        ctx=ctx,
        merges=merges,
        budget=budget,
        grid=grid,
        order=order,
        base=base,
        x_ref=vectorize(plan, base.index),
        minima=MappingProxyType(minimum_area_shares(plan.rooms, merges, ctx.regulation)),
    )


def _admits(problem: _Problem, l1: Polytope, *, bounded: bool) -> bool:
    """The relaxed optimum is a plan the exact proof accepts, as returned.

    An ``"optimal"`` LP is not enough: without the grid the L1 optimum keeps a gap, and
    the area cuts are an outer approximation (final review of phase 1, M1).
    """
    relaxed = problem.solve(l1)
    if relaxed.status != "optimal":
        return False
    return problem.prove(problem.decode(relaxed.x, l1.index), bounded=bounded).valid


def _refusal(problem: _Problem, poly_l1: Polytope, sol: LPSolution) -> Infeasible:
    """The exception for an infeasible domain: the certificate, its scope and its causes."""
    check = (
        verify_infeasibility(poly_l1, sol.farkas_certificate, sol.farkas_certificate_eq)
        if sol.farkas_certificate is not None
        else None
    )
    # The certificate is about this domain, not about the order alone (final review of
    # phase 1, C1): name every restriction, and test the ones legalize added.
    scope = _scope(problem.order, problem.merges, problem.grid is not None, problem.budget)
    relaxable: list[str] = []
    if problem.grid is not None and _admits(problem, problem.domain(grid=False)[1], bounded=True):
        relaxable.append(GRID_LABEL)
    if problem.budget is not None and _admits(
        problem, problem.domain(bounded=False)[1], bounded=False
    ):
        relaxable.append(budget_label(problem.budget))
    return Infeasible(
        farkas_certificate=sol.farkas_certificate,
        origins=_active_origins(sol, poly_l1),
        verified=None if check is None else check.verified,
        scope=scope,
        relaxable=tuple(relaxable),
    )


def _classic_result(
    problem: _Problem, sol: LPSolution, poly_l1: Polytope
) -> tuple[Plan, GeometricProof]:
    """The classically legalized plan and its exact proof, or the typed refusal."""
    if sol.status != "optimal":
        raise InvariantViolation((f"statut LP inattendu : {sol.status}",))
    corrected = problem.decode(sol.x, poly_l1.index)
    proof = problem.prove(corrected)
    if not proof.valid:
        if problem.grid is None and _only_a_gap(proof, problem.budget):
            raise GapNeedsTiling(proof.violations)
        raise InvariantViolation(proof.violations)
    return corrected, proof


def _optimize_light(
    problem: _Problem,
    corrected: Plan,
    poly: Polytope,
    objective: Surrogate,
    calibration: Calibration | None,
    duals_l1: tuple[tuple[str, float], ...],
    trace: bool,
) -> Plan:
    """Frank-Wolfe from the classic plan, inside the polytope, then the exact proof."""
    ctx, merges, budget = problem.ctx, problem.merges, problem.budget
    x0 = vectorize(corrected, poly.index)
    # Inner approximation of the minimum areas, added *after* freezing contacts so that
    # a tight room is not frozen into an equality: every point of this domain, hence
    # every Frank-Wolfe iterate, keeps every minimum area (PLAN.md batch 1.2).
    poly_fw = inner_area_constraints(
        freeze_contacts(poly, x0),
        x0,
        ctx,
        corrected.rooms,
        minima=minimum_area_shares(corrected.rooms, merges, ctx.regulation),
    )
    if budget is not None:
        # Centred on the *proposed* plan, not on x0: the budget is spent once over the
        # whole legalization (AUDIT.md §5.8 measured up to twice the budget).
        poly_fw = restrict_to_budget(poly_fw, problem.x_ref, budget, keep=x0)
    # Glazing is not part of the decision vector: it is constant during the
    # optimization and passed through unchanged. Without it the surrogate only sees
    # rectangles and cannot predict real daylight (`docs/formules/jetons.md`).
    glazing = Glazing(walls=corrected.walls, openings=corrected.openings)
    result = frank_wolfe(poly_fw, objective, ctx.orientation, x0, glazing=glazing)
    performant = problem.decode(result.x, poly.index, template=corrected)
    proof = problem.prove(performant)
    if not proof.valid:
        raise InvariantViolation(proof.violations)
    # The last Frank-Wolfe LP is on poly_fw, not on poly_l1: its duals are the only ones
    # that pair with poly_fw.origins. Failing that, keep those of the L1 pass: they
    # describe another polytope, but are at least labelled correctly. Careful:
    # figer_contacts moved the saturated rows into A_eq, which is not dualized; this
    # diagnostic is therefore often empty (see lmo.solveur.resoudre).
    duals = duals_l1
    if result.duals is not None:
        duals = _translated_duals(result.duals, poly_fw, objective=objective.indicator)
    performance = None
    if calibration is not None:
        # Centred on the prediction mu, not on the pessimistic objective mu - q sigma.
        mu, sigma = point_prediction(objective, result.x, ctx.orientation, glazing=glazing)
        performance = bound_selected_plan(mu, calibration, uncertainty=sigma)
    return replace(
        performant,
        certificate=Certificate(geometry=proof, performance=performance, duals=duals),
        trace=result.trace if trace else None,
    )


_RENAMED_MEMBERS = {
    "evaluer": "evaluate",
    "incertitude": "uncertainty",
    "indicateur": "indicator",
    "evaluer_pieces": "evaluate_rooms",
}
"""Surrogate protocol members renamed in wave 5 without an alias (users implement them)."""


def _not_a_surrogate(objective: object) -> str:
    """Build the TypeError message for ``objective``.

    It names the members to rename when the object has the pre-rename French ones
    (review of the stack, #9).
    """
    message = "objective must implement archlux.light.protocole.Surrogate"
    legacy = [old for old in _RENAMED_MEMBERS if hasattr(objective, old)]
    if not legacy:
        return message
    renames = ", ".join(f"{old} -> {_RENAMED_MEMBERS[old]}" for old in legacy)
    return f"{message}; it has the pre-0.10 French members, rename them: {renames}"


@renamed_parameters({"fusions": "merges", "pavage": "tiling", "budget_reparation": "repair_budget"})
def legalize(
    plan: Plan,
    ctx: Context,
    *,
    objective: Surrogate | None = None,
    calibration: Calibration | None = None,
    budget: float | None = None,
    trace: bool = False,
    merges: tuple[RectilinearRoom, ...] = (),
    tiling: bool = False,
    repair_budget: int = 4,
) -> Plan:
    """Correct a plan towards the closest valid plan, or the best performing one.

    With ``objective=None``, minimizes the L1 displacement of the decision variables. A
    ``Surrogate`` chains Frank-Wolfe from that point, without leaving the polytope.

    Parameters
    ----------
    plan : Plan
        Proposed plan, possibly invalid. An L-shaped room must already be decomposed into
        sub-rectangles (:func:`~archlux.geom.rectilineaire.decompose`).
    ctx : Contexte
        Load-bearing structure, orientation, outline, regulation.
    objective : Substitut or None, optional
        Objective to maximize. ``None`` means geometric proximity.
    calibration : Calibration or None, optional
        Conformal calibration of ``objective`` (same indicator, scores normalized by
        ``σ``). With it, ``certificat.performance`` holds the conformal interval of the
        returned plan, labelled ``regime="selected"``: the optimizer chose the plan, so
        the nominal coverage is **not** guaranteed and the report says so. Requires
        ``objective``.
    budget : float or None, optional
        Maximum L-infinity displacement from the proposed plan, in metres, over the
        whole legalization (classic pass and Frank-Wolfe share it), checked by the proof.
        A budget too small for the plan raises ``Infeasible``.
    trace : bool, optional
        If true, attaches the Frank-Wolfe trace to ``result.trace`` (not serialized).
    merges : tuple of PieceRectilineaire, optional
        Fused rooms (L, T, U, Z) decomposed into sub-rectangles. Their shared edges
        become equalities of ``A_eq``; on the orthogonal axis, the order of the
        sub-rectangle ends is kept and every shared edge keeps at least
        ``regulation.min_width`` of length, so an L cannot turn into a Z or split
        (:func:`~archlux.geom.rectilineaire.overlap_constraints`).
    tiling : bool, optional
        Require that the union of the rooms **tiles the outline exactly**. Without it,
        the separations of the polytope being inequalities, a plan with a gap remains the
        closest point to itself: the L1 optimum leaves it as is and the exact
        verification rejects it. With it, a gap is no longer representable.

        Turn it on as soon as the input may carry a **gap**: this is the case of the
        outputs of generative models. Measured on 4,796 corruptions of 300 real MSD
        plans (`results/j7_reparation.md`): repair goes from 35.9 % to 93.0 %, and on
        gaps alone from 10.0 % to 97.6 % (column ``tiling=True``; the 93.9 % of the
        README is the "fallback" column: ``tiling=True``, otherwise ``legalize`` alone).
        Figures measured before batch 1.1.

        Requires the grid of the proposed plan to be recoverable
        (:func:`~archlux.geom.pavage.deduce_grid`); otherwise ``GridNotRecoverable``
        names the faulty cells. Default ``False``: the 1.x contract is unchanged.
        With a grid, the relative order and the load-bearing sides are read from
        the plan snapped onto it (:func:`~archlux.geom.pavage.snap_to_grid`), so
        that they never contradict the tiling equalities.
    repair_budget : int, optional
        Number of repair steps granted to the grid recovery, passed as is to
        :func:`~archlux.geom.pavage.deduce_grid`. No effect if ``tiling`` is false.

        The default ``4`` is tuned on **corrupted** plans, where the fault is a wrong
        dimension and is absorbed in one or two steps. The output of a generative model
        is another regime: its rooms share no line, the grid has dozens of cells and the
        budget becomes the limiting factor. ``0`` forbids any repair and accepts only an
        already consistent grid; a caller that must preserve the program room by room
        uses it to refuse rather than absorb a room into its neighbour.

    Returns
    -------
    Plan
        A valid plan carrying its ``certificate``.

    Raises
    ------
    InconsistentOrder, MissingSeparation
        Propagated from the construction of the graph.
    UnsupportedInput
        An oblique load-bearing wall: it cannot be kept by a linear side constraint.
        With ``tiling``, also an input the grid cannot describe (no room, empty or
        invalid outline, flat room, outline edges closer than the grouping tolerance).
    GridNotRecoverable
        With ``tiling``: the rooms do not fall into the cells of the recovered grid
        (an input limit, subclass of ``UnsupportedInput``).
    Infeasible
        The program does not fit the envelope for this relative order. The exception
        carries ``origins`` and, when the conflict is attributable to rows of ``A`` or
        ``A_eq``, ``certificat_farkas`` with its exact verification (``verified``).
        Raised before the LP if ``min_width`` already exceeds the envelope.
    GapNeedsTiling
        The plan leaves a gap and ``tiling`` is off: rerun with ``tiling=True``
        (an input limit, subclass of ``UnsupportedInput``).
    InvariantViolation
        Solver output rejected by the exact verification, or an unexpected LP status.
        The most frequent case is a minimum area still violated after the Kelley cuts
        are exhausted: the LP says "optimal", the exact verification does not.
        A calibration unable to give a finite bound (too small for its ``alpha``,
        non-finite scores) also raises it, before any solving.
    InvalidInput
        Malformed argument, refused before any solving: a non-finite or non-numeric
        value, a non-positive room size, duplicate room ids, no room, an outline with
        fewer than 3 points, a negative ``budget`` or ``repair_budget``, a
        ``calibration`` without ``objective`` or for another indicator. Its ``field``
        names the argument (a ``ValueError`` subclass).
    TypeError
        ``objective`` does not implement :class:`~archlux.light.protocole.Surrogate`.

    Guarantees
    ----------
    - Geometric: **exact**. ``result.certificate.geometry.valid`` is re-verified by
      :func:`archlux.certify.proof.verify_exactly` before return: the solver is never
      taken at its word.
    - Performance: **none** in classic mode (``objective is None``), nor with a
      surrogate but no ``calibration`` (``performance`` is then ``None``). With both, a
      conformal interval in the **selected** regime: nominal coverage stated, not
      guaranteed, because the optimizer chose the plan (AUDIT.md §5.3).

    Complexity
    ----------
    Classic mode: one LP per Kelley iteration, at most ``MAX_CUTS_PER_ROOM`` per
    room, < 20 ms for 15 rooms.
    Performance mode: up to 50 warm LPs, < 500 ms
    (`ARCHITECTURE.md` §9).
    A refusal costs up to three times the classic mode: the tiling grid and the budget
    are each dropped once, solved and proved, to fill ``Infeasible.relaxable``. No §9
    budget covers refusals.

    Notes
    -----
    Pipeline and sources: ``docs/formules/pipeline.md``.

    Examples
    --------
    >>> from archlux.types import (
    ...     Context, Orientation, Plan, Regulation, Room, Structure,
    ... )
    >>> plan = Plan(
    ...     rooms=(
    ...         Room(id="a", type="living_room", x=0.0, y=0.0, w=6.0, h=9.0),
    ...         Room(id="b", type="living_room", x=6.0, y=0.0, w=6.0, h=9.0),
    ...     ),
    ...     outline=((0.0, 0.0), (12.0, 0.0), (12.0, 9.0), (0.0, 9.0)),
    ... )
    >>> ctx = Context(
    ...     structure=Structure(load_bearing_walls=()),
    ...     orientation=Orientation(deg=0.0),
    ...     regulation=Regulation(min_areas=(), min_width=1.0),
    ... )
    >>> q = legalize(plan, ctx)
    >>> q.certificate.geometry.valid
    True
    """
    if objective is not None and not isinstance(objective, Surrogate):
        raise TypeError(_not_a_surrogate(objective))
    validate_inputs(plan, ctx, budget=budget, repair_budget=repair_budget)
    ctx = resolve_outline(plan, ctx)
    _check_calibration(objective, calibration)

    problem = _build_problem(
        plan,
        ctx,
        merges=merges,
        budget=budget,
        tiling=tiling,
        repair_budget=repair_budget,
    )
    poly, poly_l1 = problem.domain()
    sol = problem.solve(poly_l1)
    if sol.status == "infaisable":
        raise _refusal(problem, poly_l1, sol)
    corrected, proof = _classic_result(problem, sol, poly_l1)
    # sol was solved on poly_l1: the duals line up with poly_l1.A / origines, not poly.
    duals = _translated_duals(sol.duals, poly_l1)
    if objective is None:
        return replace(
            corrected,
            certificate=Certificate(geometry=proof, performance=None, duals=duals),
        )
    return _optimize_light(problem, corrected, poly, objective, calibration, duals, trace)
