"""User-facing outcome of a repair: four answers, each with its failure class and advice.

AUDIT 2.3: a percentage of repaired plans hides why the others failed. Every attempt
recorded by :func:`archlux.certify.run.run_repair` is mapped to one of

- ``repaired``: certified valid, moved little;
- ``repaired_strong_deformation``: certified valid, but the largest move exceeds a share
  of the plan's side (default 25 %): valid, yet no longer the generated plan;
- ``not_repairable``: the input is well formed but no certified plan exists within the
  options, with a failure class (contradictory constraints proved by Farkas, tiling grid
  beyond the repair budget, gap that needs tiling, impossible topology);
- ``invalid_input``: the input itself is malformed;
- ``computation_failure``: a solver invariant broke (a bug, never expected).

Each answer carries a message that says what to do next.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from archlux.certify.run import RunReport
from archlux.errors import InvariantViolation

__all__ = ["FAILURE_CLASSES", "OUTCOMES", "PlanOutcome", "outcome"]

Outcome = Literal[
    "repaired",
    "repaired_strong_deformation",
    "not_repairable",
    "invalid_input",
    "computation_failure",
]
OUTCOMES: tuple[Outcome, ...] = (
    "repaired",
    "repaired_strong_deformation",
    "not_repairable",
    "invalid_input",
    "computation_failure",
)

FAILURE_CLASSES: dict[str, tuple[str, str]] = {
    "Infeasible": (
        "contradictory_constraints",
        "the constraints cannot hold together for this relative order; the Farkas "
        "certificate names the conflicting rows: relax one of them (a minimum area or "
        "width, the outline) or change the order of the rooms",
    ),
    "GridNotRecoverable": (
        "grid_budget_exceeded",
        "the tiling grid has more faulty cells than the repair budget: raise "
        "repair_budget, or regenerate the plan",
    ),
    "GapNeedsTiling": (
        "gap_needs_tiling",
        "the plan leaves a gap that only the tiling constraint can close: rerun with tiling=True",
    ),
    "InconsistentOrder": (
        "impossible_topology",
        "the rooms' relative order is contradictory (a cycle of left/right or "
        "above/below relations): fix the adjacency of the input",
    ),
    "MissingSeparation": (
        "impossible_topology",
        "two rooms have no separation the solver can impose: fix their positions in the input",
    ),
}
"""Exception name -> (failure class, advice) for ``not_repairable``."""


@dataclass(frozen=True, slots=True)
class PlanOutcome:
    """What a user is told about one repair attempt.

    Attributes
    ----------
    outcome : Outcome
        One of :data:`OUTCOMES`.
    failure_class : str or None
        For ``not_repairable`` and ``invalid_input``, the class of failure.
    relative_displacement : float or None
        Largest move divided by the plan's side, for a repaired plan.
    message : str
        One sentence saying what happened and what to do.
    """

    outcome: Outcome
    failure_class: str | None
    relative_displacement: float | None
    message: str


def _repaired(report: RunReport, side_m: float, strong: float) -> PlanOutcome:
    """Outcome of a certified repair, strong or not.

    Parameters
    ----------
    report : RunReport
        A ``repaired`` report.
    side_m : float
        Characteristic side of the plan, in metres.
    strong : float
        Threshold on the relative displacement.

    Returns
    -------
    PlanOutcome
        ``repaired`` or ``repaired_strong_deformation``.
    """
    moved = report.max_displacement_m or 0.0
    share = moved / side_m
    if share > strong:
        return PlanOutcome(
            "repaired_strong_deformation",
            None,
            share,
            f"certified valid, but a wall moved {moved:.2f} m ({100 * share:.0f} % of the "
            "side): check that the program and the adjacencies survived",
        )
    return PlanOutcome("repaired", None, share, f"certified valid; largest move {moved:.2f} m")


def outcome(report: RunReport, *, side_m: float, strong: float = 0.25) -> PlanOutcome:
    """Map a repair report to the answer a user gets.

    Parameters
    ----------
    report : RunReport
        Output of :func:`archlux.certify.run.run_repair`.
    side_m : float
        Characteristic side of the plan (e.g. the square root of the outline area), in
        metres, strictly positive.
    strong : float, optional
        Relative displacement above which a repair counts as a strong deformation
        (default 0.25).

    Returns
    -------
    PlanOutcome
        The outcome, its failure class and a message.

    Raises
    ------
    InvariantViolation
        If ``side_m`` or ``strong`` is not strictly positive.
    """
    if side_m <= 0.0 or strong <= 0.0:
        raise InvariantViolation((f"side_m and strong must be > 0, got {side_m}, {strong}",))
    if report.status == "repaired":
        return _repaired(report, side_m, strong)
    if report.status == "computation_failure":
        return PlanOutcome(
            "computation_failure",
            None,
            None,
            f"internal failure, please report it: {report.reason}",
        )
    known = FAILURE_CLASSES.get(report.error_type or "")
    if known is not None:
        return PlanOutcome("not_repairable", known[0], None, known[1])
    return PlanOutcome(
        "invalid_input",
        report.error_type or "invalid_input",
        None,
        f"the input was rejected before any solve: {report.reason}",
    )
