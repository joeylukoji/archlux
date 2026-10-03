"""Deduplication and distributions: `MILESTONE-4.md` §2."""

from __future__ import annotations

from pathlib import Path

from scipy.stats import ks_2samp

from archlux.bench.protocol import load_split
from archlux.data.dedup import near_duplicate_pairs
from archlux.data.synthetic import generate_corpus

SPLITS = Path(__file__).resolve().parents[2] / "splits" / "v1"


def _split_of(id: str) -> str:
    split = load_split(SPLITS)
    if id in split.train:
        return "train"
    if id in split.calibration:
        return "calibration"
    if id in split.test:
        return "test"
    raise AssertionError(id)


def test_no_duplicate_crosses_a_boundary() -> None:
    corpus = generate_corpus(90, seed=17)
    for a, b in near_duplicate_pairs(tuple(corpus.items()), threshold=0.02):
        assert _split_of(a) == _split_of(b)


def test_comparable_distributions() -> None:
    """The three sets have statistically close SW widths."""
    corpus = generate_corpus(90, seed=17)
    split = load_split(SPLITS)

    def widths(ids: tuple[str, ...]) -> list[float]:
        return [next(p.w for p in corpus[i].rooms if p.id == "sw") for i in ids]

    train = widths(split.train)
    test = widths(split.test)
    calib = widths(split.calibration)
    assert ks_2samp(train, test).pvalue > 0.05
    assert ks_2samp(train, calib).pvalue > 0.05
