"""Déduplication et distributions — `MILESTONE-4.md` §2."""

from __future__ import annotations

from pathlib import Path

from scipy.stats import ks_2samp

from archlux.bench.protocol import load_split
from archlux.data.dedup import near_duplicate_pairs
from archlux.data.synthetic import generate_corpus

SPLITS = Path(__file__).resolve().parents[2] / "splits" / "v1"


def _split_de(id: str) -> str:
    split = load_split(SPLITS)
    if id in split.train:
        return "train"
    if id in split.calibration:
        return "calibration"
    if id in split.test:
        return "test"
    raise AssertionError(id)


def test_aucun_doublon_franchit_une_frontiere() -> None:
    corpus = generate_corpus(90, seed=17)
    for a, b in near_duplicate_pairs(tuple(corpus.items()), threshold=0.02):
        assert _split_de(a) == _split_de(b)


def test_distributions_comparables() -> None:
    """Les trois jeux ont des largeurs SW statistiquement proches."""
    corpus = generate_corpus(90, seed=17)
    split = load_split(SPLITS)

    def largeurs(ids: tuple[str, ...]) -> list[float]:
        return [next(p.w for p in corpus[i].rooms if p.id == "sw") for i in ids]

    train = largeurs(split.train)
    test = largeurs(split.test)
    calib = largeurs(split.calibration)
    assert ks_2samp(train, test).pvalue > 0.05
    assert ks_2samp(train, calib).pvalue > 0.05
