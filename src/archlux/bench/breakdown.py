"""Surrogate errors broken down by group, with intervals that resample whole clusters.

:func:`archlux.light.evaluation.evaluate_surrogate` needs a live
:class:`~archlux.light.reference.Reference`. The paper's B7 compares a surrogate with
**tabulated** labels (Swiss Dwellings simulations, read from a file), and its unit of
independence is the site, not the plan. This module takes the two columns as they are,
plus one label per row for each grouping, and reports per group: ``n``, clusters, MAE,
bias, relative MAE and Spearman, each MAE and bias with a 95 % cluster-bootstrap interval.

It also writes and reads the raw rows, so that a table published from a corpus that
cannot be redistributed can at least be recomputed from its rows.
"""

from __future__ import annotations

import csv
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy import stats as scipy_stats

from archlux.errors import InvariantViolation

__all__ = ["GroupError", "breakdown", "to_markdown", "write_breakdown_rows"]

_LEVEL = 0.95


@dataclass(frozen=True, slots=True)
class GroupError:
    """Errors of one group.

    Attributes
    ----------
    grouping : str
        Name of the grouping (``all``, ``orientation``, ``room_type``...).
    group : str
        Label within the grouping.
    n : int
        Rows.
    n_clusters : int
        Distinct clusters (sites, source plans).
    mae, mae_low, mae_high : float
        Mean absolute error and its cluster-bootstrap interval.
    bias, bias_low, bias_high : float
        Mean ``prediction - truth`` and its interval.
    relative_mae : float
        ``mean |pred - truth| / mean |truth|`` (``nan`` when ``mean |truth| == 0``).
    spearman : float
        Rank correlation (``nan`` below three rows or for a constant column).
    """

    grouping: str
    group: str
    n: int
    n_clusters: int
    mae: float
    mae_low: float
    mae_high: float
    bias: float
    bias_low: float
    bias_high: float
    relative_mae: float
    spearman: float


def _cluster_ci(
    values: np.ndarray, clusters: np.ndarray, rng: np.random.Generator, draws: int
) -> tuple[float, float]:
    """Percentile interval of the mean, resampling whole clusters.

    Parameters
    ----------
    values : numpy.ndarray
        One value per row.
    clusters : numpy.ndarray
        Cluster label per row.
    rng : numpy.random.Generator
        Random source.
    draws : int
        Bootstrap draws.

    Returns
    -------
    tuple of float
        ``(low, high)``; ``(nan, nan)`` with fewer than two clusters.
    """
    labels, inverse = np.unique(clusters, return_inverse=True)
    if labels.size < 2:
        return math.nan, math.nan
    sums = np.bincount(inverse, weights=values, minlength=labels.size)
    counts = np.bincount(inverse, minlength=labels.size).astype(float)
    picks = rng.integers(0, labels.size, size=(draws, labels.size))
    means = sums[picks].sum(axis=1) / counts[picks].sum(axis=1)
    tail = (1.0 - _LEVEL) / 2.0
    low, high = np.quantile(means, [tail, 1.0 - tail])
    return float(low), float(high)


def _spearman(pred: np.ndarray, truth: np.ndarray) -> float:
    """Spearman correlation, ``nan`` when undefined.

    Parameters
    ----------
    pred, truth : numpy.ndarray
        Columns.

    Returns
    -------
    float
        The rank correlation.
    """
    if pred.size < 3 or np.ptp(pred) == 0.0 or np.ptp(truth) == 0.0:
        return math.nan
    return float(scipy_stats.spearmanr(pred, truth).statistic)


def _group(
    grouping: str,
    group: str,
    pred: np.ndarray,
    truth: np.ndarray,
    clusters: np.ndarray,
    rng: np.random.Generator,
    draws: int,
) -> GroupError:
    """Errors of one subset.

    Parameters
    ----------
    grouping, group : str
        Labels.
    pred, truth : numpy.ndarray
        Columns of the subset.
    clusters : numpy.ndarray
        Clusters of the subset.
    rng : numpy.random.Generator
        Random source.
    draws : int
        Bootstrap draws.

    Returns
    -------
    GroupError
        The summary.
    """
    error = pred - truth
    scale = float(np.mean(np.abs(truth)))
    mae_ci = _cluster_ci(np.abs(error), clusters, rng, draws)
    bias_ci = _cluster_ci(error, clusters, rng, draws)
    return GroupError(
        grouping=grouping,
        group=group,
        n=int(pred.size),
        n_clusters=int(np.unique(clusters).size),
        mae=float(np.mean(np.abs(error))),
        mae_low=mae_ci[0],
        mae_high=mae_ci[1],
        bias=float(np.mean(error)),
        bias_low=bias_ci[0],
        bias_high=bias_ci[1],
        relative_mae=float(np.mean(np.abs(error))) / scale if scale > 0.0 else math.nan,
        spearman=_spearman(pred, truth),
    )


def breakdown(
    prediction: Sequence[float],
    truth: Sequence[float],
    clusters: Sequence[str],
    labels: Mapping[str, Sequence[str]],
    *,
    seed: int,
    draws: int = 2000,
) -> list[GroupError]:
    """Errors overall, then per group of every grouping.

    Parameters
    ----------
    prediction, truth : sequence of float
        Surrogate value and reference value of each row.
    clusters : sequence of str
        Unit of independence of each row (site, source plan).
    labels : mapping of str to sequence of str
        ``grouping -> one label per row``.
    seed : int
        Bootstrap seed. Mandatory.
    draws : int, optional
        Bootstrap draws.

    Returns
    -------
    list of GroupError
        ``all`` first, then each grouping's labels in sorted order.

    Raises
    ------
    InvariantViolation
        Columns of different lengths, or no rows.
    """
    pred = np.asarray(prediction, dtype=float)
    ref = np.asarray(truth, dtype=float)
    cl = np.asarray(clusters, dtype=str)
    n = pred.size
    if n == 0 or ref.size != n or cl.size != n or any(len(v) != n for v in labels.values()):
        raise InvariantViolation(("breakdown needs non-empty columns of one length",))
    rng = np.random.default_rng(seed)
    out = [_group("all", "all", pred, ref, cl, rng, draws)]
    for grouping, column in labels.items():
        col = np.asarray(column, dtype=str)
        for value in sorted(set(col.tolist())):
            keep = col == value
            out.append(_group(grouping, value, pred[keep], ref[keep], cl[keep], rng, draws))
    return out


def to_markdown(groups: Sequence[GroupError], *, unit: str = "") -> str:
    """One Markdown table of :func:`breakdown`'s output.

    Parameters
    ----------
    groups : sequence of GroupError
        Output of :func:`breakdown`.
    unit : str, optional
        Unit of the errors, printed in the header.

    Returns
    -------
    str
        The table.
    """
    u = f" ({unit})" if unit else ""
    lines = [
        f"| grouping | group | n | clusters | MAE{u} [95 % cluster CI] | bias{u} [95 % CI] "
        "| relative MAE | Spearman |",
        "|---|---|--:|--:|:--:|:--:|--:|--:|",
    ]
    for g in groups:
        lines.append(
            f"| {g.grouping} | {g.group} | {g.n} | {g.n_clusters} | {g.mae:.3f} "
            f"[{g.mae_low:.3f} ; {g.mae_high:.3f}] | {g.bias:+.3f} "
            f"[{g.bias_low:+.3f} ; {g.bias_high:+.3f}] | {100 * g.relative_mae:.1f} % | "
            f"{g.spearman:+.3f} |"
        )
    return "\n".join(lines) + "\n"


def write_breakdown_rows(
    path: Path,
    ids: Sequence[str],
    clusters: Sequence[str],
    predictions: Mapping[str, Sequence[float]],
    truth: Sequence[float],
    labels: Mapping[str, Sequence[str]],
) -> None:
    """Write the raw rows: id, cluster, labels, reference, one column per model.

    Parameters
    ----------
    path : Path
        Output CSV.
    ids, clusters : sequence of str
        Row identifier and cluster.
    predictions : mapping of str to sequence of float
        ``model name -> prediction per row``.
    truth : sequence of float
        Reference value per row.
    labels : mapping of str to sequence of str
        ``grouping -> label per row``.
    """
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["id", "cluster", *labels, "truth", *predictions])
        for i, (row_id, cluster) in enumerate(zip(ids, clusters, strict=True)):
            cells = [f"{float(p[i]):.6f}" for p in predictions.values()]
            writer.writerow(
                [
                    row_id,
                    cluster,
                    *(v[i] for v in labels.values()),
                    f"{float(truth[i]):.6f}",
                    *cells,
                ]
            )
