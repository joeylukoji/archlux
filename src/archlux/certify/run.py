"""One repair attempt, recorded whatever its outcome (failure taxonomy and run report).

A scientific library must be able to answer *no certified solution found* instead of
returning a doubtful plan, and must keep its failures: they measure the limits of the
method. :func:`run_repair` calls an injected ``legalize``, re-checks its output with the
independent validator (:func:`archlux.certify.validation.validate_plan`) and returns a
:class:`RunReport` in every case: one row of an experiment table, serializable to JSON.

Outcomes
========
``repaired``
    ``legalize`` returned a plan **and** the independent validator accepts it. This says
    nothing about optimality: a Frank-Wolfe run stopped on ``max_iter`` is still
    ``repaired`` (the geometry holds), with a warning that the point is not stationary.
``rejected``
    The input is outside what the method represents: malformed data, an inconsistent or
    unseparated relative order, an unsupported geometry (oblique load-bearing wall, a gap
    that needs the tiling grid), an invalid surrogate or calibration.
``infeasible``
    The solver proved (Farkas) that no valid plan exists **for the proposed relative
    order** under the constraints and budget given. Another order might admit one: this
    library never changes the topology.
``computation_failure``
    The computation did not produce a certified plan: the solver broke an invariant,
    raised a numerical error, or returned a plan the independent validator refuses
    (reported as *no certified solution found*).

Denominators
============
:func:`tally` counts every outcome over **all** input plans, so a success rate can be
reported against the inputs and not only against the plans that reached the solver.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Literal

from archlux.certify.proof import max_displacement
from archlux.certify.validation import (
    ExtraConstraint,
    ValidationReport,
    _literal,
    validate_plan,
)
from archlux.errors import (
    ArchluxError,
    CalibrationLocked,
    InconsistentOrder,
    Infeasible,
    InvalidInput,
    InvalidSurrogate,
    InvariantViolation,
    MissingSeparation,
    UnsupportedInput,
)
from archlux.geom.rectilinear import RectilinearRoom
from archlux.types import Context, Plan

__all__ = [
    "NO_CERTIFIED_SOLUTION",
    "RUN_STATUSES",
    "RunReport",
    "RunStatus",
    "classify_failure",
    "run_repair",
    "tally",
]

RunStatus = Literal["repaired", "rejected", "infeasible", "computation_failure"]
"""Outcome of one repair attempt (see the module docstring)."""

RUN_STATUSES: tuple[RunStatus, ...] = ("repaired", "rejected", "infeasible", "computation_failure")
"""Every outcome, in report order."""

NO_CERTIFIED_SOLUTION = "no certified solution found"
"""Reason prefix of every attempt that ends without a certified plan."""

_REJECTED = (
    InvalidInput,
    InconsistentOrder,
    MissingSeparation,
    UnsupportedInput,
    InvalidSurrogate,
    CalibrationLocked,
)

Legalize = Callable[..., object]
"""``legalize(plan, ctx, **options)`` returning a ``Plan`` or a ``(Plan, Trace)`` pair."""

_RUN_REPORT_VERSION = 1


def classify_failure(error: BaseException) -> tuple[RunStatus, str]:
    """Map an exception of a repair attempt to its outcome and a one-line reason.

    Parameters
    ----------
    error : BaseException
        Exception raised by ``legalize``.

    Returns
    -------
    tuple of (RunStatus, str)
        The outcome, and a reason naming the exception type.

    Examples
    --------
    >>> from archlux.errors import InvariantViolation
    >>> classify_failure(InvariantViolation(("overlap a|b",)))[0]
    'computation_failure'
    """
    kind = type(error).__name__
    if isinstance(error, Infeasible):
        verified = {True: "verified exactly", False: "NOT verified", None: "unverified"}
        status = verified[error.verified]
        return "infeasible", (
            f"{NO_CERTIFIED_SOLUTION}: infeasible for the proposed relative order "
            f"(Farkas certificate {status}): {error}"
        )
    if isinstance(error, _REJECTED):
        return "rejected", f"{NO_CERTIFIED_SOLUTION}: input rejected ({kind}): {error}"
    if isinstance(error, InvariantViolation):
        return "computation_failure", f"{NO_CERTIFIED_SOLUTION}: solver invariant broken: {error}"
    return "computation_failure", f"{NO_CERTIFIED_SOLUTION}: {kind}: {error}"


@dataclass(frozen=True, slots=True, kw_only=True)
class RunReport:
    """Structured record of one repair attempt (PLAN 1.10): one row of an experiment.

    Attributes
    ----------
    plan_id : str
        Stable identifier of the input plan.
    status : RunStatus
        Outcome of the attempt.
    reason : str
        Why, in one sentence; starts with :data:`NO_CERTIFIED_SOLUTION` unless repaired.
    initial : ValidationReport
        Independent validation of the **input** plan (its initial violations).
    final : ValidationReport or None
        Independent validation of the returned plan; ``None`` if nothing was returned.
    objective_initial, objective_final : float or None
        First and last objective values of the Frank-Wolfe trace, when traced.
    predicted : tuple of (float, float, float) or None
        ``(value, lower, upper)`` of the conformal bound on the surrogate's prediction.
    predicted_regime : str or None
        Regime of that bound (``"selected"`` after optimization: coverage not
        guaranteed).
    reference_value : float or None
        Value of an independent reference (simulation), when one was run.
    max_displacement_m : float or None
        Largest change of a room coordinate, in metres.
    total_displacement_m : float or None
        Sum over rooms of ``|dx| + |dy| + |dw| + |dh|``, in metres.
    iterations : int or None
        Frank-Wolfe iterations, when traced.
    stop_status : str or None
        Why Frank-Wolfe stopped, when traced.
    elapsed_s : float
        Wall-clock time of the ``legalize`` call, in seconds.
    error_type : str or None
        Exception type of a failed attempt.
    warnings : tuple of str
        Caveats of a repaired plan (non-converged optimizer, solver/validator
        disagreement...).
    parameters : tuple of (str, str)
        Options passed to ``legalize``, as text, for reproduction.
    ood_distance : float or None
        Distance of the returned plan to the surrogate's training distribution, when an
        ``ood_check`` was given (:meth:`archlux.light.ood.FeatureEnvelope.check`).
    ood_uncertain : bool or None
        Whether that check flags the prediction as uncertain (out of distribution).
    gain_status : str or None
        How the predicted gain stands against the reference
        (:data:`archlux.light.evaluation.GainStatus`: ``closed_form_only`` while the
        reference is the frozen formula, never ``confirmed`` without a physical one).
    """

    plan_id: str
    status: RunStatus
    reason: str
    initial: ValidationReport
    final: ValidationReport | None = None
    objective_initial: float | None = None
    objective_final: float | None = None
    predicted: tuple[float, float, float] | None = None
    predicted_regime: str | None = None
    reference_value: float | None = None
    max_displacement_m: float | None = None
    total_displacement_m: float | None = None
    iterations: int | None = None
    stop_status: str | None = None
    elapsed_s: float = 0.0
    error_type: str | None = None
    warnings: tuple[str, ...] = ()
    parameters: tuple[tuple[str, str], ...] = field(default=())
    ood_distance: float | None = None
    ood_uncertain: bool | None = None
    gain_status: str | None = None

    @property
    def certified(self) -> bool:
        """``True`` iff a plan was returned and the independent validator accepts it.

        Returns
        -------
        bool
            Same as ``status == "repaired"``.
        """
        return self.status == "repaired"

    @property
    def certificate_status(self) -> str:
        """Evidence behind the returned plan: ``exact``, ``numeric`` or ``none``.

        Returns
        -------
        str
            :attr:`ValidationReport.evidence` of the final plan, ``none`` if not certified.
        """
        if self.final is None or not self.certified:
            return "none"
        return self.final.evidence

    @property
    def uncertainty(self) -> float | None:
        """Width ``upper - lower`` of the predicted bound, if any.

        Returns
        -------
        float or None
            Width of the conformal interval, in the unit of the indicator.
        """
        if self.predicted is None:
            return None
        return self.predicted[2] - self.predicted[1]

    def to_dict(self) -> dict[str, object]:
        """Serialize to JSON-compatible values.

        Returns
        -------
        dict
            Every field; validation reports nested.
        """
        return {
            "version": _RUN_REPORT_VERSION,
            "plan_id": self.plan_id,
            "status": self.status,
            "reason": self.reason,
            "certificate_status": self.certificate_status,
            "initial": self.initial.to_dict(),
            "final": None if self.final is None else self.final.to_dict(),
            "objective_initial": self.objective_initial,
            "objective_final": self.objective_final,
            "predicted": None if self.predicted is None else list(self.predicted),
            "predicted_regime": self.predicted_regime,
            "reference_value": self.reference_value,
            "max_displacement_m": self.max_displacement_m,
            "total_displacement_m": self.total_displacement_m,
            "iterations": self.iterations,
            "stop_status": self.stop_status,
            "elapsed_s": self.elapsed_s,
            "error_type": self.error_type,
            "warnings": list(self.warnings),
            "parameters": [list(pair) for pair in self.parameters],
            "ood_distance": self.ood_distance,
            "ood_uncertain": self.ood_uncertain,
            "gain_status": self.gain_status,
        }

    def to_json(self) -> str:
        """Serialize to a JSON string (``NaN`` and infinities refused).

        Returns
        -------
        str
            Strict JSON, sorted keys.
        """
        return json.dumps(self.to_dict(), sort_keys=True, allow_nan=False)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> RunReport:
        """Rebuild a report from :meth:`to_dict`.

        Parameters
        ----------
        data : dict
            Output of :meth:`to_dict`.

        Returns
        -------
        RunReport
            The same report.

        Raises
        ------
        InvalidInput
            If the status is unknown, or the stored certificate status disagrees with
            the stored validation (the status is recomputed, never trusted).
        """
        initial, final = data["initial"], data["final"]
        warnings, parameters = data["warnings"], data["parameters"]
        assert isinstance(initial, dict) and (final is None or isinstance(final, dict))
        assert isinstance(warnings, list) and isinstance(parameters, list)
        report = cls(
            plan_id=str(data["plan_id"]),
            status=_literal(data["status"], RUN_STATUSES),
            reason=str(data["reason"]),
            initial=ValidationReport.from_dict(initial),
            final=None if final is None else ValidationReport.from_dict(final),
            objective_initial=_float_or_none(data["objective_initial"]),
            objective_final=_float_or_none(data["objective_final"]),
            predicted=_triple(data["predicted"]),
            predicted_regime=_str_or_none(data["predicted_regime"]),
            reference_value=_float_or_none(data["reference_value"]),
            max_displacement_m=_float_or_none(data["max_displacement_m"]),
            total_displacement_m=_float_or_none(data["total_displacement_m"]),
            iterations=None if data["iterations"] is None else int(str(data["iterations"])),
            stop_status=_str_or_none(data["stop_status"]),
            elapsed_s=float(str(data["elapsed_s"])),
            error_type=_str_or_none(data["error_type"]),
            warnings=tuple(str(w) for w in warnings),
            parameters=tuple((str(k), str(v)) for k, v in parameters),
            ood_distance=_float_or_none(data.get("ood_distance")),
            ood_uncertain=_bool_or_none(data.get("ood_uncertain")),
            gain_status=_str_or_none(data.get("gain_status")),
        )
        if data.get("certificate_status") != report.certificate_status:
            raise InvalidInput(
                "report.certificate_status",
                "stored certificate status disagrees with the stored validation",
            )
        return report

    @classmethod
    def from_json(cls, text: str) -> RunReport:
        """Rebuild a report from :meth:`to_json`.

        Parameters
        ----------
        text : str
            Output of :meth:`to_json`.

        Returns
        -------
        RunReport
            The same report.
        """
        data = json.loads(text)
        assert isinstance(data, dict)
        return cls.from_dict(data)


def _float_or_none(value: object) -> float | None:
    return None if value is None else float(str(value))


def _triple(value: object) -> tuple[float, float, float] | None:
    if value is None:
        return None
    assert isinstance(value, list) and len(value) == 3
    return float(value[0]), float(value[1]), float(value[2])


def _str_or_none(value: object) -> str | None:
    return None if value is None else str(value)


def _total_displacement(plan: Plan, reference: Plan) -> float:
    """Sum over shared rooms of ``|dx| + |dy| + |dw| + |dh|``, in metres.

    Parameters
    ----------
    plan : Plan
        Returned plan.
    reference : Plan
        Proposed plan.

    Returns
    -------
    float
        Total L1 displacement, in metres.
    """
    by_id = {room.id: room for room in reference.rooms}
    total = 0.0
    for room in plan.rooms:
        origin = by_id.get(room.id)
        if origin is not None:
            total += sum(abs(getattr(room, f) - getattr(origin, f)) for f in ("x", "y", "w", "h"))
    return total


def _unpack(returned: object) -> tuple[Plan, object | None]:
    """The plan and the trace of whatever ``legalize`` returned.

    Parameters
    ----------
    returned : object
        A ``Plan`` or a ``(Plan, Trace)`` pair.

    Returns
    -------
    tuple of (Plan, object or None)
        The plan, and the trace if there was one.

    Raises
    ------
    InvariantViolation
        If ``legalize`` returned anything else.
    """
    if isinstance(returned, tuple) and len(returned) == 2 and isinstance(returned[0], Plan):
        return returned[0], returned[1]
    if isinstance(returned, Plan):
        return returned, None
    raise InvariantViolation((f"legalize returned {type(returned).__name__}, not a Plan",))


_OOD_WARNING = "returned plan outside the surrogate's training distribution: prediction uncertain"


def _bool_or_none(value: object) -> bool | None:
    if value is None:
        return None
    if not isinstance(value, bool):
        raise InvalidInput("report.ood_uncertain", f"expected a bool or null, got {value!r}")
    return value


def _optimization_fields(plan: Plan) -> dict[str, object]:
    """Iterations and stop status from the certificate, when no trace was requested.

    Parameters
    ----------
    plan : Plan
        Returned plan.

    Returns
    -------
    dict
        ``iterations`` and ``stop_status`` (empty in classic mode).
    """
    status = None if plan.certificate is None else plan.certificate.optimization
    if status is None:
        return {}
    return {"iterations": status.iterations, "stop_status": status.status}


def _ood_fields(plan: Plan, ood_check: Callable[[Plan], object] | None) -> dict[str, object]:
    """Distance and flag of an out-of-distribution check of the returned plan.

    Parameters
    ----------
    plan : Plan
        Returned plan.
    ood_check : callable or None
        Returns an object with ``distance`` and ``uncertain`` (an ``OODVerdict``).

    Returns
    -------
    dict
        ``ood_distance`` and ``ood_uncertain`` (empty without a check).
    """
    if ood_check is None:
        return {}
    verdict = ood_check(plan)
    return {
        "ood_distance": float(getattr(verdict, "distance")),  # noqa: B009 - duck-typed verdict
        "ood_uncertain": bool(getattr(verdict, "uncertain")),  # noqa: B009
    }


def _trace_fields(trace: object | None) -> dict[str, object]:
    """Objective values, iteration count and stop status of a Frank-Wolfe trace.

    Parameters
    ----------
    trace : object or None
        A ``Trace``, or ``None``.

    Returns
    -------
    dict
        Fields of :class:`RunReport` filled from the trace (empty without one).
    """
    if trace is None:
        return {}
    values = tuple(getattr(trace, "values", ()))
    return {
        "objective_initial": float(values[0]) if values else None,
        "objective_final": float(values[-1]) if values else None,
        "iterations": len(getattr(trace, "iterations", ())),
        "stop_status": getattr(trace, "status", None),
    }


def _bound_fields(plan: Plan) -> dict[str, object]:
    bound = None if plan.certificate is None else plan.certificate.performance
    if bound is None:
        return {}
    return {"predicted": (bound.value, bound.lower, bound.upper), "predicted_regime": bound.regime}


def _warnings(plan: Plan, final: ValidationReport, stop_status: object) -> tuple[str, ...]:
    notes: list[str] = []
    if stop_status not in (None, "converged"):
        notes.append(
            f"optimizer stopped on {stop_status}: the returned point is not a certified "
            "stationary point of the objective"
        )
    claimed = None if plan.certificate is None else plan.certificate.geometry.valid
    if claimed is None:
        notes.append("the plan carries no certificate of its own")
    elif claimed != final.valid:
        notes.append(f"solver certificate says valid={claimed}, independent validator disagrees")
    soft = [r.spec.id for r in final.violated if r.spec.kind == "soft"]
    if soft:
        notes.append(f"soft constraints violated: {', '.join(soft)}")
    return tuple(notes)


def run_repair(
    plan: Plan,
    ctx: Context,
    *,
    legalize: Legalize,
    plan_id: str,
    budget: float | None = None,
    merges: tuple[RectilinearRoom, ...] = (),
    extra: tuple[ExtraConstraint, ...] = (),
    reference_value: float | None = None,
    ood_check: Callable[[Plan], object] | None = None,
    gain_status: str | None = None,
    clock: Callable[[], float] = time.perf_counter,
    **options: object,
) -> RunReport:
    """Attempt one repair and record it, success or failure, never raising on a refusal.

    Parameters
    ----------
    plan : Plan
        Proposed plan.
    ctx : Context
        Its context.
    legalize : callable
        ``archlux.legalize`` or ``archlux.legalize_trace`` (injected: ``certify`` does not
        import ``api``). With ``legalize_trace`` the report carries the iterations.
    plan_id : str
        Stable identifier of the input plan, copied into the report.
    budget : float or None, optional
        Displacement budget, passed to ``legalize`` **and** re-checked independently.
    merges : tuple of RectilinearRoom, optional
        Fused rooms, passed to ``legalize`` and to the validator.
    extra : tuple of ExtraConstraint, optional
        Constraints added during optimization, re-checked on the final plan.
    reference_value : float or None, optional
        Value of an independent reference (simulation) of the returned plan, if run.
    ood_check : callable or None, optional
        ``plan -> verdict`` with ``distance`` and ``uncertain``, run on the returned plan
        (wrap :meth:`archlux.light.ood.FeatureEnvelope.check`; ``certify`` does not import
        ``light``).
    gain_status : str or None, optional
        Status of the predicted gain from
        :func:`archlux.light.evaluation.compare_before_after`, copied into the report.
    clock : callable, optional
        Time source, injectable for tests.
    **options : object
        Other keyword options of ``legalize`` (``objective``, ``calibration``,
        ``tiling``...).

    Returns
    -------
    RunReport
        The record. ``status == "repaired"`` only if the independent validator accepts
        the returned plan.

    Raises
    ------
    TypeError
        Programming errors are not outcomes: they propagate.
    """
    initial = validate_plan(plan, ctx, merges=merges)
    parameters = tuple(
        sorted(
            (k, repr(v)) for k, v in {**options, "budget": budget, "merges": len(merges)}.items()
        )
    )
    common = {"plan_id": plan_id, "initial": initial, "parameters": parameters}
    start = clock()
    try:
        returned = legalize(plan, ctx, budget=budget, merges=merges, **options)
        result, trace = _unpack(returned)
    except (ArchluxError, ArithmeticError, RuntimeError, ValueError) as error:
        failure, why = classify_failure(error)
        return RunReport(
            status=failure,
            reason=why,
            elapsed_s=clock() - start,
            error_type=type(error).__name__,
            **common,  # type: ignore[arg-type]
        )
    elapsed = clock() - start
    final = validate_plan(result, ctx, reference=plan, budget=budget, merges=merges, extra=extra)
    fields = {
        **_optimization_fields(result),
        **_trace_fields(trace),
        **_bound_fields(result),
        **_ood_fields(result, ood_check),
    }
    status: RunStatus = "repaired" if final.valid else "computation_failure"
    failed = [r.spec.id for r in (*final.violated, *final.unknown) if r.spec.kind == "hard"]
    reason = (
        f"independent validator accepts the plan (evidence: {final.evidence})"
        if final.valid
        else f"{NO_CERTIFIED_SOLUTION}: independent validator refuses {', '.join(failed)}"
    )
    return RunReport(
        status=status,
        reason=reason,
        final=final,
        reference_value=reference_value,
        max_displacement_m=max_displacement(result, plan),
        total_displacement_m=_total_displacement(result, plan),
        elapsed_s=elapsed,
        warnings=_warnings(result, final, fields.get("stop_status"))
        + (_OOD_WARNING,) * bool(fields.get("ood_uncertain")),
        gain_status=gain_status,
        **common,  # type: ignore[arg-type]
        **fields,  # type: ignore[arg-type]
    )


def tally(reports: Iterable[RunReport]) -> dict[str, int]:
    """Count the outcomes over **every** input plan.

    Parameters
    ----------
    reports : iterable of RunReport
        One report per input plan.

    Returns
    -------
    dict of str to int
        ``n_inputs`` and one count per :data:`RUN_STATUSES` entry (zeros included), so
        that a rate is always reported against all the inputs.
    """
    counts: dict[str, int] = dict.fromkeys(RUN_STATUSES, 0)
    n = 0
    for report in reports:
        counts[report.status] += 1
        n += 1
    return {"n_inputs": n, **counts}
