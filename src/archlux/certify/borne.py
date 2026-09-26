"""Assembly of the probabilistic guarantee in the certificate.

This module is the **only** way a daylight value enters an
:class:`archlux.types.Certificate`. It always enters with its coverage and the size of the
calibration set: no value without its uncertainty.
"""

from __future__ import annotations

from math import isfinite

from archlux._deprecation import Alias, lazy_aliases
from archlux.errors import InvariantViolation
from archlux.types import PerformanceBound, Regime
from archlux.uq.conforme import Calibration, borner, quantile_conforme
from archlux.uq.derive import DiagnosticDerive

__all__ = ["Calibration", "bound_selected_plan", "build_bound", "check_calibration"]


def build_bound(
    value: float,
    calibration: Calibration,
    drift: DiagnosticDerive,
    *,
    uncertainty: float,
    regime: Regime,
) -> PerformanceBound | None:
    """Build the bound, or ``None`` if drift invalidates exchangeability.

    Parameters
    ----------
    value : float
        Point estimate.
    calibration : Calibration
        Conformal score set.
    drift : DiagnosticDerive
        Verdict on exchangeability. A rejected exchangeability gives ``None``.
    uncertainty : float
        ``σ̂`` of the point, **strictly positive**, for normalized calibration scores;
        ``1.0`` for raw ones. Mandatory (PLAN.md batch 1.6).
    regime : {"exchangeable", "selected"}
        See :func:`archlux.uq.conforme.borner`.

    Returns
    -------
    PerformanceBound or None
        ``None`` means ``NOT EVALUABLE``: the system prefers to claim nothing rather than
        claim a coverage it cannot hold.

    Notes
    -----
    Two traps that the signature does not catch:

    - **``uncertainty`` must match the calibration.** The only calibration builder of the
      repository, :meth:`archlux.uq.conforme.CalibrateurConforme.ajuster`, divides the
      scores by ``σ``; ``Calibration`` does not record it, the caller does.
    - **A drift verdict that does not reject is not a proof of exchangeability.** It is
      treated here as a permission to publish; with few observations, the test of
      :func:`archlux.uq.derive.controler_derive` has almost no power. The certificate
      therefore says "drift not detected", never "no drift".
    """
    if not drift.echangeable:
        return None
    return borner(value, calibration, incertitude=uncertainty, regime=regime)


def check_calibration(calibration: object) -> None:
    """Refuse, before any solving, a calibration that could not give a finite bound.

    Raises
    ------
    InvariantViolation
        Not a :class:`Calibration`, non-finite scores, ``alpha`` outside ``]0, 1[`` or a
        set too small for ``alpha``: the conformal quantile is computed once here.
    """
    if not isinstance(calibration, Calibration):
        raise InvariantViolation(
            (f"calibration must be a Calibration, got {type(calibration).__name__}",)
        )
    quantile_conforme(calibration.scores, calibration.alpha)


def bound_selected_plan(
    value: float, calibration: Calibration, *, uncertainty: float
) -> PerformanceBound | None:
    """Conformal interval of a plan **chosen by the optimizer** (PLAN.md batch 1.6).

    The interval is computed as for an exchangeable plan, but it is labelled
    ``regime="selected"``: the plan maximizes the prediction, so it is not exchangeable
    with the calibration set and its nominal coverage is not guaranteed (winner's
    curse, AUDIT.md §5.3). No drift test is run: it would need the true value of the
    chosen plan, which only the oracle can give. The report says so; a procedure valid
    under selection is PLAN.md phase 6.4.

    Parameters
    ----------
    value : float
        Prediction of the surrogate at the returned plan.
    calibration : Calibration
        Scores normalized by ``σ`` (:meth:`archlux.uq.conforme.CalibrateurConforme.ajuster`).
    uncertainty : float
        ``σ̂`` of the surrogate at the returned plan, strictly positive.

    Returns
    -------
    PerformanceBound or None
        With ``regime="selected"`` and ``coverage_guaranteed`` false; ``None`` (the
        report says ``NOT EVALUABLE``) when the surrogate gives no positive finite
        ``σ̂`` at the plan, rather than discarding a plan whose geometry is proved.
    """
    if not (isfinite(uncertainty) and uncertainty > 0.0):
        return None
    return borner(value, calibration, incertitude=uncertainty, regime="selected")


__getattr__ = lazy_aliases(
    __name__,
    {
        "construire_borne": Alias(build_bound, "archlux.certify.borne.build_bound"),
    },
)
