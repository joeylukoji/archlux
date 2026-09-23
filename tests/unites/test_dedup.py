"""Déduplication et distributions — `MILESTONE-4.md` §2."""

from __future__ import annotations

from pathlib import Path

from scipy.stats import ks_2samp

from archlux.bench.protocole import charger_decoupage
from archlux.data.dedup import paires_quasi_identiques
from archlux.data.synthese import generer_corpus

SPLITS = Path(__file__).resolve().parents[2] / "splits" / "v1"


def _split_de(identifiant: str) -> str:
    decoupage = charger_decoupage(SPLITS)
    if identifiant in decoupage.entrainement:
        return "train"
    if identifiant in decoupage.calibration:
        return "calibration"
    if identifiant in decoupage.test:
        return "test"
    raise AssertionError(identifiant)


def test_aucun_doublon_franchit_une_frontiere() -> None:
    corpus = generer_corpus(90, seed=17)
    for a, b in paires_quasi_identiques(tuple(corpus.items()), seuil=0.02):
        assert _split_de(a) == _split_de(b)


def test_distributions_comparables() -> None:
    """Les trois jeux ont des largeurs SW statistiquement proches."""
    corpus = generer_corpus(90, seed=17)
    decoupage = charger_decoupage(SPLITS)

    def largeurs(ids: tuple[str, ...]) -> list[float]:
        return [next(p.w for p in corpus[i].pieces if p.id == "sw") for i in ids]

    train = largeurs(decoupage.entrainement)
    test = largeurs(decoupage.test)
    calib = largeurs(decoupage.calibration)
    assert ks_2samp(train, test).pvalue > 0.05
    assert ks_2samp(train, calib).pvalue > 0.05
