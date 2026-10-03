"""Deterministic synthetic corpus.

The MSD / Swiss Dwellings / CubiCasa5K corpora are not redistributed; this
generator honours the same identifier contract.
"""

from __future__ import annotations

import numpy as np

from archlux._deprecation import Alias, lazy_aliases
from archlux.errors import InvariantViolation
from archlux.seeds import derive
from archlux.types import Orientation, Plan, Room

__all__ = [
    "MAX_SIZE",
    "TWO_ROOM_OUTLINE",
    "generate_corpus",
    "two_room_plan",
    "two_room_vectors",
]

_OUTLINE = ((0.0, 0.0), (12.0, 0.0), (12.0, 9.0), (0.0, 9.0))
_TYPES = ("living_room", "bedroom", "kitchen", "bathroom")
_DEDUPLICATION_TWIN_RANK = 53
_TWIN_SOURCE_ID = "syn-0000"
_N_CUTS_X = 10
_N_CUTS_Y = 9

MAX_SIZE = _N_CUTS_X * _N_CUTS_Y
"""Number of distinct cuts of the grid: beyond this, the corpus would repeat."""


def _rng(seed: int, name: str) -> np.random.Generator:
    """Named sub-stream (:func:`archlux.seeds.derive`): ``data`` does not import ``bench``."""
    return np.random.default_rng(derive(seed, name))


def generate_corpus(n: int, *, seed: int) -> dict[str, Plan]:
    """Produce ``n`` deterministic 2x2 tilings, identifiers ``syn-0000``.

    Parameters
    ----------
    n : int
        Corpus size, bounded by :data:`MAX_SIZE` (10 x 9 distinct cuts).
    seed : int
        Mandatory seed, with no default (`ARCHITECTURE.md` §7).

    Raises
    ------
    InvariantViolation
        ``n`` negative, or greater than the number of distinct cuts of the
        grid. Without this guard, ``n > MAX_SIZE`` would raise a bare
        ``IndexError`` outside the project's error domain (`ARCHITECTURE.md` §7).
    """
    if n < 0:
        raise InvariantViolation((f"n must be >= 0, got {n}",))
    if n > MAX_SIZE:
        raise InvariantViolation((f"n={n} > {MAX_SIZE} distinct cuts available",))
    rng = _rng(seed, "corpus")
    grids_x = np.linspace(4.05, 7.95, _N_CUTS_X)
    grids_y = np.linspace(3.05, 5.95, _N_CUTS_Y)
    pairs = [(float(x), float(y)) for x in grids_x for y in grids_y]
    rng.shuffle(pairs)
    corpus: dict[str, Plan] = {}
    for rank in range(n):
        cut_x, cut_y = pairs[rank]
        rooms: tuple[Room, ...] = (
            Room(id="sw", type=_TYPES[rank % 4], x=0.0, y=0.0, w=cut_x, h=cut_y),
            Room(id="se", type=_TYPES[(rank + 1) % 4], x=cut_x, y=0.0, w=12.0 - cut_x, h=cut_y),
            Room(id="nw", type=_TYPES[(rank + 2) % 4], x=0.0, y=cut_y, w=cut_x, h=9.0 - cut_y),
            Room(
                id="ne",
                type=_TYPES[(rank + 3) % 4],
                x=cut_x,
                y=cut_y,
                w=12.0 - cut_x,
                h=9.0 - cut_y,
            ),
        )
        id = f"syn-{rank:04d}"
        if rank == _DEDUPLICATION_TWIN_RANK:
            rooms = corpus[_TWIN_SOURCE_ID].rooms
        corpus[id] = Plan(rooms, (), (), _OUTLINE)
    return corpus


def two_room_vectors(
    n: int, *, seed: int
) -> tuple[tuple[np.ndarray, ...], tuple[Orientation, ...]]:
    """Draw ``n`` decision vectors of two rooms side by side, with an azimuth each.

    The toy family of milestones 4 to 6 (AUDIT.md M12): rooms ``[0, c] x [0, 4.5]`` and
    ``[c, 12] x [0, 4.5]``, the cut ``c`` uniform in ``[4, 8]`` m, the azimuth uniform in
    ``[0, 360)``. One degree of freedom: a surrogate that fits it has learned a curve,
    not daylight (``docs/data/ground-truth.md``).

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
    InvariantViolation
        ``n`` is negative.
    """
    if n < 0:
        raise InvariantViolation((f"n must be >= 0, got {n}",))
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
    a = Room(id="a", type="living_room", x=float(x[0]), y=float(x[1]), w=float(x[2]), h=float(x[3]))
    b = Room(id="b", type="bedroom", x=float(x[4]), y=float(x[5]), w=float(x[6]), h=float(x[7]))
    return Plan((a, b), (), (), TWO_ROOM_OUTLINE)


__getattr__ = lazy_aliases(
    __name__,
    {
        "generer_corpus": Alias(generate_corpus, "archlux.data.synthetic.generate_corpus"),
        "TAILLE_MAX": Alias(MAX_SIZE, "archlux.data.synthetic.MAX_SIZE"),
    },
)
