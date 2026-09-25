"""Corpus synthétique déterministe.

Les corpus MSD / Swiss Dwellings / CubiCasa5K ne sont pas redistribués ;
ce générateur tient le même contrat d'identifiants.
"""

from __future__ import annotations

import numpy as np

from archlux.erreurs import InvariantViole
from archlux.seeds import derive
from archlux.types import Orientation, Piece, Plan

__all__ = [
    "TAILLE_MAX",
    "TWO_ROOM_OUTLINE",
    "generer_corpus",
    "two_room_plan",
    "two_room_vectors",
]

_CONTOUR = ((0.0, 0.0), (12.0, 0.0), (12.0, 9.0), (0.0, 9.0))
_TYPES = ("sejour", "chambre", "cuisine", "sdb")
_RANG_JUMEAU_DEDUPLICATION = 53
_ID_SOURCE_JUMEAU = "syn-0000"
_N_COUPES_X = 10
_N_COUPES_Y = 9

TAILLE_MAX = _N_COUPES_X * _N_COUPES_Y
"""Nombre de coupes distinctes de la grille : au-delà, le corpus se répéterait."""


def _rng(seed: int, nom: str) -> np.random.Generator:
    """Named sub-stream (:func:`archlux.seeds.derive`): ``data`` does not import ``bench``."""
    return np.random.default_rng(derive(seed, nom))


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


def two_room_vectors(
    n: int, *, seed: int
) -> tuple[tuple[np.ndarray, ...], tuple[Orientation, ...]]:
    """Draw ``n`` decision vectors of two rooms side by side, with an azimuth each.

    The toy family of milestones 4 to 6 (AUDIT.md M12): rooms ``[0, c] x [0, 4.5]`` and
    ``[c, 12] x [0, 4.5]``, the cut ``c`` uniform in ``[4, 8]`` m, the azimuth uniform in
    ``[0, 360)``. One degree of freedom: a surrogate that fits it has learned a curve,
    not daylight (``docs/donnees/verite-terrain.md``).

    Parameters
    ----------
    n : int
        Number of vectors, ``n >= 0``.
    seed : int
        Mandatory, no default (``ARCHITECTURE.md`` §7).

    Returns
    -------
    tuple
        ``(vectors, orientations)``: vectors in the column order of
        :func:`archlux.geom.polytope.decision_vector`.

    Raises
    ------
    InvariantViole
        ``n`` is negative.
    """
    if n < 0:
        raise InvariantViole((f"n must be >= 0, got {n}",))
    rng = _rng(seed, "two_room_vectors")
    cuts, azimuths = rng.uniform(4.0, 8.0, n), rng.uniform(0.0, 360.0, n)
    vectors = tuple(np.array([0.0, 0.0, c, 4.5, c, 0.0, 12.0 - c, 4.5]) for c in cuts)
    return vectors, tuple(Orientation(deg=float(a)) for a in azimuths)


TWO_ROOM_OUTLINE = ((0.0, 0.0), (12.0, 0.0), (12.0, 4.5), (0.0, 4.5))
"""Outline of the :func:`two_room_vectors` family, in metres."""


def two_room_plan(x: np.ndarray) -> Plan:
    """The plan of a :func:`two_room_vectors` vector: room ``a`` (living) left of ``b``.

    Parameters
    ----------
    x : numpy.ndarray
        Vector ``(a.x, a.y, a.w, a.h, b.x, b.y, b.w, b.h)``.

    Returns
    -------
    Plan
        Two rooms, no wall, outline :data:`TWO_ROOM_OUTLINE`.
    """
    a = Piece("a", "sejour", float(x[0]), float(x[1]), float(x[2]), float(x[3]))
    b = Piece("b", "chambre", float(x[4]), float(x[5]), float(x[6]), float(x[7]))
    return Plan((a, b), (), (), TWO_ROOM_OUTLINE)
