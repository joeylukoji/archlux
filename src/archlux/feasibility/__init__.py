"""Geometric feasibility of a program (exact proof, no daylight)."""

from __future__ import annotations

from dataclasses import dataclass, replace

from archlux._deprecation import Alias, lazy_aliases, renamed_parameters
from archlux.api import legalize
from archlux.errors import GapNeedsTiling, Infeasible
from archlux.types import Context, Plan, Structure

__all__ = ["FeasibilityCertificate", "Verdict", "is_feasible"]


@dataclass(frozen=True, slots=True)
class FeasibilityCertificate:
    """Proof of non-existence (Farkas), never probabilistic.

    Exact when ``verified`` is True: the certificate was checked in rational arithmetic
    (:func:`archlux.certify.farkas.verify_infeasibility`). It is about the relative order
    read from the proposed plan: another order might admit a valid plan.
    """

    origins: tuple[str, ...]
    farkas_certificate: object
    verified: bool | None = None
    scope: tuple[str, ...] = ()
    """Restrictions beyond the relative order the proof is about (``Infeasible.scope``)."""

    def explain(self) -> str:
        """Render the conflict as one readable sentence."""
        status = {
            True: " Certificate verified exactly.",
            False: " Certificate NOT verified: treat as a solver diagnosis, not a proof.",
            None: "",
        }[self.verified]
        within = f" with {', '.join(self.scope)}" if self.scope else ""
        if not self.origins:
            return f"Infeasible for this relative order{within}: no constraint identified.{status}"
        causes = ", ".join(self.origins)
        return (
            f"Infeasible for this relative order{within}: "
            f"conflicting constraints [{causes}].{status}"
        )


@dataclass(frozen=True, slots=True)
class Verdict:
    """Answer of :func:`is_feasible`."""

    feasible: bool
    certificate: FeasibilityCertificate | None = None

    def __bool__(self) -> bool:
        """``True`` if and only if the program admits at least one valid plan."""
        return self.feasible


def _legalize_any_dimensions(program: Plan, ctx: Context) -> None:
    """Legalize, closing a gap of the proposal with the tiling grid if needed.

    The program is not asked to keep its dimensions: a gap in the proposal is not a
    reason to refuse. The retry adds the tiling grid to the scope of any refusal.
    """
    try:
        legalize(program, ctx)
    except GapNeedsTiling:
        legalize(program, ctx, pavage=True)


@renamed_parameters({"programme": "program"})
def is_feasible(program: Plan, structure: Structure, ctx: Context) -> Verdict:
    """Decide whether a program (relative order fixed) admits a valid plan.

    Parameters
    ----------
    program : Plan
        Identities, types and proposed layout; the **relative order** is deduced. The
        dimensions are not an objective to preserve (unlike in ``legalize``).
    structure : Structure
        Replaces ``ctx.structure`` for this query.
    ctx : Context
        Outline and regulation. The orientation plays no part in the geometric decision.

    Returns
    -------
    Verdict
        ``feasible`` is exact; if false, ``certificate.explain()`` cites the Farkas origins.

    Raises
    ------
    InvalidInput
        Malformed argument (non-finite size, duplicate ids, ...), before any solving.
    InconsistentOrder, MissingSeparation
        Malformed input (propagated from the construction of the graph).
    UnsupportedInput
        An oblique load-bearing wall (propagated from :func:`archlux.legalize`).

    Guarantees
    ----------
    - Geometric: **exact** (same LP / Farkas oracle as ``legalize``).
    - Performance: **none**; this module says nothing about daylight.
    """
    context = replace(ctx, structure=structure)
    try:
        _legalize_any_dimensions(program, context)
    except Infeasible as err:
        return Verdict(
            feasible=False,
            certificate=FeasibilityCertificate(
                origins=err.origins,
                farkas_certificate=err.farkas_certificate,
                verified=err.verified,
                scope=err.scope,
            ),
        )
    return Verdict(feasible=True, certificate=None)


__getattr__ = lazy_aliases(
    __name__,
    {
        "CertificatFaisabilite": Alias(
            FeasibilityCertificate, "archlux.feasibility.FeasibilityCertificate"
        ),
    },
)
