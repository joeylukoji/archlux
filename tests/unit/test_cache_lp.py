"""``CacheLP``: an explicit, injectable LP model cache (PLAN.md phase 4, block 4).

Replaces a module-global dict keyed by ``id()``. The default cache (used when
``solve`` gets no explicit ``cache``) is still exercised by ``test_solver.py`` and
the warm-start benchmark; this file is about the object itself: isolation, eviction,
concurrent warm solves on one shared cache,
and that ``solve`` gives the identical result regardless of which cache serves it
(the whole point of PLAN.md 3.13's "warm start changes the time, not the answer").
"""

from __future__ import annotations

import threading

import numpy as np
import pytest

from archlux.geom.graph import RelativeOrder
from archlux.geom.polytope import build_polytope
from archlux.lmo.solver import CacheLP, solve
from archlux.types import Context, Orientation, Regulation, Structure

CTX = Context(
    structure=Structure(load_bearing_walls=()),
    orientation=Orientation(deg=0.0),
    outline=((0.0, 0.0), (10.0, 0.0), (10.0, 8.0), (0.0, 8.0)),
    regulation=Regulation(min_areas=(), min_width=1.5),
)
ORDER_AB = RelativeOrder(horizontal=(("A", "B"),), vertical=(), rooms=("A", "B"))
POLY_AB = build_polytope(ORDER_AB, CTX)


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
    polys = [build_polytope(ORDER_AB, CTX) for _ in range(3)]  # distinct objects, distinct ids
    for poly in polys:
        cache.put(poly, object(), [], [])
    assert cache.get(polys[0]) is None  # evicted first
    assert cache.get(polys[1]) is not None
    assert cache.get(polys[2]) is not None


def test_maxsize_below_one_is_rejected() -> None:
    with pytest.raises(ValueError, match="maxsize"):
        CacheLP(maxsize=0)


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

    # Warm path through the injected cache: a second solve with ``start`` and a
    # different objective reuses the model built above and must match a cold solve.
    c2 = np.zeros(len(POLY_AB.index))
    c2[POLY_AB.index["B.w"]] = -1.0
    cache = CacheLP()
    first = solve(POLY_AB, c=c, cache=cache)
    warm = solve(POLY_AB, c=c2, start=first.x, cache=cache)
    cold = solve(POLY_AB, c=c2, cache=CacheLP())
    np.testing.assert_array_equal(warm.x, cold.x)
    assert warm.value == cold.value


def test_concurrent_warm_solves_on_one_shared_cache_keep_their_own_objective() -> None:
    """Threads warm-starting on the same polytope through one shared cache must not
    overwrite each other's objective on the cached GLOP model (review of PR #22)."""
    n_threads, rounds = 8, 40
    names = sorted(POLY_AB.index)
    objectives = []
    for i in range(n_threads):
        c = np.zeros(len(POLY_AB.index))
        c[POLY_AB.index[names[i % len(names)]]] = -1.0 if i % 2 == 0 else 1.0
        objectives.append(c)
    expected = [solve(POLY_AB, c=c, cache=CacheLP()) for c in objectives]
    x0 = expected[0].x
    shared = CacheLP()
    solve(POLY_AB, c=objectives[0], cache=shared)  # warm the shared model
    barrier = threading.Barrier(n_threads)
    failures: list[str] = []

    def worker(i: int) -> None:
        for r in range(rounds):
            barrier.wait()
            got = solve(POLY_AB, c=objectives[i], start=x0, cache=shared)
            if got.value != expected[i].value or not np.array_equal(got.x, expected[i].x):
                failures.append(f"thread {i} round {r}: {got.value} != {expected[i].value}")

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not failures, failures[:5]
