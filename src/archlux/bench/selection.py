"""Conformal coverage before and after selection, on four disjoint sets of source plans.

The paper's B4 measured 89.8 % coverage on passive plans and 87.8 % on plans chosen by
Frank-Wolfe, with the calibration fitted on passive plans only. A coverage measured on
passive predictions says nothing, by itself, about plans an optimizer chose *because*
of those predictions (winner's curse). This protocol measures three procedures on the
same test set:

``passive``
    split conformal fitted on passive calibration plans, evaluated on passive test
    plans. Exchangeable: coverage ``>= 1 - alpha`` is guaranteed (marginally).
``passive_on_selected``
    the same calibrator, evaluated on the outputs of the frozen policy. **Not**
    guaranteed: the optimizer selected these points through the surrogate.
``policy``
    split conformal fitted on the outputs of the **frozen** policy run from a second,
    disjoint set of calibration plans, evaluated on the policy's outputs from the test
    plans. Guaranteed under one assumption, stated plainly: the source plans are
    exchangeable and the policy is a fixed function of its start plan, fitted on none
    of these calibration plans (its ``q_hat`` comes from the *passive* half).

Sets are drawn on **source plans**, never on variants
(:func:`archlux.data.provenance.split_by_group`): ``train`` fits a two-parameter affine
rescaling of the surrogate, ``validation`` decides whether to keep it, ``calibration``
(split in two halves, passive and policy) fits the quantiles, ``test`` measures. Each
calibration uses **one variant per source**, so its points are exchangeable; the test
set keeps every variant and its intervals resample the sources (cluster bootstrap).
"""

from __future__ import annotations

import csv
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, fields
from pathlib import Path

import numpy as np
from scipy import stats as scipy_stats

from archlux.bench.stats import cluster_bootstrap_proportion
from archlux.data.provenance import GroupedSplit, SampleId, check_no_group_leakage, split_by_group
from archlux.data.synthetic import two_room_vectors
from archlux.errors import InvariantViolation
from archlux.geom.polytope import decision_vector
from archlux.light.objective import Daylight
from archlux.light.protocol import Glazing, Surrogate
from archlux.seeds import derive
from archlux.types import Context, Indicator, Orientation, Plan, Regulation, Structure
from archlux.uq.conformal import ConformalCalibrator, minimal_n_conformal

__all__ = [
    "PROCEDURES",
    "AffineSurrogate",
    "CoverageRow",
    "ProtocolInfo",
    "Summary",
    "Variant",
    "below_target",
    "fit_affine",
    "guarantee",
    "legalize_policy",
    "run_selection_protocol",
    "summarize",
    "to_markdown",
    "two_room_variants",
    "write_rows",
]

PROCEDURES = ("passive", "passive_on_selected", "policy")
"""The three measured procedures, see the module docstring."""

Policy = Callable[[np.ndarray, Orientation], np.ndarray]
"""Frozen optimisation policy: start vector and azimuth -> selected vector."""

PolicyFactory = Callable[[Surrogate, float], Policy]
"""Builds the frozen policy from the frozen surrogate and its passive ``q_hat``."""


@dataclass(frozen=True, slots=True)
class AffineSurrogate:
    """``offset + scale * base``: a surrogate rescaled on the training set.

    Attributes
    ----------
    base : Surrogate
        Wrapped surrogate, unchanged.
    scale : float
        Multiplier of the value, the gradient and the uncertainty (in absolute value).
    offset : float
        Added to the value.
    """

    base: Surrogate
    scale: float
    offset: float

    @property
    def indicator(self) -> Indicator:
        """Indicator of the wrapped surrogate.

        Returns
        -------
        Indicator
            ``base.indicator``.
        """
        return self.base.indicator

    def evaluate(
        self, x: np.ndarray, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> float:
        """Rescaled value.

        Parameters
        ----------
        x : numpy.ndarray
            Decision vector.
        orientation : Orientation
            Azimuth.
        glazing : Glazing or None, optional
            Passed through.

        Returns
        -------
        float
            ``offset + scale * base.evaluate(x)``.
        """
        return self.offset + self.scale * self.base.evaluate(x, orientation, glazing=glazing)

    def gradient(
        self, x: np.ndarray, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> np.ndarray:
        """Rescaled gradient.

        Parameters
        ----------
        x : numpy.ndarray
            Decision vector.
        orientation : Orientation
            Azimuth.
        glazing : Glazing or None, optional
            Passed through.

        Returns
        -------
        numpy.ndarray
            ``scale * base.gradient(x)``.
        """
        return self.scale * np.asarray(self.base.gradient(x, orientation, glazing=glazing))

    def uncertainty(
        self, x: np.ndarray, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> float:
        """Rescaled uncertainty.

        Parameters
        ----------
        x : numpy.ndarray
            Decision vector.
        orientation : Orientation
            Azimuth.
        glazing : Glazing or None, optional
            Passed through.

        Returns
        -------
        float
            ``|scale| * base.uncertainty(x)``.
        """
        return abs(self.scale) * self.base.uncertainty(x, orientation, glazing=glazing)


def fit_affine(
    base: Surrogate,
    xs: Sequence[np.ndarray],
    orientations: Sequence[Orientation],
    truths: np.ndarray,
) -> AffineSurrogate:
    """Least-squares ``offset + scale * base`` on the training set.

    Parameters
    ----------
    base : Surrogate
        Surrogate to rescale.
    xs : Sequence[numpy.ndarray]
        Training vectors.
    orientations : Sequence[Orientation]
        Their azimuths.
    truths : numpy.ndarray
        Reference values (the frozen oracle).

    Returns
    -------
    AffineSurrogate
        The rescaled surrogate.

    Raises
    ------
    InvariantViolation
        Fewer than two points, or a non-positive slope: a negative scale would turn the
        gradient around, and the optimizer would walk away from daylight.
    """
    pred = np.array([base.evaluate(x, o) for x, o in zip(xs, orientations, strict=True)])
    if pred.size < 2:
        raise InvariantViolation(("need >= 2 training points",))
    scale, offset = np.polyfit(pred, np.asarray(truths, dtype=float), 1)
    if scale <= 0.0:
        raise InvariantViolation((f"non-positive affine slope {scale:.4g}",))
    return AffineSurrogate(base=base, scale=float(scale), offset=float(offset))


@dataclass(frozen=True, slots=True)
class Variant:
    """One sample: an identifier, a decision vector and an azimuth.

    Attributes
    ----------
    id : SampleId
        ``id.source`` is the split key.
    x : numpy.ndarray
        Decision vector.
    orientation : Orientation
        Azimuth of this variant.
    """

    id: SampleId
    x: np.ndarray
    orientation: Orientation


@dataclass(frozen=True, slots=True)
class CoverageRow:
    """One test interval and whether it covered the reference value.

    Attributes
    ----------
    repetition : int
        Repetition index (a fresh split per repetition).
    procedure : str
        One of :data:`PROCEDURES`.
    sample : str
        :attr:`SampleId.key` of the test variant.
    source : str
        Its source plan.
    azimuth : float
        Azimuth in degrees.
    sector : str
        ``N``, ``E``, ``S`` or ``W`` (quadrant centred on the cardinal direction).
    level : str
        Prediction tercile (``low``, ``mid``, ``high``), thresholds from calibration.
    sigma_level : str
        Tercile of ``sigma_hat``, or ``constant`` when ``sigma_hat`` does not vary.
    prediction, truth, lower, upper : float
        Surrogate value, oracle value, interval bounds.
    displacement : float
        ``||x_selected - x_start||_inf`` in metres (0 for passive rows).
    """

    repetition: int
    procedure: str
    sample: str
    source: str
    azimuth: float
    sector: str
    level: str
    sigma_level: str
    prediction: float
    truth: float
    lower: float
    upper: float
    displacement: float

    @property
    def covered(self) -> bool:
        """Whether the reference value falls inside the interval.

        Returns
        -------
        bool
            ``lower <= truth <= upper``.
        """
        return self.lower <= self.truth <= self.upper


@dataclass
class ProtocolInfo:
    """What a repetition used: set sizes, model choice, quantiles, guarantee statuses.

    Attributes
    ----------
    records : list of dict
        One dict per repetition (all values are strings or numbers, JSON-ready).
    """

    records: list[dict[str, object]] = field(default_factory=list)


def guarantee(procedure: str, n_calibration: int, alpha: float) -> str:
    """Say what a procedure guarantees, or why it guarantees nothing.

    Parameters
    ----------
    procedure : str
        One of :data:`PROCEDURES`.
    n_calibration : int
        Calibration size of the quantile it uses.
    alpha : float
        Target level.

    Returns
    -------
    str
        ``"guaranteed: ..."``, ``"not guaranteed: ..."`` or ``"refused: ..."``.

    Raises
    ------
    InvariantViolation
        Unknown procedure.
    """
    if procedure not in PROCEDURES:
        raise InvariantViolation((f"unknown procedure {procedure!r}",))
    if n_calibration < minimal_n_conformal(alpha):
        return f"refused: n={n_calibration} < {minimal_n_conformal(alpha)} for alpha={alpha}"
    if procedure == "passive_on_selected":
        return "not guaranteed: the optimizer selected these plans through the surrogate"
    if procedure == "policy":
        return "guaranteed: marginal, exchangeable sources, policy frozen before calibration"
    return "guaranteed: marginal, exchangeable sources"


def _sector(deg: float) -> str:
    """Cardinal quadrant of an azimuth.

    Parameters
    ----------
    deg : float
        Azimuth in degrees.

    Returns
    -------
    str
        ``N`` for ``[315, 45)``, then ``E``, ``S``, ``W``.
    """
    return "NESW"[int(((deg % 360.0) + 45.0) // 90.0) % 4]


def _tercile(value: float, cuts: tuple[float, float] | None) -> str:
    """Tercile label of ``value``.

    Parameters
    ----------
    value : float
        Value to classify.
    cuts : tuple of float or None
        The two tercile thresholds; ``None`` when the calibration values are constant.

    Returns
    -------
    str
        ``low``, ``mid``, ``high`` or ``constant``.
    """
    if cuts is None:
        return "constant"
    return "low" if value < cuts[0] else "mid" if value < cuts[1] else "high"


def _cuts(values: np.ndarray) -> tuple[float, float] | None:
    """Tercile thresholds, or ``None`` for constant values.

    Parameters
    ----------
    values : numpy.ndarray
        Calibration values.

    Returns
    -------
    tuple of float or None
        ``(q1/3, q2/3)``.
    """
    if float(np.ptp(values)) <= 1e-12 * max(1.0, float(np.max(np.abs(values)))):
        return None
    low, high = np.quantile(values, [1 / 3, 2 / 3])
    return float(low), float(high)


@dataclass(frozen=True, slots=True)
class _Columns:
    """Surrogate value, oracle value and ``sigma_hat`` of a list of points."""

    prediction: np.ndarray
    truth: np.ndarray
    sigma: np.ndarray


def _columns(
    model: Surrogate, oracle: Surrogate, points: Sequence[tuple[np.ndarray, Orientation]]
) -> _Columns:
    """Evaluate the surrogate, the oracle and ``sigma_hat`` on ``points``.

    Parameters
    ----------
    model : Surrogate
        Frozen surrogate.
    oracle : Surrogate
        Frozen reference.
    points : Sequence[tuple[numpy.ndarray, Orientation]]
        ``(x, orientation)`` pairs.

    Returns
    -------
    _Columns
        The three columns.
    """
    return _Columns(
        prediction=np.array([model.evaluate(x, o) for x, o in points]),
        truth=np.array([oracle.evaluate(x, o) for x, o in points]),
        sigma=np.array([model.uncertainty(x, o) for x, o in points]),
    )


def _calibrate(cols: _Columns, alpha: float) -> ConformalCalibrator:
    """Fit a split-conformal calibrator.

    Parameters
    ----------
    cols : _Columns
        Calibration columns.
    alpha : float
        Target level.

    Returns
    -------
    ConformalCalibrator
        Fitted on ``|y - y_hat| / sigma_hat``.
    """
    calibrator = ConformalCalibrator()
    calibrator.fit(cols.prediction, cols.truth, cols.sigma, alpha=alpha)
    return calibrator


def _one_per_source(variants: Sequence[Variant], seed: int) -> list[Variant]:
    """Keep one variant per source, drawn by a seeded hash.

    Parameters
    ----------
    variants : Sequence[Variant]
        Variants of several sources.
    seed : int
        Seed of the draw.

    Returns
    -------
    list of Variant
        One variant per source, sorted by source.
    """
    chosen: dict[str, Variant] = {}
    for v in sorted(variants, key=lambda v: (derive(seed, v.id.key), v.id.key)):
        chosen.setdefault(v.id.source, v)
    return [chosen[s] for s in sorted(chosen)]


def _members(variants: Sequence[Variant], split: GroupedSplit, name: str) -> list[Variant]:
    """Variants whose source is in set ``name``.

    Parameters
    ----------
    variants : Sequence[Variant]
        All variants.
    split : GroupedSplit
        Split on sources.
    name : str
        Set name.

    Returns
    -------
    list of Variant
        The members, in input order.
    """
    members = set(split.groups[name])
    return [v for v in variants if v.id.source in members]


def _choose_model(
    base: Surrogate, oracle: Surrogate, train: Sequence[Variant], validation: Sequence[Variant]
) -> tuple[Surrogate, dict[str, object]]:
    """Fit the affine rescaling on ``train``; keep it only if it wins on ``validation``.

    Parameters
    ----------
    base : Surrogate
        Surrogate before training.
    oracle : Surrogate
        Frozen reference.
    train, validation : Sequence[Variant]
        Training and validation variants.

    Returns
    -------
    tuple
        ``(frozen surrogate, record)`` with the validation MAEs and the choice.
    """
    truths = np.array([oracle.evaluate(v.x, v.orientation) for v in train])
    fitted = fit_affine(base, [v.x for v in train], [v.orientation for v in train], truths)
    points = [(v.x, v.orientation) for v in validation]
    mae = {
        name: float(np.mean(np.abs(c.prediction - c.truth)))
        for name, c in (
            ("raw", _columns(base, oracle, points)),
            ("affine", _columns(fitted, oracle, points)),
        )
    }
    model: Surrogate = fitted if mae["affine"] < mae["raw"] else base
    record: dict[str, object] = {
        "validation_mae_raw": mae["raw"],
        "validation_mae_affine": mae["affine"],
        "model": "affine" if model is fitted else "raw",
        "affine_scale": fitted.scale,
        "affine_offset": fitted.offset,
    }
    return model, record


def _rows(
    repetition: int,
    procedure: str,
    tests: Sequence[Variant],
    points: Sequence[tuple[np.ndarray, Orientation]],
    calibrator: ConformalCalibrator,
    cols: _Columns,
    cuts: tuple[tuple[float, float] | None, tuple[float, float] | None],
) -> list[CoverageRow]:
    """Bound every test point and record the outcome.

    Parameters
    ----------
    repetition : int
        Repetition index.
    procedure : str
        One of :data:`PROCEDURES`.
    tests : Sequence[Variant]
        Test start variants (identity, start vector, azimuth).
    points : Sequence[tuple[numpy.ndarray, Orientation]]
        Evaluated points (the start vectors, or the policy's outputs).
    calibrator : ConformalCalibrator
        Calibrator of the procedure.
    cols : _Columns
        Columns of ``points``.
    cuts : tuple
        Tercile thresholds of the prediction and of ``sigma_hat``.

    Returns
    -------
    list of CoverageRow
        One row per test point.
    """
    rows = []
    for i, v in enumerate(tests):
        margin = calibrator.q * float(cols.sigma[i])
        rows.append(
            CoverageRow(
                repetition=repetition,
                procedure=procedure,
                sample=v.id.key,
                source=v.id.source,
                azimuth=v.orientation.deg,
                sector=_sector(v.orientation.deg),
                level=_tercile(float(cols.prediction[i]), cuts[0]),
                sigma_level=_tercile(float(cols.sigma[i]), cuts[1]),
                prediction=float(cols.prediction[i]),
                truth=float(cols.truth[i]),
                lower=float(cols.prediction[i]) - margin,
                upper=float(cols.prediction[i]) + margin,
                displacement=float(np.max(np.abs(points[i][0] - v.x))),
            )
        )
    return rows


def _points(variants: Sequence[Variant]) -> list[tuple[np.ndarray, Orientation]]:
    """``(x, orientation)`` of each variant.

    Parameters
    ----------
    variants : Sequence[Variant]
        Variants.

    Returns
    -------
    list of tuple
        Their start points.
    """
    return [(v.x, v.orientation) for v in variants]


def _chosen(policy: Policy, variants: Sequence[Variant]) -> list[tuple[np.ndarray, Orientation]]:
    """``(policy(x), orientation)`` of each variant.

    Parameters
    ----------
    policy : Policy
        Frozen policy.
    variants : Sequence[Variant]
        Start variants.

    Returns
    -------
    list of tuple
        The points the policy selected.
    """
    return [(policy(v.x, v.orientation), v.orientation) for v in variants]


def _sets(variants: Sequence[Variant], split: GroupedSplit) -> dict[str, list[Variant]]:
    """The five sets of one repetition, checked for leakage.

    Both calibration halves keep **one variant per source**: the conformal guarantee
    needs exchangeable calibration points, and four azimuths of one plan are not.

    Parameters
    ----------
    variants : Sequence[Variant]
        All variants.
    split : GroupedSplit
        Split on sources.

    Returns
    -------
    dict of str to list of Variant
        ``train``, ``validation``, ``calibration_passive``, ``calibration_policy``,
        ``test`` (every variant of the test sources).

    Raises
    ------
    InvariantViolation
        A source reaches two sets (cannot happen by construction; checked anyway).
    """
    calibration = _one_per_source(
        _members(variants, split, "calibration"), derive(split.seed, "one-per-source")
    )
    half = len(calibration) // 2
    sets = {
        "train": _members(variants, split, "train"),
        "validation": _members(variants, split, "validation"),
        "calibration_passive": calibration[:half],
        "calibration_policy": calibration[half:],
        "test": _members(variants, split, "test"),
    }
    check_no_group_leakage({name: [v.id for v in members] for name, members in sets.items()})
    return sets


def _repetition(
    repetition: int,
    variants: Sequence[Variant],
    split: GroupedSplit,
    base: Surrogate,
    oracle: Surrogate,
    make_policy: PolicyFactory,
    alpha: float,
) -> tuple[list[CoverageRow], dict[str, object]]:
    """Run the three procedures once, on one split.

    Parameters
    ----------
    repetition : int
        Repetition index.
    variants : Sequence[Variant]
        All variants.
    split : GroupedSplit
        This repetition's split on sources.
    base : Surrogate
        Surrogate before training.
    oracle : Surrogate
        Frozen reference.
    make_policy : PolicyFactory
        Builds the frozen policy.
    alpha : float
        Target level.

    Returns
    -------
    tuple
        ``(rows, record)``.
    """
    sets = _sets(variants, split)
    model, record = _choose_model(base, oracle, sets["train"], sets["validation"])
    cal_passive, cal_policy, tests = (
        sets["calibration_passive"],
        sets["calibration_policy"],
        sets["test"],
    )
    passive_cols = _columns(model, oracle, _points(cal_passive))
    passive = _calibrate(passive_cols, alpha)
    policy = make_policy(model, passive.q)  # frozen: knows nothing of cal_policy nor test
    policy_cal = _calibrate(_columns(model, oracle, _chosen(policy, cal_policy)), alpha)
    cuts = (_cuts(passive_cols.prediction), _cuts(passive_cols.sigma))
    start, chosen = _points(tests), _chosen(policy, tests)
    start_cols, chosen_cols = _columns(model, oracle, start), _columns(model, oracle, chosen)
    rows = [
        *_rows(repetition, "passive", tests, start, passive, start_cols, cuts),
        *_rows(repetition, "passive_on_selected", tests, chosen, passive, chosen_cols, cuts),
        *_rows(repetition, "policy", tests, chosen, policy_cal, chosen_cols, cuts),
    ]
    record.update(
        repetition=repetition,
        split_seed=split.seed,
        **{f"n_sources_{k}": n for k, n in split.counts().items()},
        n_calibration_passive=passive.n,
        n_calibration_policy=policy_cal.n,
        n_test_variants=len(tests),
        q_passive=passive.q,
        q_policy=policy_cal.q,
        guarantee_passive=guarantee("passive", passive.n, alpha),
        guarantee_passive_on_selected=guarantee("passive_on_selected", passive.n, alpha),
        guarantee_policy=guarantee("policy", policy_cal.n, alpha),
    )
    return rows, record


def run_selection_protocol(
    variants: Sequence[Variant],
    *,
    base: Surrogate,
    oracle: Surrogate,
    make_policy: PolicyFactory,
    seed: int,
    repetitions: int = 10,
    alpha: float = 0.10,
    fractions: Sequence[float] = (0.4, 0.1, 0.25, 0.25),
) -> tuple[list[CoverageRow], ProtocolInfo]:
    """Measure coverage before and after selection, ``repetitions`` times.

    Parameters
    ----------
    variants : Sequence[Variant]
        The population; several variants may share a source plan.
    base : Surrogate
        Surrogate before training (rescaled on ``train``, frozen afterwards).
    oracle : Surrogate
        Frozen reference the intervals must cover.
    make_policy : PolicyFactory
        ``(frozen surrogate, passive q_hat) -> policy``. For archlux: legalize with a
        pessimistic :class:`~archlux.light.objective.Daylight` objective (injected:
        ``bench`` never imports ``api``).
    seed : int
        Root seed; repetition ``r`` splits with ``derive(seed, f"rep/{r}")``.
    repetitions : int, optional
        Number of fresh splits.
    alpha : float, optional
        Target level.
    fractions : Sequence[float], optional
        Fractions of sources in train / validation / calibration / test.

    Returns
    -------
    tuple
        ``(rows, info)``: one row per test point and procedure, and what each
        repetition used.

    Raises
    ------
    InvariantViolation
        ``repetitions < 1``, or a calibration half below the conformal minimum.
    """
    if repetitions < 1:
        raise InvariantViolation(("repetitions must be >= 1",))
    sources = [v.id.source for v in variants]
    rows: list[CoverageRow] = []
    info = ProtocolInfo()
    for r in range(repetitions):
        split = split_by_group(sources, seed=derive(seed, f"rep/{r}"), fractions=fractions)
        new_rows, record = _repetition(r, variants, split, base, oracle, make_policy, alpha)
        rows.extend(new_rows)
        info.records.append(record)
    return rows, info


@dataclass(frozen=True, slots=True)
class Summary:
    """Coverage of one stratum of one procedure.

    Attributes
    ----------
    procedure : str
        One of :data:`PROCEDURES`.
    stratum : str
        ``all`` or ``key=value``.
    n : int
        Test intervals.
    n_sources : int
        Distinct ``(repetition, source)`` clusters.
    coverage : float
        Share of intervals covering the reference.
    low, high : float
        Cluster-bootstrap 95 % interval (clusters: repetition x source).
    mean_width : float
        Mean interval width.
    mean_over_repetitions : float
        Mean of the per-repetition coverages.
    min_over_repetitions : float
        Worst repetition.
    rep_low, rep_high : float
        Student 95 % interval of the mean over repetitions (``nan`` with one
        repetition). The conformal guarantee is **marginal over the calibration draw**:
        the repetitions, each with its own calibration, are its independent units, and
        the cluster interval above (conditional on the calibrations) is too narrow to
        test it.
    """

    procedure: str
    stratum: str
    n: int
    n_sources: int
    coverage: float
    low: float
    high: float
    mean_width: float
    mean_over_repetitions: float
    min_over_repetitions: float
    rep_low: float
    rep_high: float


def _summary(procedure: str, stratum: str, rows: Sequence[CoverageRow], seed: int) -> Summary:
    """Summarize one group of rows.

    Parameters
    ----------
    procedure : str
        Procedure of the rows.
    stratum : str
        Stratum label.
    rows : Sequence[CoverageRow]
        Rows of the group, non-empty.
    seed : int
        Bootstrap seed.

    Returns
    -------
    Summary
        Coverage, cluster interval, width, per-repetition spread.
    """
    covered = [r.covered for r in rows]
    clusters = [f"{r.repetition}:{r.source}" for r in rows]
    ci = cluster_bootstrap_proportion(covered, clusters, seed=seed)
    per_rep: dict[int, list[bool]] = {}
    for r in rows:
        per_rep.setdefault(r.repetition, []).append(r.covered)
    rates = [float(np.mean(v)) for v in per_rep.values()]
    rep_low = rep_high = math.nan
    if len(rates) > 1:
        half = scipy_stats.t.ppf(0.975, len(rates) - 1) * np.std(rates, ddof=1)
        rep_low = float(np.mean(rates) - half / math.sqrt(len(rates)))
        rep_high = float(np.mean(rates) + half / math.sqrt(len(rates)))
    return Summary(
        procedure=procedure,
        stratum=stratum,
        n=len(rows),
        n_sources=len(set(clusters)),
        coverage=ci.value,
        low=ci.low,
        high=ci.high,
        mean_width=float(np.mean([r.upper - r.lower for r in rows])),
        mean_over_repetitions=float(np.mean(rates)),
        min_over_repetitions=float(np.min(rates)),
        rep_low=rep_low,
        rep_high=rep_high,
    )


def summarize(
    rows: Sequence[CoverageRow],
    *,
    seed: int,
    keys: Sequence[str] = ("sector", "level", "sigma_level"),
) -> list[Summary]:
    """Coverage per procedure, overall then per stratum.

    Parameters
    ----------
    rows : Sequence[CoverageRow]
        Output of :func:`run_selection_protocol`.
    seed : int
        Bootstrap seed.
    keys : Sequence[str], optional
        Row attributes to stratify on.

    Returns
    -------
    list of Summary
        ``all`` first, then each ``key=value`` in sorted order, for each procedure.
    """
    out = []
    for procedure in PROCEDURES:
        mine = [r for r in rows if r.procedure == procedure]
        if not mine:
            continue
        out.append(_summary(procedure, "all", mine, seed))
        for key in keys:
            for value in sorted({str(getattr(r, key)) for r in mine}):
                group = [r for r in mine if str(getattr(r, key)) == value]
                out.append(_summary(procedure, f"{key}={value}", group, seed))
    return out


def below_target(summary: Summary, alpha: float) -> bool:
    """Whether the repetition-level interval lies entirely below ``1 - alpha``.

    The behaviour when the guarantee does not hold: a procedure or stratum flagged here
    must not be reported with the nominal coverage. A stratum is never *guaranteed*
    (the guarantee is marginal, not conditional on orientation or level); the flag says
    where the marginal coverage visibly fails to carry over.

    Parameters
    ----------
    summary : Summary
        One stratum.
    alpha : float
        Target level.

    Returns
    -------
    bool
        ``summary.rep_high < 1 - alpha``; ``False`` with a single repetition.
    """
    return not math.isnan(summary.rep_high) and summary.rep_high < 1.0 - alpha


def two_room_variants(n_sources: int, *, seed: int, n_azimuths: int = 4) -> list[Variant]:
    """The synthetic population: ``n_sources`` two-room plans, each at ``n_azimuths``.

    The azimuths of one source are evenly spaced from a random start, so each source
    contributes one variant per sector when ``n_azimuths = 4``.

    Parameters
    ----------
    n_sources : int
        Number of source plans.
    seed : int
        Seed of :func:`archlux.data.synthetic.two_room_vectors`.
    n_azimuths : int, optional
        Variants per source.

    Returns
    -------
    list of Variant
        ``SampleId(source="two-0000", variant="az0")`` and so on.
    """
    xs, starts = two_room_vectors(n_sources, seed=seed)
    step = 360.0 / n_azimuths
    return [
        Variant(
            SampleId(f"two-{i:04d}", variant=f"az{k}"), x, Orientation((o.deg + step * k) % 360)
        )
        for i, (x, o) in enumerate(zip(xs, starts, strict=True))
        for k in range(n_azimuths)
    ]


def legalize_policy(
    legalize: Callable[..., Plan],
    to_plan: Callable[[np.ndarray], Plan],
    outline: tuple[tuple[float, float], ...],
    regulation: Regulation,
) -> PolicyFactory:
    """Policy factory for archlux itself: legalize with the pessimistic daylight objective.

    Parameters
    ----------
    legalize : Callable[..., Plan]
        :func:`archlux.legalize`, injected (``bench`` never imports ``api``).
    to_plan : Callable[[numpy.ndarray], Plan]
        Decision vector -> plan, e.g. :func:`archlux.data.synthetic.two_room_plan`.
    outline : tuple of tuple of float
        Outline of the plans.
    regulation : Regulation
        Regulation of the context.

    Returns
    -------
    PolicyFactory
        ``(frozen surrogate, q_hat) -> policy``.
    """

    def factory(model: Surrogate, q_hat: float) -> Policy:
        """Freeze the objective on ``model`` and ``q_hat``.

        Parameters
        ----------
        model : Surrogate
            Frozen surrogate.
        q_hat : float
            Passive conformal quantile.

        Returns
        -------
        Policy
            The frozen policy.
        """
        objective = Daylight(model, q_hat=q_hat)

        def policy(x: np.ndarray, orientation: Orientation) -> np.ndarray:
            """Legalize ``x`` at ``orientation`` with the frozen objective.

            Parameters
            ----------
            x : numpy.ndarray
                Start vector.
            orientation : Orientation
                Azimuth.

            Returns
            -------
            numpy.ndarray
                Decision vector of the legalized plan.
            """
            context = Context(
                structure=Structure(()),
                orientation=orientation,
                outline=outline,
                regulation=regulation,
            )
            return decision_vector(legalize(to_plan(x), context, objective=objective))

        return policy

    return factory


def write_rows(path: Path, rows: Sequence[CoverageRow]) -> None:
    """Write the raw rows as CSV, one interval per line.

    Parameters
    ----------
    path : Path
        Output CSV.
    rows : Sequence[CoverageRow]
        Output of :func:`run_selection_protocol`.
    """
    names = [f.name for f in fields(CoverageRow)]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow([*names, "covered"])
        for r in rows:
            values = [getattr(r, n) for n in names]
            cells = [f"{v:.6f}" if isinstance(v, float) else v for v in values]
            writer.writerow([*cells, r.covered])


def to_markdown(summaries: Sequence[Summary], info: ProtocolInfo, *, alpha: float) -> str:
    """Render the summaries and the guarantee statuses as Markdown.

    Parameters
    ----------
    summaries : Sequence[Summary]
        Output of :func:`summarize`.
    info : ProtocolInfo
        What each repetition used.
    alpha : float
        Target level.

    Returns
    -------
    str
        One table, strata included, then the status of each guarantee.
    """
    first = info.records[0]
    lines = [
        "| procedure | stratum | n | clusters | coverage | cluster 95 % CI | "
        "mean of reps [95 % CI over reps] | worst rep | mean width | below target |",
        "|---|---|--:|--:|--:|:--:|:--:|--:|--:|:--:|",
    ]
    for s in summaries:
        flag = "**yes**" if below_target(s, alpha) else "no"
        lines.append(
            f"| {s.procedure} | {s.stratum} | {s.n} | {s.n_sources} | "
            f"{100 * s.coverage:.1f} % | [{100 * s.low:.1f} ; {100 * s.high:.1f}] | "
            f"{100 * s.mean_over_repetitions:.1f} % [{100 * s.rep_low:.1f} ; "
            f"{100 * s.rep_high:.1f}] | {100 * s.min_over_repetitions:.1f} % | "
            f"{s.mean_width:.3f} | {flag} |"
        )
    status = [f"- `{p}`: {first[f'guarantee_{p}']}" for p in PROCEDURES]
    return "\n".join([*lines, "", "Guarantee of each procedure:", "", *status, ""])
