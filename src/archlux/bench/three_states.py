"""B9 cases in three states, and their CSV rows (AUDIT 2.2, ``experiments/b9_three_states.py``).

Builds, for each generated plan and azimuth, the initial plan, the classic legalization
(tiling, repair budget 16) and the archlux optimization (surrogate objective, 3 m budget
around the classic plan), as vectors with one shared room order, plus default facade
glazing. :func:`rows` turns :func:`archlux.light.three_states.compare_three_states` into
CSV rows.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from typing import Any

import numpy as np

from archlux.io.json_io import from_dict
from archlux.light.three_states import ThreeStates, facade_glazing
from archlux.types import Context, Orientation, Plan, Regulation, Structure

__all__ = ["HEADER", "b9_cases", "rows"]

HEADER = (
    "case",
    "reference",
    "ref_initial",
    "ref_classic",
    "ref_optimized",
    "pred_classic",
    "pred_optimized",
    "pred_gain_pct",
    "ref_gain_pct",
    "status",
)
"""Columns written by :func:`rows`."""


def _vector(plan: Plan, ids: list[str]) -> np.ndarray:
    """``(x, y, w, h)`` of the rooms ``ids``, in that order.

    Parameters
    ----------
    plan : Plan
        Plan to flatten.
    ids : list of str
        Room order shared by the three states.

    Returns
    -------
    numpy.ndarray
        The flat vector.
    """
    rooms = {r.id: r for r in plan.rooms}
    return np.array([v for i in ids for v in (rooms[i].x, rooms[i].y, rooms[i].w, rooms[i].h)])


def b9_cases(
    plans: Mapping[str, Mapping[str, Any]],
    objective: object,
    *,
    legalize: Callable[..., Plan],
    budget: float = 3.0,
) -> list[tuple[str, np.ndarray, np.ndarray, np.ndarray, Orientation, Any]]:
    """The three states of every plan at 8 azimuths.

    Parameters
    ----------
    plans : mapping
        ``results/j9_inputs.json``'s ``plans``: name -> entry with a ``proposed`` plan.
    objective : Surrogate
        Daylight objective of the optimization.
    legalize : callable
        :func:`archlux.legalize`, injected: ``bench`` does not import ``api``
        (``ARCHITECTURE.md`` §5).
    budget : float, optional
        Trust-region radius around the classic plan, in metres.

    Returns
    -------
    list of tuple
        ``(id, x_initial, x_classic, x_optimized, orientation, glazing)``, the input of
        :func:`archlux.light.three_states.compare_three_states`.
    """
    cases = []
    for name in sorted(plans):
        proposed = from_dict(dict(plans[name]["proposed"]))
        glazing, ids = facade_glazing(proposed.outline), sorted(r.id for r in proposed.rooms)
        kinds = tuple(sorted({r.type for r in proposed.rooms}))
        for azimuth in range(0, 360, 45):
            ctx = Context(
                Structure(()),
                Orientation(float(azimuth)),
                Regulation((), 0.50),
                outline=proposed.outline,
                program=kinds,
            )
            classic = legalize(proposed, ctx, tiling=True, repair_budget=16)
            best = legalize(classic, ctx, objective=objective, budget=budget)
            x0, x1, x2 = (_vector(p, ids) for p in (proposed, classic, best))
            cases.append((f"{name}/{azimuth}", x0, x1, x2, ctx.orientation, glazing))
    return cases


def rows(results: Iterable[ThreeStates]) -> list[tuple[str, ...]]:
    """CSV rows of :data:`HEADER`, values to four decimals.

    Parameters
    ----------
    results : iterable of ThreeStates
        Output of :func:`archlux.light.three_states.compare_three_states`.

    Returns
    -------
    list of tuple of str
        One row per case.
    """
    out = []
    for r in results:
        g = r.gain
        values = (
            r.reference_initial,
            r.reference_classic,
            r.reference_optimized,
            g.predicted_before,
            g.predicted_after,
            g.predicted_gain_pct,
            g.reference_gain_pct,
        )
        out.append((r.id, r.reference_kind, *(f"{v:.4f}" for v in values), r.status))
    return out
