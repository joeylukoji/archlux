"""Report stratified by orientation — mandatory, never a lone global aggregate."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

import numpy as np

from archlux._deprecation import Alias, lazy_aliases, renamed_parameters
from archlux.bench.run import Result
from archlux.bench.seeds import derive
from archlux.bench.stats import Interval, paired_bootstrap
from archlux.errors import InvariantViolation
from archlux.orient.circular import stratify

__all__ = ["N_REPLICATIONS", "BenchReport", "OrientationStratum", "report"]

N_REPLICATIONS = 2000
"""Bootstrap replications per stratum.

A 2.5% bound estimated over 199 replications is the 5th order statistic: its
Monte-Carlo error dominates the width being claimed for publication. 2000 brings
that error below the sampling noise for a paper table.
"""


@dataclass(frozen=True, slots=True)
class OrientationStratum:
    """Aggregates of a wind rose (sector)."""

    sector: str
    n: int
    scores_by_method: Mapping[str, Interval]


@dataclass(frozen=True, slots=True)
class BenchReport:
    """Output of :func:`report`: one stratum per sector, including empty ones."""

    strata: tuple[OrientationStratum, ...]


def _sector_by_degree(degres: Iterable[float], *, n_secteurs: int) -> dict[float, str]:
    """Map each distinct azimuth to its sector, via ``orient.stratify``.

    ``stratify`` returns grouped values, not indices, so it is queried distinct
    azimuth by distinct azimuth. Two equal azimuths always fall in the same sector,
    so ``O(distinct)`` calls suffice.
    """
    mapping: dict[float, str] = {}
    for deg in degres:
        groups = stratify([deg], n_secteurs=n_secteurs)
        mapping[deg] = next(name for name, values in groups.items() if values.size)
    return mapping


@renamed_parameters({"resultat": "result"})
def report(
    result: Result,
    *,
    seed: int,
    n_secteurs: int = 8,
) -> BenchReport:
    """Aggregate **after** the raw rows, stratified by orientation.

    Stratification is mandatory (`MILESTONE-6.md` §5): no single global summary.

    **Known limitation**: the intervals are marginal, one per (sector, method) pair.
    Reading ``n_secteurs × n_methods`` 95% intervals as that many simultaneous
    conclusions overstates significance; correct the family with
    :func:`archlux.bench.stats.holm` before any publication.
    """
    if n_secteurs < 1:
        raise InvariantViolation(("n_secteurs must be >= 1",))

    # The binning comes from ``stratify`` alone: reimplementing it here would let two
    # sector conventions silently diverge at the slightest tweak to ``orient``.
    names = tuple(stratify([0.0], n_secteurs=n_secteurs).keys())
    sector_of = _sector_by_degree(
        {row.orientation_deg for row in result.rows}, n_secteurs=n_secteurs
    )

    by_sector: dict[str, dict[str, list[float]]] = {name: defaultdict(list) for name in names}
    for row in result.rows:
        by_sector[sector_of[row.orientation_deg]][row.method].append(row.score)

    strata: list[OrientationStratum] = []
    for name in names:
        scores: dict[str, Interval] = {}
        for method, values in sorted(by_sector[name].items()):
            if len(values) >= 2:
                zeros = [0.0] * len(values)
                ic = paired_bootstrap(
                    values,
                    zeros,
                    # Named sub-seed rather than ``seed + i``: two neighboring strata
                    # do not end up with adjacent seeds.
                    seed=derive(seed, f"strate:{name}:{method}"),
                    n_replications=N_REPLICATIONS,
                    alpha=0.05,
                )
                scores[method] = Interval(value=float(np.mean(values)), low=ic.low, high=ic.high)
            elif len(values) == 1:
                # **Degenerate** interval: a single observation bounds nothing. It is
                # returned with zero width and must be read as "not estimable".
                v = float(values[0])
                scores[method] = Interval(value=v, low=v, high=v)
        n_plans = max((len(v) for v in by_sector[name].values()), default=0)
        strata.append(OrientationStratum(sector=name, n=n_plans, scores_by_method=scores))
    return BenchReport(strata=tuple(strata))


__getattr__ = lazy_aliases(
    __name__,
    {
        "RapportBanc": Alias(BenchReport, "archlux.bench.report.BenchReport"),
        "StrateOrientation": Alias(OrientationStratum, "archlux.bench.report.OrientationStratum"),
    },
)
