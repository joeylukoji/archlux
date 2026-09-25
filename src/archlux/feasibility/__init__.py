"""Faisabilité géométrique d'un programme (preuve exacte, sans lumière)."""

from __future__ import annotations

from dataclasses import dataclass, replace

from archlux.api import legalize
from archlux.errors import GapNeedsTiling, Infeasible
from archlux.types import Context, Plan, Structure

__all__ = ["CertificatFaisabilite", "Verdict", "is_feasible"]


@dataclass(frozen=True, slots=True)
class CertificatFaisabilite:
    """Preuve d'inexistence (Farkas), never probabilistic.

    Exact when ``verified`` is True: the certificate was checked in rational arithmetic
    (:func:`archlux.certify.farkas.verify_infeasibility`). It is about the relative order
    read from the proposed plan: another order might admit a valid plan.
    """

    origines: tuple[str, ...]
    certificat_farkas: object
    verified: bool | None = None
    scope: tuple[str, ...] = ()
    """Restrictions beyond the relative order the proof is about (``Infeasible.scope``)."""

    def expliquer(self) -> str:
        """Rendre le conflit en une phrase lisible."""
        status = {
            True: " Certificate verified exactly.",
            False: " Certificate NOT verified: treat as a solver diagnosis, not a proof.",
            None: "",
        }[self.verified]
        within = f" with {', '.join(self.scope)}" if self.scope else ""
        if not self.origines:
            return f"Infeasible for this relative order{within}: no constraint identified.{status}"
        causes = ", ".join(self.origines)
        return (
            f"Infeasible for this relative order{within}: "
            f"conflicting constraints [{causes}].{status}"
        )


@dataclass(frozen=True, slots=True)
class Verdict:
    """Réponse de :func:`is_feasible`."""

    faisable: bool
    certificat: CertificatFaisabilite | None = None

    def __bool__(self) -> bool:
        """``True`` ssi le programme admet au moins un plan valide."""
        return self.faisable


def _legalize_any_dimensions(programme: Plan, ctx: Context) -> None:
    """Legalize, closing a gap of the proposal with the tiling grid if needed.

    The program is not asked to keep its dimensions: a gap in the proposal is not a
    reason to refuse. The retry adds the tiling grid to the scope of any refusal.
    """
    try:
        legalize(programme, ctx)
    except GapNeedsTiling:
        legalize(programme, ctx, pavage=True)


def is_feasible(programme: Plan, structure: Structure, ctx: Context) -> Verdict:
    """Décider si un programme (ordre relatif fixé) admet un plan valide.

    Parameters
    ----------
    programme : Plan
        Identités, types et disposition proposée ; l'**ordre relatif** est déduit.
        Les cotes ne sont pas un objectif à préserver (contrairement à ``legalize``).
    structure : Structure
        Remplace ``ctx.structure`` pour cette requête.
    ctx : Contexte
        Contour et référentiel. L'orientation n'entre pas dans la décision géométrique.

    Returns
    -------
    Verdict
        ``faisable`` exact ; si faux, ``certificat.expliquer()`` cite les origines Farkas.

    Raises
    ------
    InvalidInput
        Malformed argument (non-finite size, duplicate ids, ...), before any solving.
    InconsistentOrder, MissingSeparation
        Entrée mal formée (propagées depuis la construction du graphe).
    UnsupportedInput
        An oblique load-bearing wall (propagated from :func:`archlux.legalize`).

    Guarantees
    ----------
    - Géométrique : **exacte** (même oracle LP / Farkas que ``legalize``).
    - Performance : **aucune** — ce module ne parle pas de lumière.
    """
    contexte = replace(ctx, structure=structure)
    try:
        _legalize_any_dimensions(programme, contexte)
    except Infeasible as err:
        return Verdict(
            faisable=False,
            certificat=CertificatFaisabilite(
                origines=err.origins,
                certificat_farkas=err.farkas_certificate,
                verified=err.verified,
                scope=err.scope,
            ),
        )
    return Verdict(faisable=True, certificat=None)
