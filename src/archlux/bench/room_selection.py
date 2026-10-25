"""Conformal coverage per **room**, before and after selection, broken down by room type.

:mod:`archlux.bench.selection` measures coverage per plan, on two-room plans that carry no
room type: "coverage by room type" cannot be read from it. Daylight is a per-room quantity
(:class:`~archlux.light.protocol.PerRoomSurrogate`), so this module repeats the same three
procedures (``passive``, ``passive_on_selected``, ``policy``) with the **room** as the unit
of the interval, on typed four-room plans (:func:`four_room_variants`).

Exchangeability, stated plainly. The four rooms of one plan, and the four azimuths of one
source, are not exchangeable. Each calibration half therefore keeps **one variant and one
room per source** (seeded draw); the test set keeps every variant and every room, and its
intervals resample whole sources (cluster bootstrap, clusters ``repetition x source``).

The policy selects plans through the **plan-level** objective
``sum(rooms) - q_hat * sigma``; the intervals are then put on each room of the selected
plan. The per-room surrogate is an affine rescaling of the analytic surrogate fitted on
the train rooms (one scale, one offset for every room); its ``sigma_hat`` is constant, so
the scores are plain absolute residuals up to that constant.

The reference is the frozen closed-form oracle, not a simulation: every coverage below is
a coverage of that oracle's value.
"""

from __future__ import annotations

import csv
from collections.abc import Sequence
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Protocol, runtime_checkable

import numpy as np

from archlux.bench.selection import (
    CoverageRow,
    PolicyFactory,
    ProtocolInfo,
    Variant,
    guarantee,
)
from archlux.bench.selection import _cuts as cuts_of
from archlux.bench.selection import _sector as sector_of
from archlux.bench.selection import _sets as sets_of
from archlux.bench.selection import _tercile as tercile_of
from archlux.data.provenance import SampleId, split_by_group
from archlux.errors import InvariantViolation
from archlux.light.protocol import Glazing, PerRoomSurrogate, Surrogate
from archlux.seeds import derive
from archlux.types import Indicator, Orientation, Plan, Room
from archlux.uq.conformal import ConformalCalibrator

__all__ = [
    "FOUR_ROOM_OUTLINE",
    "ROOM_TYPES",
    "RoomAffineSurrogate",
    "RoomCoverageRow",
    "RoomSurrogate",
    "RoomVariant",
    "four_room_plan",
    "four_room_variants",
    "run_room_protocol",
    "write_room_rows",
]

FOUR_ROOM_OUTLINE = ((0.0, 0.0), (12.0, 0.0), (12.0, 9.0), (0.0, 9.0))
"""Outline of the :func:`four_room_variants` family, in metres."""

ROOM_TYPES = ("living_room", "bedroom", "kitchen", "bathroom")
"""Room types drawn, one of each per plan."""

ROOM_IDS = ("ne", "nw", "se", "sw")
"""Room identifiers in decision-vector order (sorted)."""


@runtime_checkable
class RoomSurrogate(Surrogate, PerRoomSurrogate, Protocol):
    """A :class:`Surrogate` that also exposes its per-room values."""


@dataclass(frozen=True, slots=True)
class RoomVariant(Variant):
    """A :class:`~archlux.bench.selection.Variant` whose rooms carry a type.

    Attributes
    ----------
    room_types : tuple of str
        Type of each room, in decision-vector order (:data:`ROOM_IDS`).
    """

    room_types: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RoomCoverageRow(CoverageRow):
    """One room interval; :attr:`sample` is ``<variant key>/<room id>``.

    Attributes
    ----------
    room_type : str
        Type of the room.
    """

    room_type: str = "unknown"


@dataclass(frozen=True, slots=True)
class RoomAffineSurrogate:
    """``offset + scale * base`` per room; the plan value is the sum of the rooms.

    Attributes
    ----------
    base : RoomSurrogate
        Wrapped surrogate (its plan value is the sum of its rooms).
    scale : float
        Multiplier of every room value, of the gradient and of the uncertainty.
    offset : float
        Added to every room value.
    """

    base: RoomSurrogate
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

    def evaluate_rooms(
        self, x: np.ndarray, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> np.ndarray:
        """Rescaled value of every room.

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
            One value per room.
        """
        rooms = np.asarray(self.base.evaluate_rooms(x, orientation, glazing=glazing))
        return self.offset + self.scale * rooms

    def evaluate(
        self, x: np.ndarray, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> float:
        """Sum of the rescaled rooms.

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
            The plan value.
        """
        return float(np.sum(self.evaluate_rooms(x, orientation, glazing=glazing)))

    def gradient(
        self, x: np.ndarray, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> np.ndarray:
        """Gradient of the plan value: ``scale`` times the base gradient.

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
            Same dimension as ``x`` (the offsets are constants).
        """
        return self.scale * np.asarray(self.base.gradient(x, orientation, glazing=glazing))

    def uncertainty(
        self, x: np.ndarray, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> float:
        """Rescaled uncertainty of the base.

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
        return abs(self.scale) * float(self.base.uncertainty(x, orientation, glazing=glazing))


def four_room_plan(x: np.ndarray, room_types: Sequence[str] = ROOM_TYPES) -> Plan:
    """The plan of a four-room vector (rooms in :data:`ROOM_IDS` order).

    Parameters
    ----------
    x : numpy.ndarray
        Vector of dimension 16, ``(x, y, w, h)`` per room.
    room_types : sequence of str, optional
        Type of each room, same order.

    Returns
    -------
    Plan
        Four rooms, no wall, outline :data:`FOUR_ROOM_OUTLINE`.
    """
    rooms = tuple(
        Room(
            id=rid,
            type=kind,
            x=float(x[4 * k]),
            y=float(x[4 * k + 1]),
            w=float(x[4 * k + 2]),
            h=float(x[4 * k + 3]),
        )
        for k, (rid, kind) in enumerate(zip(ROOM_IDS, room_types, strict=True))
    )
    return Plan(rooms, (), (), FOUR_ROOM_OUTLINE)


def four_room_variants(
    n_sources: int, *, seed: int, n_azimuths: int = 4, prefix: str = "four"
) -> list[RoomVariant]:
    """Typed 2x2 tilings of a 12 x 9 m outline, each at ``n_azimuths`` azimuths.

    The vertical cut is uniform in ``[4, 8]`` m, the horizontal one in ``[3, 6]`` m, and
    the four types of :data:`ROOM_TYPES` are dealt to the four rooms by a random
    permutation. Unlike :func:`archlux.data.synthetic.generate_corpus` (90 plans on a
    grid of cuts), the cuts are continuous, so any number of distinct sources exists.

    Parameters
    ----------
    n_sources : int
        Number of source plans.
    seed : int
        Mandatory seed.
    n_azimuths : int, optional
        Variants per source, evenly spaced from a random start.
    prefix : str, optional
        Prefix of the source ids; give disjoint pools disjoint prefixes.

    Returns
    -------
    list of RoomVariant
        ``SampleId(source="four-0000", variant="az0")`` and so on.

    Raises
    ------
    InvariantViolation
        ``n_sources`` negative or ``n_azimuths < 1``.
    """
    if n_sources < 0 or n_azimuths < 1:
        raise InvariantViolation(("need n_sources >= 0 and n_azimuths >= 1",))
    rng = np.random.default_rng(derive(seed, f"four_room_variants/{prefix}"))
    step = 360.0 / n_azimuths
    out: list[RoomVariant] = []
    for i in range(n_sources):
        cx, cy = float(rng.uniform(4.0, 8.0)), float(rng.uniform(3.0, 6.0))
        start = float(rng.uniform(0.0, 360.0))
        kinds = tuple(ROOM_TYPES[j] for j in rng.permutation(len(ROOM_TYPES)))
        boxes = {
            "ne": (cx, cy, 12.0 - cx, 9.0 - cy),
            "nw": (0.0, cy, cx, 9.0 - cy),
            "se": (cx, 0.0, 12.0 - cx, cy),
            "sw": (0.0, 0.0, cx, cy),
        }
        x = np.array([v for rid in ROOM_IDS for v in boxes[rid]], dtype=float)
        out.extend(
            RoomVariant(
                SampleId(f"{prefix}-{i:04d}", variant=f"az{k}"),
                x,
                Orientation((start + step * k) % 360.0),
                room_types=kinds,
            )
            for k in range(n_azimuths)
        )
    return out


@dataclass(frozen=True, slots=True)
class _RoomColumns:
    """Per-room prediction, truth and ``sigma_hat`` of a list of plans, flattened."""

    prediction: np.ndarray
    truth: np.ndarray
    sigma: np.ndarray

    def pick(self, index: Sequence[int]) -> _RoomColumns:
        """Keep the rooms at ``index``.

        Parameters
        ----------
        index : sequence of int
            Flat room indices.

        Returns
        -------
        _RoomColumns
            The selected rooms.
        """
        i = np.asarray(index, dtype=int)
        return _RoomColumns(self.prediction[i], self.truth[i], self.sigma[i])


def _room_columns(
    model: RoomAffineSurrogate,
    oracle: RoomSurrogate,
    points: Sequence[tuple[np.ndarray, Orientation]],
) -> _RoomColumns:
    """Evaluate every room of every point.

    Parameters
    ----------
    model : RoomAffineSurrogate
        Frozen surrogate.
    oracle : RoomSurrogate
        Frozen reference.
    points : sequence of tuple
        ``(x, orientation)`` pairs.

    Returns
    -------
    _RoomColumns
        ``len(points) * rooms`` entries, plan-major.
    """
    pred: list[float] = []
    truth: list[float] = []
    sigma: list[float] = []
    for x, o in points:
        p = model.evaluate_rooms(x, o)
        pred.extend(p)
        truth.extend(np.asarray(oracle.evaluate_rooms(x, o)))
        sigma.extend([model.uncertainty(x, o)] * len(p))
    return _RoomColumns(np.array(pred), np.array(truth), np.array(sigma))


def _fit_rooms(
    base: RoomSurrogate, oracle: RoomSurrogate, train: Sequence[Variant]
) -> RoomAffineSurrogate:
    """Least-squares ``room_oracle ~ offset + scale * room_base`` on the train rooms.

    Parameters
    ----------
    base : RoomSurrogate
        Surrogate before training.
    oracle : RoomSurrogate
        Reference.
    train : sequence of Variant
        Training variants.

    Returns
    -------
    RoomAffineSurrogate
        The rescaled surrogate.

    Raises
    ------
    InvariantViolation
        Non-positive slope (it would turn the gradient around).
    """
    raw = np.concatenate([np.asarray(base.evaluate_rooms(v.x, v.orientation)) for v in train])
    ys = np.concatenate([np.asarray(oracle.evaluate_rooms(v.x, v.orientation)) for v in train])
    scale, offset = np.polyfit(raw, ys, 1)
    if scale <= 0.0:
        raise InvariantViolation((f"non-positive affine slope {scale:.4g}",))
    return RoomAffineSurrogate(base=base, scale=float(scale), offset=float(offset))


def _one_room(variants: Sequence[Variant], n_rooms: int, seed: int) -> list[int]:
    """One flat room index per variant (one variant per source already), by seeded draw.

    Parameters
    ----------
    variants : sequence of Variant
        One variant per source.
    n_rooms : int
        Rooms per plan.
    seed : int
        Seed.

    Returns
    -------
    list of int
        Flat indices into the plan-major room columns.
    """
    return [k * n_rooms + derive(seed, v.id.key) % n_rooms for k, v in enumerate(variants)]


def _calibrate(cols: _RoomColumns, alpha: float) -> ConformalCalibrator:
    """Split conformal on ``|y - y_hat| / sigma_hat``.

    Parameters
    ----------
    cols : _RoomColumns
        Calibration rooms.
    alpha : float
        Target level.

    Returns
    -------
    ConformalCalibrator
        Fitted calibrator.
    """
    calibrator = ConformalCalibrator()
    calibrator.fit(cols.prediction, cols.truth, cols.sigma, alpha=alpha)
    return calibrator


def _room_rows(
    repetition: int,
    procedure: str,
    tests: Sequence[RoomVariant],
    points: Sequence[tuple[np.ndarray, Orientation]],
    calibrator: ConformalCalibrator,
    cols: _RoomColumns,
    cuts: tuple[float, float] | None,
) -> list[RoomCoverageRow]:
    """One row per room of every test point.

    Parameters
    ----------
    repetition : int
        Repetition index.
    procedure : str
        Procedure name.
    tests : sequence of RoomVariant
        Test start variants.
    points : sequence of tuple
        Evaluated points (starts or the policy's outputs).
    calibrator : ConformalCalibrator
        Calibrator of the procedure.
    cols : _RoomColumns
        Room columns of ``points``.
    cuts : tuple or None
        Tercile thresholds of the room prediction.

    Returns
    -------
    list of RoomCoverageRow
        The rows.
    """
    rows = []
    n = len(ROOM_IDS)
    for i, v in enumerate(tests):
        moved = float(np.max(np.abs(points[i][0] - v.x)))
        for r, rid in enumerate(ROOM_IDS):
            j = i * n + r
            pred, margin = float(cols.prediction[j]), calibrator.q * float(cols.sigma[j])
            rows.append(
                RoomCoverageRow(
                    repetition=repetition,
                    procedure=procedure,
                    sample=f"{v.id.key}/{rid}",
                    source=v.id.source,
                    azimuth=v.orientation.deg,
                    sector=sector_of(v.orientation.deg),
                    level=tercile_of(pred, cuts),
                    sigma_level="constant",
                    prediction=pred,
                    truth=float(cols.truth[j]),
                    lower=pred - margin,
                    upper=pred + margin,
                    displacement=moved,
                    room_type=v.room_types[r],
                )
            )
    return rows


def _room_repetition(
    repetition: int,
    variants: Sequence[RoomVariant],
    seed: int,
    base: RoomSurrogate,
    oracle: RoomSurrogate,
    make_policy: PolicyFactory,
    alpha: float,
    fractions: Sequence[float],
) -> tuple[list[RoomCoverageRow], dict[str, object]]:
    """Run the three procedures once, per room.

    Parameters
    ----------
    repetition : int
        Repetition index.
    variants : sequence of RoomVariant
        Population.
    seed : int
        Split seed of this repetition.
    base, oracle : RoomSurrogate
        Surrogate before training, frozen reference.
    make_policy : PolicyFactory
        Builds the frozen policy.
    alpha : float
        Target level.
    fractions : sequence of float
        Source fractions train / validation / calibration / test.

    Returns
    -------
    tuple
        ``(rows, record)``.
    """
    split = split_by_group([v.id.source for v in variants], seed=seed, fractions=fractions)
    sets = sets_of(variants, split)
    model = _fit_rooms(base, oracle, sets["train"])
    validation = _room_columns(model, oracle, [(v.x, v.orientation) for v in sets["validation"]])
    cal_passive = sets["calibration_passive"]
    cal_policy = sets["calibration_policy"]
    tests = [v for v in variants if v.id.source in set(split.groups["test"])]
    n = len(ROOM_IDS)
    passive_cols = _room_columns(model, oracle, [(v.x, v.orientation) for v in cal_passive])
    passive_cols = passive_cols.pick(_one_room(cal_passive, n, derive(seed, "room/passive")))
    passive = _calibrate(passive_cols, alpha)
    policy = make_policy(model, passive.q)
    chosen_cal = [(policy(v.x, v.orientation), v.orientation) for v in cal_policy]
    policy_cols = _room_columns(model, oracle, chosen_cal)
    policy_cols = policy_cols.pick(_one_room(cal_policy, n, derive(seed, "room/policy")))
    policy_cal = _calibrate(policy_cols, alpha)
    start = [(v.x, v.orientation) for v in tests]
    chosen = [(policy(v.x, v.orientation), v.orientation) for v in tests]
    start_cols, chosen_cols = (
        _room_columns(model, oracle, start),
        _room_columns(model, oracle, chosen),
    )
    cuts = cuts_of(passive_cols.prediction)
    rows = [
        *_room_rows(repetition, "passive", tests, start, passive, start_cols, cuts),
        *_room_rows(repetition, "passive_on_selected", tests, chosen, passive, chosen_cols, cuts),
        *_room_rows(repetition, "policy", tests, chosen, policy_cal, chosen_cols, cuts),
    ]
    record: dict[str, object] = {
        "repetition": repetition,
        "split_seed": seed,
        **{f"n_sources_{k}": c for k, c in split.counts().items()},
        "affine_scale": model.scale,
        "affine_offset": model.offset,
        "validation_room_mae": float(np.mean(np.abs(validation.prediction - validation.truth))),
        "n_calibration_passive": passive.n,
        "n_calibration_policy": policy_cal.n,
        "n_test_rooms": len(tests) * n,
        "q_passive": passive.q,
        "q_policy": policy_cal.q,
        "guarantee_passive": guarantee("passive", passive.n, alpha),
        "guarantee_passive_on_selected": guarantee("passive_on_selected", passive.n, alpha),
        "guarantee_policy": guarantee("policy", policy_cal.n, alpha),
    }
    return rows, record


def run_room_protocol(
    variants: Sequence[RoomVariant],
    *,
    base: RoomSurrogate,
    oracle: RoomSurrogate,
    make_policy: PolicyFactory,
    seed: int,
    repetitions: int = 10,
    alpha: float = 0.10,
    fractions: Sequence[float] = (0.4, 0.1, 0.25, 0.25),
) -> tuple[list[RoomCoverageRow], ProtocolInfo]:
    """Per-room coverage of the three procedures, ``repetitions`` fresh splits by source.

    Parameters
    ----------
    variants : sequence of RoomVariant
        Typed population, several variants per source.
    base : RoomSurrogate
        Surrogate before training (rescaled per room on ``train``).
    oracle : RoomSurrogate
        Frozen reference.
    make_policy : PolicyFactory
        ``(frozen surrogate, passive q_hat) -> policy`` (plan-level objective).
    seed : int
        Root seed; repetition ``r`` splits with ``derive(seed, f"rep/{r}")``.
    repetitions : int, optional
        Number of splits.
    alpha : float, optional
        Target level.
    fractions : sequence of float, optional
        Source fractions.

    Returns
    -------
    tuple
        ``(rows, info)``. The rows can be summarised by
        :func:`archlux.bench.selection.summarize` with ``keys=("room_type", "sector")``.

    Raises
    ------
    InvariantViolation
        ``repetitions < 1``.
    """
    if repetitions < 1:
        raise InvariantViolation(("repetitions must be >= 1",))
    rows: list[RoomCoverageRow] = []
    info = ProtocolInfo()
    for r in range(repetitions):
        new, record = _room_repetition(
            r, variants, derive(seed, f"rep/{r}"), base, oracle, make_policy, alpha, fractions
        )
        rows.extend(new)
        info.records.append(record)
    return rows, info


def write_room_rows(path: Path, rows: Sequence[RoomCoverageRow]) -> None:
    """Write the raw room rows as CSV, one interval per line.

    Parameters
    ----------
    path : Path
        Output CSV.
    rows : sequence of RoomCoverageRow
        Output of :func:`run_room_protocol`.
    """
    names = [f.name for f in fields(RoomCoverageRow)]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow([*names, "covered"])
        for r in rows:
            values = [getattr(r, n) for n in names]
            writer.writerow(
                [*(f"{v:.6f}" if isinstance(v, float) else v for v in values), r.covered]
            )
