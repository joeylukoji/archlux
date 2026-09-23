"""Corpus synthétique déterministe.

Les corpus MSD / Swiss Dwellings / CubiCasa5K ne sont pas redistribués ;
ce générateur tient le même contrat d'identifiants.
"""

from __future__ import annotations

import hashlib

import numpy as np

from archlux.erreurs import InvariantViole
from archlux.types import Piece, Plan

__all__ = ["TAILLE_MAX", "generer_corpus"]

_CONTOUR = ((0.0, 0.0), (12.0, 0.0), (12.0, 9.0), (0.0, 9.0))
_TYPES = ("sejour", "chambre", "cuisine", "sdb")
_RANG_JUMEAU_DEDUPLICATION = 53
_ID_SOURCE_JUMEAU = "syn-0000"
_N_COUPES_X = 10
_N_COUPES_Y = 9

TAILLE_MAX = _N_COUPES_X * _N_COUPES_Y
"""Nombre de coupes distinctes de la grille : au-delà, le corpus se répéterait."""


def _rng(seed: int, nom: str) -> np.random.Generator:
    """Sous-graine locale : ``data`` n'importe pas ``bench``."""
    digest = hashlib.blake2b(f"{seed}:{nom}".encode(), digest_size=4).digest()
    return np.random.default_rng(int.from_bytes(digest, "big"))


def generer_corpus(n: int, *, seed: int) -> dict[str, Plan]:
    """Produire ``n`` pavages 2×2 déterministes, identifiants ``syn-0000``.

    Parameters
    ----------
    n : int
        Taille du corpus, bornée par :data:`TAILLE_MAX` (10 × 9 coupes distinctes).
    seed : int
        Graine obligatoire, sans défaut (`ARCHITECTURE.md` §7).

    Raises
    ------
    InvariantViole
        ``n`` négatif, ou supérieur au nombre de coupes distinctes de la grille.
        Sans cette garde, ``n > TAILLE_MAX`` levait un ``IndexError`` nu hors du
        domaine d'erreurs du projet (`ARCHITECTURE.md` §7).
    """
    if n < 0:
        raise InvariantViole((f"n doit être ≥ 0, reçu {n}",))
    if n > TAILLE_MAX:
        raise InvariantViole((f"n={n} > {TAILLE_MAX} coupes distinctes disponibles",))
    rng = _rng(seed, "corpus")
    grilles_x = np.linspace(4.05, 7.95, _N_COUPES_X)
    grilles_y = np.linspace(3.05, 5.95, _N_COUPES_Y)
    paires = [(float(x), float(y)) for x in grilles_x for y in grilles_y]
    rng.shuffle(paires)
    corpus: dict[str, Plan] = {}
    for rang in range(n):
        coupe_x, coupe_y = paires[rang]
        pieces: tuple[Piece, ...] = (
            Piece("sw", _TYPES[rang % 4], 0.0, 0.0, coupe_x, coupe_y),
            Piece("se", _TYPES[(rang + 1) % 4], coupe_x, 0.0, 12.0 - coupe_x, coupe_y),
            Piece("nw", _TYPES[(rang + 2) % 4], 0.0, coupe_y, coupe_x, 9.0 - coupe_y),
            Piece("ne", _TYPES[(rang + 3) % 4], coupe_x, coupe_y, 12.0 - coupe_x, 9.0 - coupe_y),
        )
        identifiant = f"syn-{rang:04d}"
        if rang == _RANG_JUMEAU_DEDUPLICATION:
            pieces = corpus[_ID_SOURCE_JUMEAU].pieces
        corpus[identifiant] = Plan(pieces, (), (), _CONTOUR)
    return corpus
