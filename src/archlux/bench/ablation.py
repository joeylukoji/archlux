"""Ablations on one fixed set of inputs: what each component of the pipeline contributes.

Every configuration runs on **the same** corrupted plans, contexts and azimuths, so the
comparisons are paired. Configurations:

==================================== ==================================================
``initial``                          the corrupted input, not legalized
``repair``                           geometric repair only (``tiling=True``, L1)
``fw_surrogate``                     repair + Frank-Wolfe on the pessimistic surrogate
``fw_surrogate_no_penalty``          the same, without the ``- q_hat * sigma`` penalty
``fw_reference``                     repair + Frank-Wolfe on the frozen reference itself
``fw_surrogate_budget_<b>``          ``fw_surrogate`` under a displacement budget ``b``
==================================== ==================================================

Several initialisations (corruption seeds) of every source plan measure stability. The
"reference" is the frozen closed-form oracle (:class:`~archlux.light.split_flux.
SplitFluxOracle`), **not** a physical simulation: "confirmed by the reference" below
means confirmed by that oracle, and a Radiance comparison remains to be run.

Not covered here: an iteration-budget sweep. ``legalize`` does not expose Frank-Wolfe's
``max_iter``; the number of iterations and the stop status of every run are recorded
instead, so the share of runs that hit the cap is visible.
"""

from __future__ import annotations

import csv
import statistics
from collections.abc import Callable, Sequence
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

import numpy as np

from archlux.bench.stats import cluster_bootstrap_proportion
from archlux.certify.proof import verify_exactly
from archlux.data.corruption import corrupt
from archlux.errors import ArchluxError, InvariantViolation
from archlux.export.wilson import wilson_interval
from archlux.geom.polytope import decision_vector
from archlux.light.objective import Daylight
from archlux.light.protocol import Surrogate
from archlux.light.trust import FiniteDifferenceSurrogate
from archlux.seeds import derive
from archlux.types import Context, Orientation, Plan
from archlux.uq.conformal import conformal_quantile

__all__ = [
    "AblationCase",
    "AblationRow",
    "calibrate_q",
    "configurations",
    "run_ablations",
    "summarize_ablations",
    "write_ablation_rows",
]

LegalizeTrace = Callable[..., tuple[Plan, Any]]
"""Signature of the injected :func:`archlux.legalize_trace` (``bench`` never imports
``api``)."""


@dataclass(frozen=True, slots=True)
class AblationCase:
    """One input, shared by every configuration.

    Attributes
    ----------
    source : str
        Source plan identifier (the statistical unit).
    init : int
        Initialisation index (corruption seed rank).
    plan : Plan
        Corrupted plan.
    context : Context
        Its context, azimuth included.
    """

    source: str
    init: int
    plan: Plan
    context: Context


@dataclass(frozen=True, slots=True)
class AblationRow:
    """Outcome of one configuration on one case.

    Attributes
    ----------
    config : str
        Configuration name.
    source : str
        Source plan.
    init : int
        Initialisation index.
    azimuth : float
        Azimuth in degrees.
    status : str
        ``ok`` or the name of the refusal (``Infeasible``, ``GapNeedsTiling``...).
    valid : bool
        Exact verification of the output (of the input, for ``initial``).
    surrogate : float
        Surrogate value of the output (``nan`` on refusal).
    reference : float
        Reference (frozen oracle) value of the output (``nan`` on refusal).
    displacement : float
        Max displacement from the input, metres (``nan`` on refusal).
    iterations : int
        Frank-Wolfe iterations (0 without an objective).
    fw_status : str
        Frank-Wolfe stop status (``-`` without an objective).
    """

    config: str
    source: str
    init: int
    azimuth: float
    status: str
    valid: bool
    surrogate: float
    reference: float
    displacement: float
    iterations: int
    fw_status: str


def calibrate_q(
    model: Surrogate,
    reference: Surrogate,
    points: Sequence[tuple[np.ndarray, Orientation]],
    *,
    alpha: float = 0.10,
) -> float:
    """Passive conformal quantile of ``|y - y_hat| / sigma_hat`` on intact plans.

    Parameters
    ----------
    model : Surrogate
        Frozen surrogate.
    reference : Surrogate
        Frozen reference.
    points : Sequence[tuple[numpy.ndarray, Orientation]]
        Calibration points, disjoint from the ablation cases.
    alpha : float, optional
        Target level.

    Returns
    -------
    float
        ``q_hat``.
    """
    scores = [
        abs(reference.evaluate(x, o) - model.evaluate(x, o)) / max(model.uncertainty(x, o), 1e-12)
        for x, o in points
    ]
    return conformal_quantile(np.array(scores), alpha)


def configurations(
    model: Surrogate,
    reference: Surrogate,
    q_hat: float,
    budgets: Sequence[float],
    *,
    gradient_free: bool = False,
) -> dict[str, dict[str, object] | None]:
    """The configurations, as ``legalize`` keyword arguments (``None``: not legalized).

    Parameters
    ----------
    model : Surrogate
        Frozen surrogate.
    reference : Surrogate
        Frozen reference (Frank-Wolfe on it is the ideal-objective baseline).
    q_hat : float
        Passive conformal quantile of ``model``.
    budgets : Sequence[float]
        Displacement budgets, metres.
    gradient_free : bool, optional
        Add ``fw_finite_difference``: the same surrogate, its analytic gradient replaced
        by centred finite differences (:class:`~archlux.light.trust.
        FiniteDifferenceSurrogate`), no penalty. Same values, no learned direction: it
        isolates what the closed-form gradient contributes.

    Returns
    -------
    dict
        Name -> keyword arguments of ``legalize_trace``.
    """
    surrogate = Daylight(model, q_hat=q_hat)
    configs: dict[str, dict[str, object] | None] = {
        "initial": None,
        "repair": {"tiling": True},
        "fw_surrogate": {"tiling": True, "objective": surrogate},
        "fw_surrogate_no_penalty": {
            "tiling": True,
            "objective": Daylight(model, q_hat=q_hat, pessimistic=False),
        },
        "fw_reference": {
            "tiling": True,
            "objective": Daylight(reference, q_hat=0.0, pessimistic=False),
        },
    }
    if gradient_free:
        configs["fw_finite_difference"] = {
            "tiling": True,
            "objective": Daylight(
                FiniteDifferenceSurrogate(base=model, target_indicator=model.indicator),
                q_hat=0.0,
                pessimistic=False,
            ),
        }
    for b in budgets:
        configs[f"fw_surrogate_budget_{b:g}"] = {
            "tiling": True,
            "objective": surrogate,
            "budget": b,
        }
    return configs


def _values(
    plan: Plan, context: Context, model: Surrogate, reference: Surrogate
) -> tuple[float, float]:
    """Surrogate and reference values of ``plan``.

    Parameters
    ----------
    plan : Plan
        Plan to evaluate.
    context : Context
        Its context (azimuth).
    model : Surrogate
        Surrogate.
    reference : Surrogate
        Reference.

    Returns
    -------
    tuple of float
        ``(surrogate, reference)``.
    """
    x = decision_vector(plan)
    return model.evaluate(x, context.orientation), reference.evaluate(x, context.orientation)


def _run_one(
    name: str,
    kwargs: dict[str, object] | None,
    case: AblationCase,
    legalize_trace: LegalizeTrace,
    model: Surrogate,
    reference: Surrogate,
) -> AblationRow:
    """Run one configuration on one case.

    Parameters
    ----------
    name : str
        Configuration name.
    kwargs : dict or None
        Keyword arguments of ``legalize_trace``; ``None`` for ``initial``.
    case : AblationCase
        The input.
    legalize_trace : LegalizeTrace
        Injected :func:`archlux.legalize_trace`.
    model, reference : Surrogate
        Surrogate and reference, to evaluate the output.

    Returns
    -------
    AblationRow
        The outcome, refusals included.
    """
    head: dict[str, Any] = {"config": name, "source": case.source, "init": case.init}
    head["azimuth"] = case.context.orientation.deg
    idle: dict[str, Any] = {"iterations": 0, "fw_status": "-"}
    if kwargs is None:
        s, r = _values(case.plan, case.context, model, reference)
        valid = verify_exactly(case.plan, case.context).valid
        values: dict[str, Any] = {
            "valid": valid,
            "surrogate": s,
            "reference": r,
            "displacement": 0.0,
        }
        return AblationRow(**head, status="ok", **values, **idle)
    try:
        out, trace = legalize_trace(case.plan, case.context, **kwargs)
    except ArchluxError as error:
        nan = float("nan")
        failed: dict[str, Any] = {
            "valid": False,
            "surrogate": nan,
            "reference": nan,
            "displacement": nan,
        }
        return AblationRow(**head, status=type(error).__name__, **failed, **idle)
    if out.certificate is None:  # legalize always certifies; guard for the type checker
        raise InvariantViolation(("legalize returned a plan without a certificate",))
    proof = out.certificate.geometry
    s, r = _values(out, case.context, model, reference)
    return AblationRow(
        **head,
        status="ok",
        valid=proof.valid,
        surrogate=s,
        reference=r,
        displacement=proof.max_displacement,
        iterations=len(trace.iterations) if trace is not None else 0,
        fw_status=str(trace.status) if trace is not None else "-",
    )


def make_cases(
    plans: dict[str, Plan],
    context_of: Callable[[Plan, Orientation], Context],
    *,
    seed: int,
    n_inits: int = 3,
    amplitude: float = 0.25,
) -> list[AblationCase]:
    """Corrupt every source plan ``n_inits`` times, one azimuth per source.

    Parameters
    ----------
    plans : dict of str to Plan
        Valid source plans.
    context_of : Callable[[Plan, Orientation], Context]
        Context of a source plan at an azimuth.
    seed : int
        Root seed.
    n_inits : int, optional
        Initialisations (corruption seeds) per source.
    amplitude : float, optional
        Corruption amplitude, metres.

    Returns
    -------
    list of AblationCase
        ``len(plans) * n_inits`` cases, sorted by source then init.
    """
    cases = []
    for source, plan in sorted(plans.items()):
        azimuth = Orientation(float(derive(seed, f"azimuth/{source}") % 360))
        context = context_of(plan, azimuth)
        for init in range(n_inits):
            faulty, _ = corrupt(
                plan, seed=derive(seed, f"init/{source}/{init}"), amplitude=amplitude
            )
            cases.append(AblationCase(source, init, faulty, context))
    return cases


def run_ablations(
    cases: Sequence[AblationCase],
    configs: dict[str, dict[str, object] | None],
    *,
    legalize_trace: LegalizeTrace,
    model: Surrogate,
    reference: Surrogate,
) -> list[AblationRow]:
    """Run every configuration on every case.

    Parameters
    ----------
    cases : Sequence[AblationCase]
        Shared inputs.
    configs : dict
        Output of :func:`configurations`.
    legalize_trace : LegalizeTrace
        Injected :func:`archlux.legalize_trace`.
    model, reference : Surrogate
        Surrogate and reference.

    Returns
    -------
    list of AblationRow
        ``len(cases) * len(configs)`` rows.
    """
    return [
        _run_one(name, kwargs, case, legalize_trace, model, reference)
        for name, kwargs in configs.items()
        for case in cases
    ]


def _gain(after: float, before: float) -> float:
    """Relative change in percent, ``nan`` when undefined.

    Parameters
    ----------
    after, before : float
        Values.

    Returns
    -------
    float
        ``100 * (after / before - 1)``.
    """
    if not np.isfinite(after) or not np.isfinite(before) or before == 0.0:
        return float("nan")
    return 100.0 * (after / before - 1.0)


def _paired(
    rows: Sequence[AblationRow], baseline: dict[tuple[str, int], AblationRow]
) -> dict[str, float]:
    """Gains of ``rows`` over the ``repair`` baseline, paired by case.

    Parameters
    ----------
    rows : Sequence[AblationRow]
        Rows of one configuration.
    baseline : dict
        ``(source, init) -> repair row``.

    Returns
    -------
    dict of str to float
        Median surrogate and reference gains, share of predicted gains the reference
        contradicts, share of valid outputs with a reference-confirmed gain.
    """
    pairs = [(r, baseline[r.source, r.init]) for r in rows]
    kept = [(r, b) for r, b in pairs if r.valid and b.valid]
    sg = np.array([_gain(r.surrogate, b.surrogate) for r, b in kept] or [np.nan])
    rg = np.array([_gain(r.reference, b.reference) for r, b in kept] or [np.nan])
    predicted = sg > 0.0
    return {
        "median_surrogate_gain": _median(sg),
        "median_reference_gain": _median(rg),
        "contradicted": _share(rg[predicted] <= 0.0),
        "confirmed_share_of_valid": float((rg > 0.0).sum() / max(len(rows), 1)),
    }


def _median(values: np.ndarray) -> float:
    """Median of the finite values, ``nan`` when there are none.

    Parameters
    ----------
    values : numpy.ndarray
        Values, possibly ``nan``.

    Returns
    -------
    float
        The median.
    """
    finite = values[np.isfinite(values)]
    return float(np.median(finite)) if finite.size else float("nan")


def _share(flags: np.ndarray) -> float:
    """Share of ``True``, ``nan`` for an empty array.

    Parameters
    ----------
    flags : numpy.ndarray
        Booleans.

    Returns
    -------
    float
        ``mean(flags)``.
    """
    return float(flags.mean()) if flags.size else float("nan")


def _line(
    name: str,
    mine: Sequence[AblationRow],
    baseline: dict[tuple[str, int], AblationRow],
    seed: int,
) -> str:
    """One table line.

    Parameters
    ----------
    name : str
        Configuration.
    mine : Sequence[AblationRow]
        Its rows.
    baseline : dict
        ``(source, init) -> repair row``.
    seed : int
        Bootstrap seed.

    Returns
    -------
    str
        The Markdown line.
    """
    valid = np.array([r.valid for r in mine])
    k = int(valid.sum())
    low, high = wilson_interval(k, len(mine))
    ci = cluster_bootstrap_proportion(list(valid), [r.source for r in mine], seed=seed)
    p = _paired(mine, baseline)
    disp = np.array([r.displacement for r in mine])[valid]
    median_disp = float(np.median(disp)) if disp.size else float("nan")
    capped = sum(r.fw_status == "max_iter" for r in mine)
    return (
        f"| {name} | {len(mine)} | {k} | [{100 * low:.1f} ; {100 * high:.1f}] | "
        f"[{100 * ci.low:.1f} ; {100 * ci.high:.1f}] | {median_disp:.3f} | "
        f"{p['median_surrogate_gain']:+.1f} % | {p['median_reference_gain']:+.1f} % | "
        f"{100 * p['contradicted']:.1f} % | {100 * p['confirmed_share_of_valid']:.1f} % | "
        f"{capped} | {_stability(mine):.3f} |"
    )


def _stability(rows: Sequence[AblationRow]) -> float:
    """Median, over sources, of the spread of the reference value across inits.

    Parameters
    ----------
    rows : Sequence[AblationRow]
        Rows of one configuration.

    Returns
    -------
    float
        Median per-source standard deviation (valid outputs, >= 2 inits).
    """
    by_source: dict[str, list[float]] = {}
    for r in rows:
        if r.valid:
            by_source.setdefault(r.source, []).append(r.reference)
    spreads = [statistics.stdev(v) for v in by_source.values() if len(v) > 1]
    return float(np.median(spreads)) if spreads else float("nan")


def summarize_ablations(rows: Sequence[AblationRow], *, seed: int) -> str:
    """One Markdown table, one line per configuration, gains paired against ``repair``.

    Parameters
    ----------
    rows : Sequence[AblationRow]
        Output of :func:`run_ablations`.
    seed : int
        Seed of the cluster bootstrap (clusters: source plans).

    Returns
    -------
    str
        The table.

    Raises
    ------
    InvariantViolation
        No ``repair`` rows to pair against.
    """
    baseline = {(r.source, r.init): r for r in rows if r.config == "repair"}
    if not baseline:
        raise InvariantViolation(("no repair rows",))
    lines = [
        "| config | n | valid | Wilson 95 % | cluster 95 % | median displ. (m) | "
        "surrogate gain | reference gain | predicted gain contradicted | valid and confirmed "
        "| FW at max_iter | spread across inits |",
        "|---|--:|--:|:--:|:--:|--:|--:|--:|--:|--:|--:|--:|",
    ]
    for name in dict.fromkeys(r.config for r in rows):
        lines.append(_line(name, [r for r in rows if r.config == name], baseline, seed))
    return "\n".join(lines) + "\n"


def write_ablation_rows(path: Path, rows: Sequence[AblationRow]) -> None:
    """Write the raw rows as CSV.

    Parameters
    ----------
    path : Path
        Output CSV.
    rows : Sequence[AblationRow]
        Output of :func:`run_ablations`.
    """
    names = [f.name for f in fields(AblationRow)]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(names)
        for r in rows:
            values = [getattr(r, n) for n in names]
            writer.writerow([f"{v:.6f}" if isinstance(v, float) else v for v in values])
