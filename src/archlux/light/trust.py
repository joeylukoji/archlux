"""Whether the surrogate's direction is good enough for the optimizer to follow.

:func:`~archlux.light.validation.validate_gradient` is a gate: it raises below the
threshold. This module is the measuring side, and the run-time guard:

- :func:`gradient_agreement` and :func:`gradient_reliability`: sign agreement and cosine
  of the declared gradient against centred finite differences of an **independent**
  evaluator, per azimuth sector, room type and perturbation amplitude, on any plans,
  including the ones the optimizer produced;
- :func:`step_gain_audit`: for a sequence of iterates, the gain the surrogate predicted
  for each step against the gain the reference realised;
- :func:`gradient_trust` and :class:`GuardedSurrogate`: a non-raising verdict ``"ok"`` /
  ``"refuse"``, and a :class:`~archlux.light.protocol.Surrogate` wrapper that applies it
  at every gradient call. On ``"refuse"`` it either returns a zero gradient (Frank-Wolfe
  then sees a zero duality gap and stops where it is) or raises
  :class:`UntrustedGradient`. ``solve`` needs no change: the guard is an objective;
- :class:`FiniteDifferenceSurrogate`: the gradient-free baseline. Any deterministic
  evaluator, the frozen oracle included, becomes a ``Surrogate`` whose gradient is its
  own centred finite differences: the optimizer then never reads a learned direction.

The independent evaluator is anything with ``evaluate(x, orientation, *, glazing)``: the
frozen oracle, or a :class:`~archlux.light.reference.Reference` behind
:class:`~archlux.light.reference.ReferenceEvaluator`. Each gradient check costs
``2 len(x)`` evaluations of it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, Protocol

import numpy as np

from archlux._log import event
from archlux.errors import InvalidSurrogate
from archlux.light.evaluation import EvaluationCase, orientation_sector

if TYPE_CHECKING:
    from archlux.arrays import FloatVector
    from archlux.light.protocol import Glazing, Surrogate
    from archlux.types import Indicator, Orientation

__all__ = [
    "DEFAULT_SIGN_THRESHOLD",
    "Evaluator",
    "FiniteDifferenceSurrogate",
    "GradientAgreement",
    "GradientTrust",
    "GuardedSurrogate",
    "ReliabilityRow",
    "StepAudit",
    "UntrustedGradient",
    "gradient_agreement",
    "gradient_reliability",
    "gradient_trust",
    "step_gain_audit",
]

DEFAULT_SIGN_THRESHOLD = 0.80
"""Checkpoint of `MILESTONE-4.md` §7, the same as ``validate_gradient``."""

_FLAT = 1e-3
"""A finite-difference slope below this is "flat": its sign is not counted."""

_TINY = 1e-12


class Evaluator(Protocol):
    """Anything that returns a scalar for a plan: oracle, surrogate, reference adapter."""

    def evaluate(
        self, x: FloatVector, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> float:
        """Scalar value of the plan.

        Parameters
        ----------
        x
            Decision vector.
        orientation
            Azimuth.
        glazing
            Openings, or ``None``.

        Returns
        -------
        float
            The value.
        """
        ...


class UntrustedGradient(InvalidSurrogate):
    """Raised by :class:`GuardedSurrogate` when it refuses a gradient and must not stop.

    Parameters
    ----------
    detail : str
        Why the gradient was refused.
    report : object
        The :class:`GradientTrust` verdict.
    """


def _finite_differences(
    evaluator: Evaluator,
    x: np.ndarray,
    orientation: Orientation,
    step: float,
    glazing: Glazing | None,
) -> np.ndarray:
    """Centred slope of ``evaluator`` along every coordinate, glazing passed on.

    Parameters
    ----------
    evaluator : Evaluator
        Function differentiated.
    x : numpy.ndarray
        Point.
    orientation : Orientation
        Azimuth.
    step : float
        Half-width of the difference, in metres.
    glazing : Glazing or None
        Openings.

    Returns
    -------
    numpy.ndarray
        One slope per coordinate.
    """
    x0 = np.asarray(x, dtype=float).ravel()
    slope = np.empty_like(x0)
    for i in range(x0.size):
        plus, minus = x0.copy(), x0.copy()
        plus[i] += step
        minus[i] -= step
        up = float(evaluator.evaluate(plus, orientation, glazing=glazing))
        down = float(evaluator.evaluate(minus, orientation, glazing=glazing))
        slope[i] = (up - down) / (2.0 * step)
    return slope


@dataclass(frozen=True, slots=True)
class GradientAgreement:
    """Agreement of declared gradients with finite differences, on a set of points.

    Attributes
    ----------
    sign_agreement : float
        Share of non-flat coordinates whose signs match; ``nan`` if every slope is flat.
    mean_cosine : float
        Mean cosine between the two vectors (``nan`` if every pair is null).
    n_points : int
        Points.
    n_coordinates : int
        Non-flat coordinates the sign agreement is computed on.
    step : float
        Finite-difference half-width, in metres.
    """

    sign_agreement: float
    mean_cosine: float
    n_points: int
    n_coordinates: int
    step: float


def _compare(declared: np.ndarray, target: np.ndarray) -> tuple[list[bool], float | None]:
    """Sign matches over the non-flat coordinates, and the cosine.

    Parameters
    ----------
    declared, target : numpy.ndarray
        Declared gradient and finite-difference slope.

    Returns
    -------
    tuple
        Matches of the non-flat coordinates, and the cosine (``None`` if a vector is null).
    """
    keep = np.abs(target) >= _FLAT
    matches = list((np.sign(declared[keep]) == np.sign(target[keep])) & (declared[keep] != 0.0))
    nd, nt = float(np.linalg.norm(declared)), float(np.linalg.norm(target))
    cosine = float(declared @ target / (nd * nt)) if nd > _TINY and nt > _TINY else None
    return matches, cosine


def gradient_agreement(
    surrogate: Surrogate,
    reference: Evaluator,
    points: Sequence[FloatVector],
    orientations: Sequence[Orientation],
    *,
    step: float = 0.10,
    glazing: Sequence[Glazing | None] | None = None,
) -> GradientAgreement:
    """Compare the surrogate's gradients with the reference's finite differences.

    Never raises on a low agreement: it measures.

    Parameters
    ----------
    surrogate : Surrogate
        Model whose ``gradient`` is checked.
    reference : Evaluator
        Independent evaluator, differentiated by centred differences.
    points : sequence of numpy.ndarray
        Decision vectors.
    orientations : sequence of Orientation
        One azimuth per point.
    step : float, optional
        Finite-difference half-width, in metres (the perturbation amplitude).
    glazing : sequence of Glazing or None, optional
        One glazing per point.

    Returns
    -------
    GradientAgreement
        Sign agreement and cosine.
    """
    panes = list(glazing) if glazing is not None else [None] * len(points)
    matches: list[bool] = []
    cosines: list[float] = []
    for x, o, g in zip(points, orientations, panes, strict=True):
        vector = np.asarray(x, dtype=float).ravel()
        declared = np.asarray(surrogate.gradient(vector, o, glazing=g), dtype=float).ravel()
        target = _finite_differences(reference, vector, o, step, g)
        m, c = _compare(declared, target)
        matches.extend(m)
        if c is not None:
            cosines.append(c)
    return GradientAgreement(
        sign_agreement=float(np.mean(matches)) if matches else float("nan"),
        mean_cosine=float(np.mean(cosines)) if cosines else float("nan"),
        n_points=len(points),
        n_coordinates=len(matches),
        step=step,
    )


@dataclass(frozen=True, slots=True)
class ReliabilityRow:
    """Gradient agreement of one group at one perturbation amplitude.

    Attributes
    ----------
    grouping : str
        ``"all"``, ``"azimuth"``, ``"room_type"`` or ``"window_config"``.
    group : str
        Label within the grouping.
    agreement : GradientAgreement
        The measure.
    passed : bool
        ``agreement.sign_agreement >= threshold``.
    """

    grouping: str
    group: str
    agreement: GradientAgreement
    passed: bool


def _labels(case: EvaluationCase, grouping: str, sector_deg: float) -> str:
    """Group label of a case.

    Parameters
    ----------
    case : EvaluationCase
        The case.
    grouping : str
        ``"all"``, ``"azimuth"``, ``"room_type"`` or ``"window_config"``.
    sector_deg : float
        Azimuth sector width.

    Returns
    -------
    str
        The label.
    """
    if grouping == "azimuth":
        return orientation_sector(case.orientation.deg, sector_deg)
    if grouping == "room_type":
        return case.room_type
    if grouping == "window_config":
        return case.window_config
    return "all"


def gradient_reliability(
    surrogate: Surrogate,
    reference: Evaluator,
    cases: Sequence[EvaluationCase],
    *,
    steps: Sequence[float] = (0.02, 0.10, 0.50),
    sector_deg: float = 90.0,
    threshold: float = DEFAULT_SIGN_THRESHOLD,
) -> tuple[ReliabilityRow, ...]:
    """Gradient agreement broken down by azimuth, room type, windows and amplitude.

    Parameters
    ----------
    surrogate : Surrogate
        Model whose gradient is checked.
    reference : Evaluator
        Independent evaluator.
    cases : sequence of EvaluationCase
        Plans, held-out or produced by the optimizer.
    steps : sequence of float, optional
        Perturbation amplitudes, in metres.
    sector_deg : float, optional
        Azimuth sector width.
    threshold : float, optional
        Sign-agreement checkpoint.

    Returns
    -------
    tuple of ReliabilityRow
        For every amplitude: ``all``, then each group of each grouping, sorted.
    """
    rows = []
    for step in steps:
        for grouping in ("all", "azimuth", "room_type", "window_config"):
            labels = [_labels(c, grouping, sector_deg) for c in cases]
            for label in sorted(set(labels)):
                chosen = [c for c, lab in zip(cases, labels, strict=True) if lab == label]
                agreement = gradient_agreement(
                    surrogate,
                    reference,
                    [c.x for c in chosen],
                    [c.orientation for c in chosen],
                    step=step,
                    glazing=[c.glazing for c in chosen],
                )
                ok = bool(agreement.sign_agreement >= threshold)
                rows.append(ReliabilityRow(grouping, label, agreement, ok))
    return tuple(rows)


@dataclass(frozen=True, slots=True)
class StepAudit:
    """One optimizer step: the gain the surrogate announced against the realised gain.

    Attributes
    ----------
    k : int
        Index of the step (from iterate ``k`` to ``k + 1``).
    predicted_gain : float
        ``surrogate(x_{k+1}) - surrogate(x_k)``.
    first_order_gain : float
        ``gradient(x_k) . (x_{k+1} - x_k)``: what the linear model the optimizer used
        promised.
    realised_gain : float
        ``reference(x_{k+1}) - reference(x_k)``.
    sign_agrees : bool
        ``predicted_gain`` and ``realised_gain`` have the same strict sign.
    displacement_l1 : float
        ``sum |x_{k+1} - x_k|``.
    """

    k: int
    predicted_gain: float
    first_order_gain: float
    realised_gain: float
    sign_agrees: bool
    displacement_l1: float


def step_gain_audit(
    surrogate: Surrogate,
    reference: Evaluator,
    iterates: Sequence[FloatVector],
    orientation: Orientation,
    *,
    glazing: Glazing | None = None,
) -> tuple[StepAudit, ...]:
    """Audit every step of an optimization trajectory against the reference.

    Parameters
    ----------
    surrogate : Surrogate
        Model the optimizer followed.
    reference : Evaluator
        Independent evaluator.
    iterates : sequence of numpy.ndarray
        ``x_0, x_1, ...`` (for instance ``Trace.iterations[k].x``).
    orientation : Orientation
        Azimuth.
    glazing : Glazing or None, optional
        Openings.

    Returns
    -------
    tuple of StepAudit
        ``len(iterates) - 1`` rows.
    """
    xs = [np.asarray(x, dtype=float).ravel() for x in iterates]
    s = [float(surrogate.evaluate(x, orientation, glazing=glazing)) for x in xs]
    r = [float(reference.evaluate(x, orientation, glazing=glazing)) for x in xs]
    rows = []
    for k in range(len(xs) - 1):
        dx = xs[k + 1] - xs[k]
        grad = np.asarray(surrogate.gradient(xs[k], orientation, glazing=glazing), dtype=float)
        predicted, realised = s[k + 1] - s[k], r[k + 1] - r[k]
        rows.append(
            StepAudit(
                k=k,
                predicted_gain=predicted,
                first_order_gain=float(grad.ravel() @ dx),
                realised_gain=realised,
                sign_agrees=bool(np.sign(predicted) == np.sign(realised) != 0.0),
                displacement_l1=float(np.abs(dx).sum()),
            )
        )
    return tuple(rows)


@dataclass(frozen=True, slots=True)
class GradientTrust:
    """Verdict on one gradient: follow it, or refuse it.

    Attributes
    ----------
    status : {"ok", "refuse"}
        ``"refuse"`` when the sign agreement is below the threshold or undefined.
    sign_agreement, mean_cosine : float
        The measure at this point.
    threshold : float
        Checkpoint used.
    reason : str
        Plain-language reason.
    """

    status: Literal["ok", "refuse"]
    sign_agreement: float
    mean_cosine: float
    threshold: float
    reason: str


def gradient_trust(
    surrogate: Surrogate,
    reference: Evaluator,
    x: FloatVector,
    orientation: Orientation,
    *,
    glazing: Glazing | None = None,
    threshold: float = DEFAULT_SIGN_THRESHOLD,
    step: float = 0.10,
) -> GradientTrust:
    """Decide, at one point, whether the surrogate's gradient may be followed.

    Parameters
    ----------
    surrogate : Surrogate
        Model.
    reference : Evaluator
        Independent evaluator.
    x
        Decision vector.
    orientation
        Azimuth.
    glazing
        Openings, or ``None``.
    threshold : float, optional
        Minimal sign agreement.
    step : float, optional
        Finite-difference half-width, in metres.

    Returns
    -------
    GradientTrust
        ``"ok"`` or ``"refuse"``; never raises on disagreement.
    """
    a = gradient_agreement(surrogate, reference, [x], [orientation], step=step, glazing=[glazing])
    if not np.isfinite(a.sign_agreement):
        return GradientTrust(
            "refuse", a.sign_agreement, a.mean_cosine, threshold, "reference flat: no direction"
        )
    if a.sign_agreement < threshold:
        reason = f"sign agreement {a.sign_agreement:.3f} < {threshold}"
        return GradientTrust("refuse", a.sign_agreement, a.mean_cosine, threshold, reason)
    return GradientTrust("ok", a.sign_agreement, a.mean_cosine, threshold, "agreement reached")


@dataclass
class GuardedSurrogate:
    """A surrogate whose every gradient is checked against a reference before use.

    Pass it as ``objective=`` to :func:`archlux.legalize`; ``solve`` sees an ordinary
    :class:`~archlux.light.protocol.Surrogate`. ``evaluate`` and ``uncertainty`` are the
    wrapped surrogate's.

    Attributes
    ----------
    surrogate : Surrogate
        Model followed when trusted.
    reference : Evaluator
        Independent evaluator.
    threshold : float
        Minimal sign agreement.
    step : float
        Finite-difference half-width, in metres.
    on_refuse : {"stop", "raise"}
        ``"stop"``: return a zero gradient, so the optimizer stops at the current point.
        ``"raise"``: raise :class:`UntrustedGradient`.
    history : list of GradientTrust
        Every verdict, in call order. Read it to report how often the guard refused.
    """

    surrogate: Surrogate
    reference: Evaluator
    threshold: float = DEFAULT_SIGN_THRESHOLD
    step: float = 0.10
    on_refuse: Literal["stop", "raise"] = "stop"
    history: list[GradientTrust] = field(default_factory=list)

    @property
    def indicator(self) -> Indicator:
        """Indicator of the wrapped surrogate.

        Returns
        -------
        Indicator
            The indicator.
        """
        return self.surrogate.indicator

    def evaluate(
        self, x: FloatVector, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> float:
        """Prediction of the wrapped surrogate.

        Parameters
        ----------
        x
            Decision vector.
        orientation
            Azimuth.
        glazing
            Openings, or ``None``.

        Returns
        -------
        float
            The prediction.
        """
        return float(self.surrogate.evaluate(x, orientation, glazing=glazing))

    def gradient(
        self, x: FloatVector, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> FloatVector:
        """Gradient of the wrapped surrogate if trusted, zero (or an error) otherwise.

        Parameters
        ----------
        x
            Decision vector.
        orientation
            Azimuth.
        glazing
            Openings, or ``None``.

        Returns
        -------
        numpy.ndarray
            The gradient, or zeros when refused with ``on_refuse="stop"``.

        Raises
        ------
        UntrustedGradient
            Refused with ``on_refuse="raise"``.
        """
        verdict = gradient_trust(
            self.surrogate,
            self.reference,
            x,
            orientation,
            glazing=glazing,
            threshold=self.threshold,
            step=self.step,
        )
        self.history.append(verdict)
        event("archlux.light", "gradient.trust", status=verdict.status, sign=verdict.sign_agreement)
        if verdict.status == "ok":
            return np.asarray(self.surrogate.gradient(x, orientation, glazing=glazing), dtype=float)
        if self.on_refuse == "raise":
            raise UntrustedGradient(verdict.reason, report=verdict)
        return np.zeros_like(np.asarray(x, dtype=float))

    def uncertainty(
        self, x: FloatVector, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> float:
        """Uncertainty of the wrapped surrogate.

        Parameters
        ----------
        x
            Decision vector.
        orientation
            Azimuth.
        glazing
            Openings, or ``None``.

        Returns
        -------
        float
            The predictive standard deviation.
        """
        return float(self.surrogate.uncertainty(x, orientation, glazing=glazing))

    @property
    def refusals(self) -> int:
        """Number of refused gradients so far.

        Returns
        -------
        int
            Count of ``"refuse"`` verdicts.
        """
        return sum(v.status == "refuse" for v in self.history)


@dataclass(frozen=True, slots=True)
class FiniteDifferenceSurrogate:
    """Gradient-free baseline: a deterministic evaluator with finite-difference gradient.

    Optimizing it runs the same Frank-Wolfe on the same polytope without any learned
    direction. With the frozen oracle as ``base``, it is the "oracle-in-the-loop" arm of
    an ablation (``2 len(x)`` evaluations per iteration).

    Attributes
    ----------
    base : Evaluator
        Deterministic evaluator.
    target_indicator : Indicator
        Indicator reported to the solver.
    sigma : float
        Constant uncertainty reported (the evaluator has none of its own). A workshop
        value, like ``SplitFluxOracle.sigma_nominal``: do not calibrate on it.
    step : float
        Finite-difference half-width, in metres.
    """

    base: Evaluator
    target_indicator: Indicator = "sDA"
    sigma: float = 0.04
    step: float = 0.05

    @property
    def indicator(self) -> Indicator:
        """Reported indicator.

        Returns
        -------
        Indicator
            ``target_indicator``.
        """
        return self.target_indicator

    def evaluate(
        self, x: FloatVector, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> float:
        """Value of the evaluator.

        Parameters
        ----------
        x
            Decision vector.
        orientation
            Azimuth.
        glazing
            Openings, or ``None``.

        Returns
        -------
        float
            The value.
        """
        return float(self.base.evaluate(x, orientation, glazing=glazing))

    def gradient(
        self, x: FloatVector, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> FloatVector:
        """Centred finite differences of the evaluator.

        Parameters
        ----------
        x
            Decision vector.
        orientation
            Azimuth.
        glazing
            Openings, or ``None``.

        Returns
        -------
        numpy.ndarray
            One slope per coordinate.
        """
        return _finite_differences(
            self.base, np.asarray(x, dtype=float), orientation, self.step, glazing
        )

    def uncertainty(
        self, x: FloatVector, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> float:
        """Constant ``sigma``.

        Parameters
        ----------
        x
            Decision vector (unused).
        orientation
            Azimuth (unused).
        glazing
            Openings (unused).

        Returns
        -------
        float
            ``sigma``.
        """
        del x, orientation, glazing
        return self.sigma
