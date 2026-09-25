"""Exceptions typees du projet.

Ce module est une **extension** de l'arborescence de ``ARCHITECTURE.md`` §11 : les
exceptions y sont exigees (§7, « exceptions typees -- jamais ``Exception`` ») sans qu'un
fichier leur soit assigne. Elles sont isolees ici plutot que dans :mod:`archlux.types`
pour une raison de dependance : ``Infeasible`` transporte un polytope et un certificat de
Farkas, objets de la couche ``geom``/``lmo``. Les referencer depuis ``types`` creerait un
cycle. Ici, les champs sont types en ``object`` et la dependance reste nulle.

``erreurs`` ne depend de **rien** : comme ``types``, il est en amont de toutes les couches.
"""

from __future__ import annotations

from archlux._deprecation import Alias, lazy_aliases

__all__ = [
    "ArchluxError",
    "CalibrationLocked",
    "GapNeedsTiling",
    "GridNotRecoverable",
    "InconsistentOrder",
    "Infeasible",
    "InvalidInput",
    "InvalidSurrogate",
    "InvariantViolation",
    "MissingSeparation",
    "ModelModified",
    "UnsupportedInput",
]


class ArchluxError(Exception):
    """Racine de toutes les exceptions du projet.

    Aucun code du projet ne leve ``Exception`` nue ni ne l'attrape.
    """


class InvalidInput(ArchluxError, ValueError):
    """An argument is malformed: wrong type, non-finite, out of range, or inconsistent.

    Raised at the door of the public functions, before any solving, so that a typo never
    surfaces as ``InvariantViolation`` (which means an internal bug). It also is a
    ``ValueError``: callers that caught ``ValueError`` keep working.

    Parameters
    ----------
    field : str
        Path of the offending argument, e.g. ``"pieces[kitchen].w"`` or ``"budget"``.
    problem : str
        What is wrong with it.
    hint : str, optional
        How to fix it, when there is a single obvious correction.
    """

    def __init__(self, field: str, problem: str, hint: str = "") -> None:
        """Retain the field and compose an actionable message."""
        self.field = field
        self.problem = problem
        self.hint = hint
        super().__init__(f"{field}: {problem}" + (f". {hint}" if hint else ""))


class InconsistentOrder(ArchluxError):
    """L'ordre relatif contient un cycle : ``A`` a gauche de ``B`` a gauche de ``A``.

    Parameters
    ----------
    cycle : tuple of str
        Les identifiants de pieces formant le cycle, dans l'ordre.
    axe : {"horizontal", "vertical"}
        L'axe sur lequel le cycle a ete detecte.
    """

    def __init__(self, cycle: tuple[str, ...], axe: str) -> None:
        """Retenir le cycle et son axe, et composer le message lisible."""
        self.cycle = cycle
        self.axe = axe
        super().__init__(f"cycle {axe} : {' -> '.join(cycle)}")


class MissingSeparation(ArchluxError):
    """Une paire de pieces n'est separee sur aucun axe : le chevauchement est possible.

    Parameters
    ----------
    paire : tuple of str
        Les deux identifiants de pieces concernes.
    """

    def __init__(self, paire: tuple[str, str]) -> None:
        """Retenir la paire de pieces non separee."""
        self.paire = paire
        super().__init__(f"aucune separation entre {paire[0]} et {paire[1]}")


class Infeasible(ArchluxError):
    """Le programme ne tient pas dans l'enveloppe : aucun plan valide n'existe.

    L'exception **porte la preuve de l'infaisabilite**, jamais un simple message : un
    certificat de Farkas identifie le sous-ensemble de contraintes en conflit.

    Parameters
    ----------
    certificat_farkas : object
        Vecteur dual du probleme auxiliaire (``numpy.ndarray``), non type ici pour
        maintenir ``erreurs`` sans dependance.
    origines : tuple of str
        Libelles lisibles des contraintes en conflit, issus de ``Polytope.origines``
        et, since batch 1.5c, of ``Polytope.origines_eq`` (tiling, fusions, contacts).
    verified : bool or None
        Whether the certificate was checked in exact arithmetic
        (:func:`archlux.certify.farkas.verify_infeasibility`); ``None`` if no check
        was run (for instance a conflict detected before any LP).

    scope : tuple of str
        Restrictions of the solver's domain beyond the relative order, each of which
        the certificate is about: ``"load-bearing sides"``, ``"tiling grid"``,
        ``"budget 0.3 m"``, ``"one shared side per fused room straddling a wall"``...
        The certificate proves the domain **with all of them** empty, nothing more.
    relaxable : tuple of str
        Entries of ``scope`` without which ``legalize`` finds a plan that passes the
        exact proof **for this same order**: they, not the order, are the cause. Only
        the tiling grid and the budget are tested, each dropped alone: an empty tuple
        does not rule out the other restrictions, nor the two dropped together.

    Notes
    -----
    The proof is about the polytope of **this relative order**, read from the proposed
    plan, **with the restrictions of** ``scope``: another order, or the same order
    without one of them, might admit a valid plan (AUDIT.md §5.2; final review of
    phase 1, C1).
    """

    def __init__(
        self,
        certificat_farkas: object,
        origines: tuple[str, ...] = (),
        *,
        verified: bool | None = None,
        scope: tuple[str, ...] = (),
        relaxable: tuple[str, ...] = (),
    ) -> None:
        """Retenir le certificat de Farkas et les origines en conflit."""
        self.certificat_farkas = certificat_farkas
        self.origines = origines
        self.verified = verified
        self.scope = scope
        self.relaxable = relaxable
        detail = " ; ".join(origines) if origines else "no constraint identified"
        status = {
            True: " [certificate verified exactly]",
            False: " [certificate NOT verified]",
            None: "",
        }[verified]
        within = f" with {', '.join(scope)}" if scope else ""
        cause = (
            f". Without {' or without '.join(relaxable)}, this order admits a plan"
            if relaxable
            else ""
        )
        super().__init__(f"infeasible for this relative order{within}: {detail}{status}{cause}")


class InvariantViolation(ArchluxError):
    """Le solveur a rendu une sortie que la verification exacte rejette.

    Most often an internal bug; also the documented refusal of a plan with a gap when
    ``legalize`` runs without ``pavage`` (the L1 optimum keeps the gap, the proof rejects
    it). Never caught silently: `ARCHITECTURE.md` forbids trusting the solver.

    Parameters
    ----------
    violations : tuple of str
        Messages lisibles produits par :func:`archlux.certify.proof.verify_exactly`.
    """

    def __init__(self, violations: tuple[str, ...]) -> None:
        """Retenir la liste des violations relevees par la verification exacte."""
        self.violations = violations
        super().__init__("invariant viole : " + " ; ".join(violations))


class CalibrationLocked(ArchluxError):
    """Acces au jeu de calibration sans jeton emis apres le gel du modele.

    Garde-fou de la seule erreur silencieuse capable d'invalider une publication : un jeu
    de calibration vu a l'entrainement rend la couverture conforme fausse sans qu'aucun
    test ne le signale.
    """

    def __init__(self, detail: str = "jeton absent, invalide, ou antérieur au gel") -> None:
        """Composer le message de refus d'acces au jeu de calibration."""
        super().__init__(detail)


class ModelModified(CalibrationLocked):
    """Les poids ont changé après ``geler_et_emettre`` : le jeton ne déverrouille plus.

    Sous-classe de :class:`CalibrationLocked` : c'est la même barrière, avec la
    cause précise (empreinte divergente plutôt que signature invalide).
    """

    def __init__(self, detail: str = "poids du modèle modifiés après le gel") -> None:
        """Composer le message d'empreinte de poids divergente."""
        super().__init__(detail)


class InvalidSurrogate(ArchluxError):
    """Le gradient d'un substitut ne correspond pas a ses differences finies.

    Levee par :func:`archlux.light.validation.valider_gradient`. Un substitut dont le
    gradient est faux fait converger l'optimiseur vers du bruit, sans erreur visible.
    """

    def __init__(
        self,
        detail: str = "gradient du substitut inexploitable",
        *,
        report: object = None,
    ) -> None:
        """Composer le message de gradient de substitut inexploitable.

        ``report`` is the full :class:`~archlux.light.validation.RapportGradient` of a
        failed check, so that a caller can record the failing value without parsing
        the message (PLAN.md phase 2, J4). Typed ``object``: ``erreurs`` is imported by
        every layer and may not import ``light``, not even for a type.
        """
        self.report = report
        super().__init__(detail)


class UnsupportedInput(ArchluxError):
    """The input is well formed but outside what the library can handle exactly.

    Raised instead of silently ignoring part of the input. Example: an oblique
    load-bearing wall, which cannot be written as a linear side constraint on
    axis-aligned rooms.
    """

    def __init__(self, detail: str) -> None:
        """Compose the message of an unsupported input."""
        super().__init__(detail)


class GapNeedsTiling(UnsupportedInput):
    """The proposed plan leaves a gap, and ``pavage`` was not asked.

    Without the tiling equalities the separations are inequalities, so a plan with a
    gap is its own closest valid point: the L1 optimum keeps the gap and the exact
    proof rejects it. An input limit with a known fix, not an internal error: until
    PLAN.md batch 3.4 it was raised as ``InvariantViolation``.

    Parameters
    ----------
    violations : tuple of str
        The ``gap:`` violations reported by the exact proof.
    """

    def __init__(self, violations: tuple[str, ...]) -> None:
        """Compose the message: what the proof found and how to fix it."""
        self.violations = violations
        super().__init__(
            "the plan leaves a gap that legalize cannot close on its own ("
            + " ; ".join(violations)
            + "). Rerun with pavage=True, which forces the rooms to tile the outline"
        )


class GridNotRecoverable(UnsupportedInput):
    """The tiling grid of the plan cannot be recovered within the repair budget.

    Raised by :func:`archlux.geom.pavage.deduire_trame` when the proposed plan is too
    far from a tiling: some grid cells stay covered twice (``excess``) or not at all
    (``missing``) after the bounded repair. An input limit, not an internal error:
    until batch 1.5c it was raised as ``InvariantViolation`` and callers sorted it by
    reading the message text.

    Parameters
    ----------
    excess, missing : int
        Grid cells covered twice, and cells left uncovered.
    """

    def __init__(self, excess: int, missing: int) -> None:
        """Compose the message from the cell counts."""
        self.excess = excess
        self.missing = missing
        super().__init__(
            f"tiling grid not recoverable: {excess} cells covered twice, {missing} "
            "uncovered; raise budget_reparation or fix the plan"
        )


DEPRECATED_NAMES = {
    "OrdreIncoherent": "InconsistentOrder",
    "SeparationManquante": "MissingSeparation",
    "Infaisable": "Infeasible",
    "InvariantViole": "InvariantViolation",
    "CalibrationVerrouillee": "CalibrationLocked",
    "ModeleModifie": "ModelModified",
    "SubstitutInvalide": "InvalidSurrogate",
}
"""Former French names of the exceptions, kept as deprecated aliases until 1.0.0 (ADR 0001,
PLAN.md 3.9 wave 1). Not part of ``__all__``."""

__getattr__ = lazy_aliases(
    __name__,
    {old: Alias(globals()[new], f"archlux.erreurs.{new}") for old, new in DEPRECATED_NAMES.items()},
)
