"""Assembly of the probabilistic guarantee in the certificate.

This module is the **only** way a daylight value enters an
:class:`archlux.types.Certificate`. It always enters with its coverage and the size of the
calibration set: no value without its uncertainty.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite

import numpy as np

from archlux._deprecation import Alias, lazy_aliases, renamed_parameters
from archlux.errors import InvariantViolation
from archlux.types import PerformanceBound, Regime
from archlux.uq.conformal import Calibration, ConformalCalibrator, bound, conformal_quantile
from archlux.uq.drift import DriftDiagnostic

__all__ = [
    "Calibration",
    "PolicyCalibration",
    "bound_policy_plan",
    "bound_selected_plan",
    "build_bound",
    "calibrate_policy",
    "check_calibration",
    "policy_settings",
]


@renamed_parameters({"valeur": "value", "derive": "drift", "incertitude": "uncertainty"})
def build_bound(
    value: float,
    calibration: Calibration,
    drift: DriftDiagnostic,
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
        See :func:`archlux.uq.conformal.bound`.

    Returns
    -------
    PerformanceBound or None
        ``None`` means ``NOT EVALUABLE``: the system prefers to claim nothing rather than
        claim a coverage it cannot hold.

    Notes
    -----
    Two traps that the signature does not catch:

    - **``uncertainty`` must match the calibration.** The only calibration builder of the
      repository, :meth:`archlux.uq.conformal.ConformalCalibrator.fit`, divides the
      scores by ``σ``; ``Calibration`` does not record it, the caller does.
    - **A drift verdict that does not reject is not a proof of exchangeability.** It is
      treated here as a permission to publish; with few observations, the test of
      :func:`archlux.uq.drift.check_drift` has almost no power. The certificate
      therefore says "drift not detected", never "no drift".
    """
    if not drift.exchangeable:
        return None
    return bound(value, calibration, uncertainty=uncertainty, regime=regime)


@dataclass(frozen=True, slots=True)
class PolicyCalibration:
    """Conformal scores computed on the outputs of one **frozen** optimization policy.

    A passive calibration (scores on plans nobody optimized) does not cover the plans
    the optimizer selects: measured 76.0 % for a 90 % target (``results/j5_selection.md``).
    Recomputing the scores on the plans **that same policy returned**, for calibration
    inputs exchangeable with the plans it will be applied to, restores the nominal
    coverage marginally (91.3 % measured, intervals 21 % wider). Both results are on
    synthetic two-room plans with the closed-form oracle as reference.

    The guarantee holds only for the policy that produced the scores. ``settings`` names
    it; :func:`archlux.legalize` refuses to apply this calibration under other settings.

    Attributes
    ----------
    calibration : Calibration
        Scores ``|y - y_hat| / sigma`` on the policy's outputs.
    settings : tuple of (str, str)
        The frozen policy, sorted by key: surrogate type and indicator, displacement
        budget, Frank-Wolfe settings (:func:`policy_settings`).
    """

    calibration: Calibration
    settings: tuple[tuple[str, str], ...]

    @property
    def indicator(self) -> str:
        """Indicator of the scores.

        Returns
        -------
        str
            The calibration's indicator.
        """
        return self.calibration.indicator


def policy_settings(objective: object, **settings: object) -> tuple[tuple[str, str], ...]:
    """Name a frozen policy: the objective's type and indicator, then its settings.

    The surrogate's weights are not fingerprinted (the protocol does not expose them): two
    objects of the same class with different weights read as the same policy. Keep one
    calibration per trained model.

    Parameters
    ----------
    objective : Surrogate
        Objective the policy maximizes.
    **settings
        Policy settings (``budget``, ``max_iter``, ``penalty``, ``stall_window``...).

    Returns
    -------
    tuple of (str, str)
        Sorted ``(key, text)`` pairs (:func:`_setting_text`).
    """
    named: dict[str, object] = {
        "objective": type(objective).__qualname__,
        "indicator": getattr(objective, "indicator", "?"),
        **settings,
    }
    return tuple(sorted((key, _setting_text(value)) for key, value in named.items()))


def _setting_text(value: object) -> str:
    """Canonical text of a setting: ``1`` and ``1.0`` name the same budget.

    Parameters
    ----------
    value : object
        Setting value.

    Returns
    -------
    str
        A string as is, a real number as ``repr(float)``, anything else ``repr``.
    """
    if isinstance(value, str):
        return value
    if isinstance(value, int | float) and not isinstance(value, bool):
        return repr(float(value))
    return repr(value)


def calibrate_policy(
    predictions: np.ndarray,
    truths: np.ndarray,
    uncertainties: np.ndarray,
    *,
    indicator: str,
    settings: Mapping[str, object] | tuple[tuple[str, str], ...],
    alpha: float = 0.10,
) -> PolicyCalibration:
    """Fit a policy calibration on what the frozen policy returned.

    Parameters
    ----------
    predictions, truths, uncertainties : numpy.ndarray
        One value per calibration input: the surrogate's prediction at the plan the
        policy **returned**, the reference value of that plan, and ``sigma`` there.
    indicator : str
        Indicator of the surrogate.
    settings : mapping or tuple of (str, str)
        The output of :func:`policy_settings` for the policy that was run.
    alpha : float, optional
        Target miscoverage (default 0.10, 90 % coverage).

    Returns
    -------
    PolicyCalibration
        Ready for ``legalize(..., calibration=...)`` under the same settings.
    """
    calibrator = ConformalCalibrator()
    calibrator.fit(predictions, truths, uncertainties, alpha=alpha)
    assert calibrator.scores is not None  # set by fit
    calibration = Calibration(
        scores=calibrator.scores,
        alpha=calibrator.alpha,
        indicator=indicator,
        data_fingerprint=calibrator.data_fingerprint,
    )
    pairs = tuple(settings.items()) if isinstance(settings, Mapping) else settings
    return PolicyCalibration(calibration, tuple(sorted((str(k), str(v)) for k, v in pairs)))


def bound_policy_plan(
    value: float, calibration: PolicyCalibration, *, uncertainty: float
) -> PerformanceBound | None:
    """Conformal interval of a plan returned by the policy that ``calibration`` scored.

    Parameters
    ----------
    value : float
        Prediction of the surrogate at the returned plan.
    calibration : PolicyCalibration
        Scores of the same frozen policy.
    uncertainty : float
        ``sigma`` of the surrogate at the returned plan, strictly positive.

    Returns
    -------
    PerformanceBound or None
        With ``regime="policy_calibrated"`` (nominal coverage guaranteed marginally over
        inputs exchangeable with the calibration inputs); ``None`` without a positive
        finite ``sigma``.
    """
    if not (isfinite(uncertainty) and uncertainty > 0.0):
        return None
    return bound(
        value, calibration.calibration, uncertainty=uncertainty, regime="policy_calibrated"
    )


def check_calibration(calibration: object) -> None:
    """Refuse, before any solving, a calibration that could not give a finite bound.

    Parameters
    ----------
    calibration
        Calibration to check.

    Raises
    ------
    InvariantViolation
        Not a :class:`Calibration`, non-finite scores, ``alpha`` outside ``]0, 1[`` or a
        set too small for ``alpha``: the conformal quantile is computed once here.
    """
    if isinstance(calibration, PolicyCalibration):
        calibration = calibration.calibration
    if not isinstance(calibration, Calibration):
        raise InvariantViolation(
            (f"calibration must be a Calibration, got {type(calibration).__name__}",)
        )
    conformal_quantile(calibration.scores, calibration.alpha)


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
        Scores normalized by ``σ`` (:meth:`archlux.uq.conformal.ConformalCalibrator.fit`).
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
    return bound(value, calibration, uncertainty=uncertainty, regime="selected")


__getattr__ = lazy_aliases(
    __name__,
    {
        "construire_borne": Alias(build_bound, "archlux.certify.bound.build_bound"),
    },
)
