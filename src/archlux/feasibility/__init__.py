"""Faisabilité géométrique d'un programme (preuve exacte, sans lumière)."""

from __future__ import annotations

from dataclasses import dataclass, replace

from archlux.api import legalize
from archlux.erreurs import Infaisable
from archlux.types import Contexte, Plan, Structure

__all__ = ["CertificatFaisabilite", "Verdict", "is_feasible"]


@dataclass(frozen=True, slots=True)
class CertificatFaisabilite:
    """Preuve d'inexistence (Farkas) — nature **exacte**, jamais probabiliste."""

    origines: tuple[str, ...]
    certificat_farkas: object

    def expliquer(self) -> str:
        """Rendre le conflit en une phrase lisible."""
        if not self.origines:
            return "Infaisable : origines non renseignées."
        causes = ", ".join(self.origines)
        return f"Infaisable : contraintes en cause : [{causes}]."


@dataclass(frozen=True, slots=True)
class Verdict:
    """Réponse de :func:`is_feasible`."""

    faisable: bool
    certificat: CertificatFaisabilite | None = None

    def __bool__(self) -> bool:
        """``True`` ssi le programme admet au moins un plan valide."""
        return self.faisable


def is_feasible(programme: Plan, structure: Structure, ctx: Contexte) -> Verdict:
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
    OrdreIncoherent, SeparationManquante
        Entrée mal formée (propagées depuis la construction du graphe).

    Guarantees
    ----------
    - Géométrique : **exacte** (même oracle LP / Farkas que ``legalize``).
    - Performance : **aucune** — ce module ne parle pas de lumière.
    """
    contexte = replace(ctx, structure=structure)
    try:
        legalize(programme, contexte)
    except Infaisable as err:
        return Verdict(
            faisable=False,
            certificat=CertificatFaisabilite(
                origines=err.origines,
                certificat_farkas=err.certificat_farkas,
            ),
        )
    return Verdict(faisable=True, certificat=None)
