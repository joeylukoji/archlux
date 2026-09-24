"""French names of ``Trace`` stay available, deprecated, until 1.0.0 (ADR 0001)."""

from __future__ import annotations

import numpy as np
import pytest

from archlux.solve.trace import Iteration, Trace

_TRACE = Trace(
    iterations=tuple(
        Iteration(
            k=k,
            value=float(k),
            gap=1.0 / (k + 2),
            step=0.5,
            away_step=False,
            lp_ms=2.0,
            n_cuts=0,
            x=np.full(4, float(k)),
        )
        for k in range(-1, 3)
    ),
    status="max_iter",
    final_gap=0.25,
)


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("iteres", "iterates"),
        ("ecarts", "gaps"),
        ("objectif", "values"),
        ("temps_lp_total_ms", "total_lp_ms"),
    ],
)
def test_old_names_warn_and_return_the_same_data(old: str, new: str) -> None:
    with pytest.warns(DeprecationWarning, match=f"Trace.{old} is deprecated, use Trace.{new}"):
        legacy = getattr(_TRACE, old)
    current = getattr(_TRACE, new)
    if isinstance(current, tuple) and current and isinstance(current[0], np.ndarray):
        assert all(np.array_equal(a, b) for a, b in zip(legacy, current, strict=True))
    else:
        assert legacy == current


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("valeur", "value"),
        ("pas", "step"),  # lang-ok: deprecated French alias under test
        ("temps_lp_ms", "lp_ms"),
        ("n_coupes", "n_cuts"),
    ],
)
def test_old_iteration_names_warn_and_return_the_same_data(old: str, new: str) -> None:
    """Review M3: Plan.trace.iterations[i] is public too."""
    step = _TRACE.iterations[1]
    with pytest.warns(DeprecationWarning, match=f"Iteration.{old} is deprecated"):
        legacy = getattr(step, old)
    assert legacy == getattr(step, new)
