"""Named sub-seeds (AUDIT.md Q-M5): one stream per component, no overlap between runs."""

from __future__ import annotations

from archlux.bench.graines import deriver
from archlux.seeds import derive


def test_bench_derivation_is_unchanged() -> None:
    """``bench.graines.deriver`` delegates: published manifests keep their sub-seeds."""
    assert all(deriver(s, n) == derive(s, n) for s in range(5) for n in ("a", "fit/0"))


def test_consecutive_run_seeds_do_not_share_cycles() -> None:
    """With ``seed + cycle``, run 17 at cycle 1 was run 18 at cycle 0."""
    streams_17 = {derive(17, f"selection/{cycle}") for cycle in range(50)}
    streams_18 = {derive(18, f"selection/{cycle}") for cycle in range(50)}
    assert not streams_17 & streams_18
    assert derive(17, "selection/0") != derive(17, "fit/0")
