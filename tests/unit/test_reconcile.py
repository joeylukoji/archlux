"""The paper's numbers stay pinned to the raw rows of ``results/`` (metric non-regression).

If a raw file changes, a published number moves: these tests fail before the paper is
left quoting a figure nothing produces any more.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from archlux.bench.reconcile import reconcile, to_json, to_markdown
from archlux.bench.stats import cluster_bootstrap_proportion
from archlux.errors import InvariantViolation

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results"


@pytest.fixture(scope="module")
def claims():  # type: ignore[no-untyped-def]
    return {(c.bench, c.quantity): c for c in reconcile(RESULTS)}


def test_b1_counts_cases_not_legalize_calls(claims) -> None:  # type: ignore[no-untyped-def]
    claim = claims["B1", "number of corrected cases"]
    assert claim.verdict == "article_wrong"
    assert claim.recomputed.startswith("270 cases")


@pytest.mark.parametrize(
    ("key", "fragment"),
    [
        (("B1", "legalize alone valid after"), "122/270 (45.2 %)"),
        (("B4", "coverage, exchangeable"), "89.8 % mean"),
        (("B4", "coverage, selected"), "87.8 % mean"),
        (("B6", "legalize / tiling / fallback valid after"), "35.9 % / 93.0 % / 93.9 %"),
        (("B8", "repaired at B=16 (tiling)"), "145/740 (19.6 %)"),
        (("B9", "median surrogate gain (IQR; range)"), "17.2 %"),
        (("B9", "variants saturating the 3.0 m radius / at the 0.50 m floor"), "36/48 ; 20/48"),
    ],
)
def test_published_numbers_are_recomputed_from_raw_rows(claims, key, fragment) -> None:  # type: ignore[no-untyped-def]
    assert fragment in claims[key].recomputed


def test_unverifiable_timing_is_not_marked_consistent(claims) -> None:  # type: ignore[no-untyped-def]
    assert claims["B9", "timing: 160 runs (20 plans x 8 azimuths), 160/160 valid"].verdict == (
        "cannot_verify"
    )


def test_committed_reconciliation_matches_a_fresh_one() -> None:
    fresh = to_json(reconcile(RESULTS))
    committed = json.loads((RESULTS / "reconciliation.json").read_text(encoding="utf-8"))
    assert committed == fresh
    assert to_markdown(reconcile(RESULTS)) in (RESULTS / "RECONCILIATION.md").read_text(
        encoding="utf-8"
    )


def test_cluster_bootstrap_is_wider_than_rows_when_clusters_are_homogeneous() -> None:
    # 10 clusters of 10 identical outcomes: the effective sample is 10, not 100.
    ok = [i < 50 for i in range(100)]
    groups = [str(i // 10) for i in range(100)]
    ci = cluster_bootstrap_proportion(ok, groups, seed=1)
    assert ci.value == 0.5
    assert ci.high - ci.low > 0.3  # Wilson on 100 rows would give about 0.19


def test_cluster_bootstrap_is_reproducible_and_checks_lengths() -> None:
    ok, groups = [True, False, True], ["a", "b", "c"]
    assert cluster_bootstrap_proportion(ok, groups, seed=3) == cluster_bootstrap_proportion(
        ok, groups, seed=3
    )
    with pytest.raises(InvariantViolation):
        cluster_bootstrap_proportion(ok, groups[:2], seed=3)
