"""``CacheLP``: an explicit, injectable LP model cache (PLAN.md phase 4, block 4).

Replaces a module-global dict keyed by ``id()``. The default cache (used when
``solve`` gets no explicit ``cache``) is still exercised by ``test_solveur.py`` and
the warm-start benchmark; this file is about the object itself: isolation, eviction,
and that ``solve`` gives the identical result regardless of which cache serves it
(the whole point of PLAN.md 3.13's "warm start changes the time, not the answer").
"""

from __future__ import annotations

import threading

import numpy as np

from archlux.geom.graphe import RelativeOrder
from archlux.geom.polytope import build_polytope
from archlux.lmo.solveur import CacheLP, solve
from archlux.types import Context, Orientation, Regulation, Structure

CTX = Context(
    structure=Structure(load_bearing_walls=()),
    orientation=Orientation(deg=0.0),
    outline=((0.0, 0.0), (10.0, 0.0), (10.0, 8.0), (0.0, 8.0)),
    regulation=Regulation(min_areas=(), min_width=1.5),
)
ORDRE_AB = RelativeOrder(horizontal=(("A", "B"),), vertical=(), rooms=("A", "B"))
POLY_AB = build_polytope(ORDRE_AB, CTX)


def test_a_fresh_cache_starts_empty() -> None:
    assert CacheLP().get(POLY_AB) is None


def test_put_then_get_returns_the_same_objects() -> None:
    cache = CacheLP()
    model = (object(), [object()], [object()])
    cache.put(POLY_AB, *model)
    assert cache.get(POLY_AB) == model


def test_clear_empties_the_cache() -> None:
    cache = CacheLP()
    cache.put(POLY_AB, object(), [], [])
    cache.clear()
    assert cache.get(POLY_AB) is None


def test_eviction_drops_the_oldest_beyond_maxsize() -> None:
    cache = CacheLP(maxsize=2)
    polys = [build_polytope(ORDRE_AB, CTX) for _ in range(3)]  # distinct objects, distinct ids
    for poly in polys:
        cache.put(poly, object(), [], [])
    assert cache.get(polys[0]) is None  # evicted first
    assert cache.get(polys[1]) is not None
    assert cache.get(polys[2]) is not None


def test_two_caches_do_not_see_each_other() -> None:
    """The isolation the object form buys over a module global."""
    a, b = CacheLP(), CacheLP()
    a.put(POLY_AB, object(), [], [])
    assert b.get(POLY_AB) is None


def test_solve_gives_the_same_answer_with_an_own_cache() -> None:
    """PLAN.md 3.13: the warm start (or which cache serves it) changes the time, never
    the answer."""
    c = np.zeros(len(POLY_AB.index))
    c[POLY_AB.index["A.w"]] = -1.0
    default = solve(POLY_AB, c=c)
    own_cache = solve(POLY_AB, c=c, cache=CacheLP())
    np.testing.assert_array_equal(default.x, own_cache.x)
    assert default.value == own_cache.value
    assert default.status == own_cache.status


def test_concurrent_put_does_not_corrupt_the_cache() -> None:
    """A global dict was not safe if two threads solved on different polytopes at
    once; an instance with its own lock is (PLAN.md phase 4, block 4)."""
    cache = CacheLP(maxsize=50)
    polys = [build_polytope(ORDRE_AB, CTX) for _ in range(50)]

    def worker(poly: object) -> None:
        cache.put(poly, object(), [], [])  # type: ignore[arg-type]

    threads = [threading.Thread(target=worker, args=(poly,)) for poly in polys]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert all(cache.get(poly) is not None for poly in polys)
