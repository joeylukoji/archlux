"""Splits by source plan, leakage checks, filter counts (spec 1.8)."""

from __future__ import annotations

import pytest

from archlux.data.provenance import (
    SPLIT_NAMES,
    FilterLog,
    SampleId,
    check_no_group_leakage,
    cross_split_near_duplicates,
    split_by_group,
)
from archlux.data.synthetic import generate_corpus
from archlux.errors import InvariantViolation


def test_sample_id_round_trips_and_refuses_ambiguous_fields() -> None:
    sample = SampleId("msd-12", "retrecir:0.25", "az090", "rep3")
    assert SampleId.parse(sample.key) == sample
    with pytest.raises(InvariantViolation):
        SampleId("a/b")
    with pytest.raises(InvariantViolation):
        SampleId.parse("only/three/fields")


def test_split_is_by_source_disjoint_complete_and_stable() -> None:
    sources = [f"s{i}" for i in range(100)]
    split = split_by_group(sources * 4, seed=17)  # four variants each: still 100 sources
    members = [s for name in SPLIT_NAMES for s in split.groups[name]]
    assert sorted(members) == sorted(sources)
    assert split.counts() == {"train": 40, "validation": 10, "calibration": 25, "test": 25}
    assert split_by_group(sources, seed=17) == split
    grown = split_by_group([*sources, "new"], seed=17)
    moved = [s for s in sources if grown.of(s) != split.of(s)]
    assert len(moved) <= 3  # rounding of the boundaries only, never a reshuffle


def test_split_refuses_bad_fractions() -> None:
    with pytest.raises(InvariantViolation):
        split_by_group(["a"], seed=1, fractions=(0.5, 0.5))
    with pytest.raises(InvariantViolation):
        split_by_group(["a"], seed=1, fractions=(0.5, 0.5, 0.5, -0.5))


def test_leakage_of_a_source_across_sets_is_refused() -> None:
    clean = {"calibration": [SampleId("a", variant="az0")], "test": [SampleId("b")]}
    check_no_group_leakage(clean)
    leaked = {"calibration": [SampleId("a", variant="az0")], "test": [SampleId("a", variant="az1")]}
    with pytest.raises(InvariantViolation, match="a in calibration and test"):
        check_no_group_leakage(leaked)


def test_cross_split_near_duplicates_finds_the_planted_twin() -> None:
    corpus = generate_corpus(60, seed=17)  # rank 53 is a planted twin of syn-0000
    split = split_by_group(corpus, seed=5)
    pairs = cross_split_near_duplicates(split, corpus)
    twin_split = split.of("syn-0000") != split.of("syn-0053")
    assert (("syn-0000", "syn-0053") in pairs) == twin_split


def test_filter_log_counts_every_step() -> None:
    log = FilterLog()
    kept = log.apply("even", range(10), lambda i: i % 2 == 0)
    kept = log.apply("small", kept, lambda i: i < 5)
    assert kept == [0, 2, 4]
    assert log.steps == [("even", 10, 5), ("small", 5, 3)]
    assert "| small | 5 | 3 | 2 | 60.0 % |" in log.to_markdown()
