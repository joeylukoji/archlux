"""Evaluate a surrogate against an independent reference, on held-out plans only.

Two questions, two functions:

- :func:`evaluate_surrogate`: **how wrong is the surrogate on plans it never saw?**
  Absolute and relative error, bias, linear and rank correlation, overall and broken
  down by orientation sector, room type and window configuration. Every number comes
  with a seeded bootstrap interval (``ARCHITECTURE.md`` §7: never a bare scalar). A case
  whose id was used for training or tuning is refused, not silently scored;
- :func:`compare_before_after`: **is the gain the optimizer reports real?** For each
  plan, before and after optimization: the surrogate prediction, the reference measure,
  the gap between the two gains, and the geometric displacement that bought the gain.
  :attr:`GainSummary.claim` says which word a paper may use: ``"predicted"`` unless a
  **physical** reference confirmed the gain.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

import numpy as np

from archlux.errors import InvalidInput
from archlux.light.protocol import point_prediction
from archlux.light.reference import ReferenceUnavailable

if TYPE_CHECKING:
    from archlux.arrays import FloatVector
    from archlux.light.protocol import Glazing, Surrogate
    from archlux.light.reference import Reference, ReferenceKind
    from archlux.types import Orientation

__all__ = [
    "BeforeAfter",
    "ErrorSummary",
    "Estimate",
    "EvaluationCase",
    "GainSummary",
    "SurrogateEvaluation",
    "compare_before_after",
    "evaluate_surrogate",
    "orientation_sector",
    "summarize_gains",
]

GainStatus = Literal["confirmed", "contradicted", "closed_form_only", "predicted_only"]
"""``confirmed``/``contradicted``: by a physical reference. ``closed_form_only``: the
reference is a formula. ``predicted_only``: the reference could not measure the plan."""

_N_BOOTSTRAP = 1000
_LEVEL = 0.95
_TINY = 1e-12


@dataclass(frozen=True, slots=True)
class EvaluationCase:
    """One held-out plan, with the labels it is grouped by.

    Attributes
    ----------
    id : str
        Stable identifier of the plan, checked against the training ids.
    x : numpy.ndarray
        Decision vector.
    orientation : Orientation
        Azimuth.
    glazing : Glazing or None
        Openings, or ``None``.
    room_type : str
        Group label: dominant room type, or ``"mixed"``.
    window_config : str
        Group label of the fenestration (``"none"``, ``"south"``, ``"two-sided"``...).
    """

    id: str
    x: FloatVector
    orientation: Orientation
    glazing: Glazing | None = None
    room_type: str = "unknown"
    window_config: str = "unknown"


@dataclass(frozen=True, slots=True)
class Estimate:
    """A value and its percentile-bootstrap interval.

    Attributes
    ----------
    value : float
        Point estimate on the full sample; ``nan`` when undefined.
    low, high : float
        Bounds of the bootstrap interval at level ``level``.
    level : float
        Confidence level of the interval.
    """

    value: float
    low: float
    high: float
    level: float = _LEVEL


@dataclass(frozen=True, slots=True)
class ErrorSummary:
    """Errors of the surrogate against the reference on one group of cases.

    Attributes
    ----------
    n : int
        Number of cases measured by the reference.
    same_unit : bool
        Whether the surrogate and the reference share a unit. When ``False``, the
        absolute errors and the bias are ``nan``: only correlations are meaningful.
    mae, relative_error, bias : Estimate
        Mean absolute error, mean ``|pred - ref| / |ref|``, mean ``pred - ref``.
    pearson, spearman : Estimate
        Linear and rank correlations (``nan`` below three cases or for a constant).
    """

    n: int
    same_unit: bool
    mae: Estimate
    relative_error: Estimate
    bias: Estimate
    pearson: Estimate
    spearman: Estimate


@dataclass(frozen=True, slots=True)
class SurrogateEvaluation:
    """Full held-out evaluation of a surrogate.

    Attributes
    ----------
    overall : ErrorSummary
        All cases.
    by_orientation, by_room_type, by_window_config : tuple of (str, ErrorSummary)
        One summary per group, sorted by label.
    reference_kind : ReferenceKind
        ``"physical"`` or ``"closed_form"``.
    reference_engine : str
        Engine of the measures.
    n_cases : int
        Cases given.
    n_unmeasured : int
        Cases the reference could not measure (left out of every summary, counted here).
    """

    overall: ErrorSummary
    by_orientation: tuple[tuple[str, ErrorSummary], ...]
    by_room_type: tuple[tuple[str, ErrorSummary], ...]
    by_window_config: tuple[tuple[str, ErrorSummary], ...]
    reference_kind: ReferenceKind
    reference_engine: str
    n_cases: int
    n_unmeasured: int


def orientation_sector(deg: float, width: float = 90.0) -> str:
    """Label of the circular sector of ``deg``, sectors centred on ``0``.

    Parameters
    ----------
    deg : float
        Azimuth in degrees.
    width : float, optional
        Sector width in degrees; must divide 360.

    Returns
    -------
    str
        Centre of the sector, for instance ``"90"`` for ``deg = 100`` and ``width = 90``.
    """
    centre = (round((deg % 360.0) / width) * width) % 360.0
    return f"{centre:g}"


def _pearson(a: np.ndarray, b: np.ndarray) -> float:
    """Pearson correlation, ``nan`` below three points or for a constant sample.

    Parameters
    ----------
    a, b : numpy.ndarray
        Paired samples.

    Returns
    -------
    float
        The correlation, or ``nan``.
    """
    if a.size < 3 or np.std(a) < _TINY or np.std(b) < _TINY:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def _ranks(a: np.ndarray) -> np.ndarray:
    """Average ranks (ties share their mean rank).

    Parameters
    ----------
    a : numpy.ndarray
        Sample.

    Returns
    -------
    numpy.ndarray
        Ranks, starting at 0.
    """
    order = np.argsort(a, kind="stable")
    ranks = np.empty(a.size, dtype=float)
    ranks[order] = np.arange(a.size, dtype=float)
    for value in np.unique(a):
        tie = a == value
        ranks[tie] = ranks[tie].mean()
    return ranks


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    """Spearman rank correlation.

    Parameters
    ----------
    a, b : numpy.ndarray
        Paired samples.

    Returns
    -------
    float
        The correlation of the ranks, or ``nan``.
    """
    return _pearson(_ranks(a), _ranks(b)) if a.size >= 3 else float("nan")


def _bootstrap(
    statistic: Callable[[np.ndarray, np.ndarray], float],
    pred: np.ndarray,
    ref: np.ndarray,
    rng: np.random.Generator,
) -> Estimate:
    """Percentile bootstrap of a paired statistic.

    Parameters
    ----------
    statistic : callable
        ``(pred, ref) -> float``.
    pred, ref : numpy.ndarray
        Paired samples.
    rng : numpy.random.Generator
        Seeded generator.

    Returns
    -------
    Estimate
        Statistic on the full sample and its interval; ``nan`` everywhere when empty.
    """
    if pred.size == 0:
        return Estimate(float("nan"), float("nan"), float("nan"))
    value = statistic(pred, ref)
    draws = rng.integers(0, pred.size, size=(_N_BOOTSTRAP, pred.size))
    samples = np.array([statistic(pred[i], ref[i]) for i in draws])
    samples = samples[np.isfinite(samples)]
    if samples.size == 0:
        return Estimate(value, float("nan"), float("nan"))
    tail = (1.0 - _LEVEL) / 2.0
    low, high = np.quantile(samples, [tail, 1.0 - tail])
    return Estimate(value, float(low), float(high))


def _mae(pred: np.ndarray, ref: np.ndarray) -> float:
    """Mean absolute error.

    Parameters
    ----------
    pred, ref : numpy.ndarray
        Paired samples.

    Returns
    -------
    float
        ``mean |pred - ref|``.
    """
    return float(np.mean(np.abs(pred - ref)))


def _relative(pred: np.ndarray, ref: np.ndarray) -> float:
    """Mean relative absolute error.

    Parameters
    ----------
    pred, ref : numpy.ndarray
        Paired samples.

    Returns
    -------
    float
        ``mean |pred - ref| / |ref|``.
    """
    return float(np.mean(np.abs(pred - ref) / np.maximum(np.abs(ref), _TINY)))


def _bias(pred: np.ndarray, ref: np.ndarray) -> float:
    """Mean signed error.

    Parameters
    ----------
    pred, ref : numpy.ndarray
        Paired samples.

    Returns
    -------
    float
        ``mean (pred - ref)``.
    """
    return float(np.mean(pred - ref))


def _nan_statistic(pred: np.ndarray, ref: np.ndarray) -> float:
    """Statistic of a comparison in different units: always ``nan``.

    Parameters
    ----------
    pred, ref : numpy.ndarray
        Unused.

    Returns
    -------
    float
        ``nan``.
    """
    del pred, ref
    return float("nan")


def _summary(
    pred: np.ndarray, ref: np.ndarray, *, same_unit: bool, rng: np.random.Generator
) -> ErrorSummary:
    """Error summary of one group.

    Parameters
    ----------
    pred, ref : numpy.ndarray
        Predictions and reference measures.
    same_unit : bool
        Whether absolute errors are meaningful.
    rng : numpy.random.Generator
        Seeded generator.

    Returns
    -------
    ErrorSummary
        The group summary.
    """
    absolute = (_mae, _relative, _bias) if same_unit else (_nan_statistic,) * 3
    return ErrorSummary(
        n=int(pred.size),
        same_unit=same_unit,
        mae=_bootstrap(absolute[0], pred, ref, rng),
        relative_error=_bootstrap(absolute[1], pred, ref, rng),
        bias=_bootstrap(absolute[2], pred, ref, rng),
        pearson=_bootstrap(_pearson, pred, ref, rng),
        spearman=_bootstrap(_spearman, pred, ref, rng),
    )


def _grouped(
    labels: Sequence[str],
    pred: np.ndarray,
    ref: np.ndarray,
    *,
    same_unit: bool,
    rng: np.random.Generator,
) -> tuple[tuple[str, ErrorSummary], ...]:
    """One summary per label, sorted by label.

    Parameters
    ----------
    labels : sequence of str
        Group of each case.
    pred, ref : numpy.ndarray
        Predictions and reference measures.
    same_unit : bool
        Whether absolute errors are meaningful.
    rng : numpy.random.Generator
        Seeded generator.

    Returns
    -------
    tuple of (str, ErrorSummary)
        The summaries.
    """
    tags = np.array(labels, dtype=object)
    return tuple(
        (label, _summary(pred[tags == label], ref[tags == label], same_unit=same_unit, rng=rng))
        for label in sorted(set(labels))
    )


def _check_held_out(cases: Sequence[EvaluationCase], training_ids: Iterable[str]) -> None:
    """Refuse a case used for training or tuning, and duplicated ids.

    Parameters
    ----------
    cases : sequence of EvaluationCase
        Cases to evaluate.
    training_ids : iterable of str
        Ids of every plan used to train or tune the surrogate.

    Raises
    ------
    InvalidInput
        A case leaks from training, or two cases share an id.
    """
    seen = set(training_ids)
    leaked = sorted(c.id for c in cases if c.id in seen)
    if leaked:
        raise InvalidInput("cases", f"used for training or tuning, not held out: {leaked[:5]}")
    ids = [c.id for c in cases]
    if len(set(ids)) != len(ids):
        raise InvalidInput("cases", "two cases share an id")


def evaluate_surrogate(
    surrogate: Surrogate,
    cases: Sequence[EvaluationCase],
    reference: Reference,
    *,
    seed: int,
    training_ids: Iterable[str],
    surrogate_unit: str = "score",
    sector_deg: float = 90.0,
) -> SurrogateEvaluation:
    """Compare the surrogate with the reference on held-out plans.

    Parameters
    ----------
    surrogate : Surrogate
        Model under test. Its point prediction is read through
        :func:`~archlux.light.protocol.point_prediction` (positive ASE, no margin).
    cases : sequence of EvaluationCase
        Held-out plans.
    reference : Reference
        Independent reference.
    seed : int
        Seed of the bootstrap. Mandatory, no default.
    training_ids : iterable of str
        Ids of every plan used for training **or tuning**; any overlap raises.
    surrogate_unit : str, optional
        Unit of the surrogate's prediction; absolute errors are computed only when it
        equals ``reference.unit``.
    sector_deg : float, optional
        Width of the orientation sectors.

    Returns
    -------
    SurrogateEvaluation
        Overall and per-group errors, the reference's kind and engine, and the number of
        cases the reference could not measure.

    Raises
    ------
    InvalidInput
        A case is not held out, or ids repeat.
    """
    _check_held_out(cases, training_ids)
    rng = np.random.default_rng(seed)
    pred, ref, kept = [], [], []
    engine = "none"
    for case in cases:
        try:
            measure = reference.measure(case.x, case.orientation, glazing=case.glazing)
        except ReferenceUnavailable:
            continue
        engine = measure.engine
        pred.append(point_prediction(surrogate, case.x, case.orientation, glazing=case.glazing)[0])
        ref.append(measure.value)
        kept.append(case)
    p, r = np.array(pred, dtype=float), np.array(ref, dtype=float)
    same = surrogate_unit == reference.unit
    return SurrogateEvaluation(
        overall=_summary(p, r, same_unit=same, rng=rng),
        by_orientation=_grouped(
            [orientation_sector(c.orientation.deg, sector_deg) for c in kept],
            p,
            r,
            same_unit=same,
            rng=rng,
        ),
        by_room_type=_grouped([c.room_type for c in kept], p, r, same_unit=same, rng=rng),
        by_window_config=_grouped([c.window_config for c in kept], p, r, same_unit=same, rng=rng),
        reference_kind=reference.kind,
        reference_engine=engine,
        n_cases=len(cases),
        n_unmeasured=len(cases) - len(kept),
    )


@dataclass(frozen=True, slots=True)
class BeforeAfter:
    """One plan before and after optimization: predicted gain against measured gain.

    Attributes
    ----------
    id : str
        Plan identifier.
    predicted_before, predicted_after : float
        Surrogate point predictions.
    predicted_gain_pct : float
        ``100 (after - before) / |before|`` on the surrogate.
    reference_before, reference_after, reference_gain_pct : float
        Same on the reference; ``nan`` when it could not measure.
    gap_pct : float
        ``predicted_gain_pct - reference_gain_pct``: how much of the gain the surrogate
        invents (positive) or misses (negative). ``nan`` when unmeasured.
    displacement_l1, displacement_max : float
        ``sum |x_after - x_before|`` and its largest coordinate, in metres.
    status : GainStatus
        What the reference says about the predicted gain.
    """

    id: str
    predicted_before: float
    predicted_after: float
    predicted_gain_pct: float
    reference_before: float
    reference_after: float
    reference_gain_pct: float
    gap_pct: float
    displacement_l1: float
    displacement_max: float
    status: GainStatus


def _gain(before: float, after: float) -> float:
    """Relative gain, in percent.

    Parameters
    ----------
    before, after : float
        Values before and after.

    Returns
    -------
    float
        ``100 (after - before) / |before|``; ``nan`` when ``before`` is zero.
    """
    return 100.0 * (after - before) / abs(before) if abs(before) > _TINY else float("nan")


def _status(kind: ReferenceKind | None, predicted: float, measured: float) -> GainStatus:
    """What a reference says about a predicted gain.

    Parameters
    ----------
    kind : ReferenceKind or None
        Kind of the reference; ``None`` when it could not measure.
    predicted, measured : float
        Gains in percent.

    Returns
    -------
    GainStatus
        A physical reference confirms a gain of the same sign, strictly positive.
    """
    if kind is None:
        return "predicted_only"
    if kind == "closed_form":
        return "closed_form_only"
    return "confirmed" if measured > 0.0 and predicted > 0.0 else "contradicted"


def compare_before_after(
    surrogate: Surrogate,
    reference: Reference,
    pairs: Sequence[tuple[str, FloatVector, FloatVector, Orientation, Glazing | None]],
) -> tuple[BeforeAfter, ...]:
    """Measure, on the same plans, the gain predicted and the gain the reference sees.

    Parameters
    ----------
    surrogate : Surrogate
        Model the optimizer used.
    reference : Reference
        Independent reference.
    pairs : sequence of tuple
        ``(id, x_before, x_after, orientation, glazing)``. ``x_before`` is the plan the
        optimizer started from (typically the L1-legalized plan), ``x_after`` the plan
        it returned; both must have the same layout.

    Returns
    -------
    tuple of BeforeAfter
        One row per pair, in order.
    """
    rows = []
    for identifier, before, after, orientation, glazing in pairs:
        b, a = np.asarray(before, dtype=float), np.asarray(after, dtype=float)
        pb = point_prediction(surrogate, b, orientation, glazing=glazing)[0]
        pa = point_prediction(surrogate, a, orientation, glazing=glazing)[0]
        kind: ReferenceKind | None = reference.kind
        try:
            rb = reference.measure(b, orientation, glazing=glazing).value
            ra = reference.measure(a, orientation, glazing=glazing).value
        except ReferenceUnavailable:
            rb = ra = float("nan")
            kind = None
        predicted, measured = _gain(pb, pa), _gain(rb, ra)
        rows.append(
            BeforeAfter(
                id=identifier,
                predicted_before=pb,
                predicted_after=pa,
                predicted_gain_pct=predicted,
                reference_before=rb,
                reference_after=ra,
                reference_gain_pct=measured,
                gap_pct=predicted - measured,
                displacement_l1=float(np.abs(a - b).sum()),
                displacement_max=float(np.abs(a - b).max(initial=0.0)),
                status=_status(kind, predicted, measured),
            )
        )
    return tuple(rows)


@dataclass(frozen=True, slots=True)
class GainSummary:
    """Aggregate of :func:`compare_before_after`, and the word a paper may use.

    Attributes
    ----------
    n : int
        Rows.
    mean_predicted_gain_pct : float
        Mean surrogate gain.
    mean_reference_gain_pct : float
        Mean reference gain over the measured rows (``nan`` if none).
    n_measured, n_confirmed, n_contradicted : int
        Rows the reference measured; of them, confirmed and contradicted by a physical
        reference.
    median_displacement_l1 : float
        Median L1 displacement, in metres.
    claim : str
        ``"confirmed"`` only if every row was measured by a physical reference and the
        mean reference gain is positive; ``"predicted"`` otherwise.
    """

    n: int
    mean_predicted_gain_pct: float
    mean_reference_gain_pct: float
    n_measured: int
    n_confirmed: int
    n_contradicted: int
    median_displacement_l1: float
    claim: Literal["predicted", "confirmed"]


def _mean_or_nan(values: Sequence[float], *, median: bool = False) -> float:
    """Mean (or median) ignoring ``nan``; ``nan`` for an empty or all-``nan`` sample.

    Parameters
    ----------
    values : sequence of float
        Sample.
    median : bool, optional
        Return the median instead of the mean.

    Returns
    -------
    float
        The statistic.
    """
    finite = np.array(values, dtype=float)
    finite = finite[np.isfinite(finite)]
    if finite.size == 0:
        return float("nan")
    return float(np.median(finite) if median else np.mean(finite))


def summarize_gains(rows: Sequence[BeforeAfter]) -> GainSummary:
    """Aggregate before/after rows and decide the claim.

    Parameters
    ----------
    rows : sequence of BeforeAfter
        Output of :func:`compare_before_after`.

    Returns
    -------
    GainSummary
        Means, counts and claim.
    """
    measured = [r for r in rows if r.status != "predicted_only"]
    statuses = [r.status for r in rows]
    confirmed, contradicted = statuses.count("confirmed"), statuses.count("contradicted")
    reference_gain = _mean_or_nan([r.reference_gain_pct for r in measured])
    physical = bool(rows) and confirmed + contradicted == len(rows)
    claim: Literal["predicted", "confirmed"] = (
        "confirmed" if physical and reference_gain > 0.0 else "predicted"
    )
    return GainSummary(
        n=len(rows),
        mean_predicted_gain_pct=_mean_or_nan([r.predicted_gain_pct for r in rows]),
        mean_reference_gain_pct=reference_gain,
        n_measured=len(measured),
        n_confirmed=confirmed,
        n_contradicted=contradicted,
        median_displacement_l1=_mean_or_nan([r.displacement_l1 for r in rows], median=True),
        claim=claim,
    )
