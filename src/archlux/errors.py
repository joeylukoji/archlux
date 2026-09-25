"""Typed exceptions of the project.

``ARCHITECTURE.md`` requires them (§7, "typed exceptions, never ``Exception``") without
assigning them a file. They live here rather than in :mod:`archlux.types` for a dependency
reason: ``Infeasible`` carries a Farkas certificate, an object of the ``geom``/``lmo``
layers, and referencing those from ``types`` would create a cycle. The fields are typed
``object`` instead, so this module depends on **nothing**: like ``types``, it sits upstream
of every layer.
"""

from __future__ import annotations

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
    """Root of every exception of the project.

    No code of the project raises or catches a bare ``Exception``.
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
    """The relative order contains a cycle: ``A`` left of ``B`` left of ``A``.

    Parameters
    ----------
    cycle : tuple of str
        The room identifiers forming the cycle, in order.
    axis : {"horizontal", "vertical"}
        The axis on which the cycle was detected.
    """

    def __init__(self, cycle: tuple[str, ...], axis: str) -> None:
        """Retain the cycle and its axis, and compose the message."""
        self.cycle = cycle
        self.axis = axis
        super().__init__(f"{axis} cycle: {' -> '.join(cycle)}")


class MissingSeparation(ArchluxError):
    """A pair of rooms is separated on no axis: they may overlap.

    Parameters
    ----------
    pair : tuple of str
        The two room identifiers concerned.
    """

    def __init__(self, pair: tuple[str, str]) -> None:
        """Retain the pair of rooms that is not separated."""
        self.pair = pair
        super().__init__(f"no separation between {pair[0]} and {pair[1]}")


class Infeasible(ArchluxError):
    """The program does not fit the envelope: no valid plan exists.

    The exception **carries the proof of infeasibility**, never a bare message: a Farkas
    certificate identifies the subset of constraints in conflict.

    Parameters
    ----------
    farkas_certificate : object
        Dual vector of the auxiliary problem (a ``numpy.ndarray``), not typed here so that
        this module stays free of dependencies.
    origins : tuple of str
        Readable labels of the constraints in conflict, from ``Polytope.origines`` and,
        since batch 1.5c, ``Polytope.origines_eq`` (tiling, fusions, contacts).
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
        farkas_certificate: object,
        origins: tuple[str, ...] = (),
        *,
        verified: bool | None = None,
        scope: tuple[str, ...] = (),
        relaxable: tuple[str, ...] = (),
    ) -> None:
        """Retain the Farkas certificate and the origins in conflict."""
        self.farkas_certificate = farkas_certificate
        self.origins = origins
        self.verified = verified
        self.scope = scope
        self.relaxable = relaxable
        detail = " ; ".join(origins) if origins else "no constraint identified"
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
    """The solver returned an output that the exact verification rejects.

    Most often an internal bug. Never caught silently: `ARCHITECTURE.md` forbids trusting
    the solver.

    Parameters
    ----------
    violations : tuple of str
        Readable messages produced by :func:`archlux.certify.proof.verify_exactly`.
    """

    def __init__(self, violations: tuple[str, ...]) -> None:
        """Retain the violations found by the exact verification."""
        self.violations = violations
        super().__init__("invariant violated: " + " ; ".join(violations))


class CalibrationLocked(ArchluxError):
    """Access to the calibration set without a token issued after the model was frozen.

    Guard against the one silent error able to invalidate a publication: a calibration set
    seen during training makes the conformal coverage false, and no test would notice.
    """

    def __init__(self, detail: str = "token missing, invalid, or issued before the freeze") -> None:
        """Compose the message refusing access to the calibration set."""
        super().__init__(detail)


class ModelModified(CalibrationLocked):
    """The weights changed after the model was frozen: the token no longer unlocks.

    Subclass of :class:`CalibrationLocked`: the same barrier, with the precise cause (a
    diverging fingerprint rather than an invalid signature).
    """

    def __init__(self, detail: str = "model weights changed after the freeze") -> None:
        """Compose the message of a diverging weights fingerprint."""
        super().__init__(detail)


class InvalidSurrogate(ArchluxError):
    """The gradient of a surrogate does not match its finite differences.

    Raised by :func:`archlux.light.validation.valider_gradient`. A surrogate with a wrong
    gradient makes the optimizer converge to noise, with no visible error.
    """

    def __init__(
        self,
        detail: str = "surrogate gradient unusable",
        *,
        report: object = None,
    ) -> None:
        """Compose the message of an unusable surrogate gradient.

        ``report`` is the full :class:`~archlux.light.validation.RapportGradient` of a
        failed check, so that a caller can record the failing value without parsing
        the message (PLAN.md phase 2, J4). Typed ``object``: this module is imported by
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
