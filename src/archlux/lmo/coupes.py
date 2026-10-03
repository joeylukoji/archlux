"""Deprecated module name: use :mod:`archlux.lmo.cuts` (ADR 0001, PLAN.md 3.9).

Every name of the old module stays reachable until 1.0.0 and emits a
``DeprecationWarning``: the classes and functions under their English names, and under the
French names they had before wave 5.
"""

from __future__ import annotations

import archlux.lmo.cuts as _cuts
from archlux._deprecation import Alias, lazy_aliases

__all__: list[str] = []

_RENAMED = {
    "Coupe": "Cut",
    "coupe_surface": "area_cut",
    "surfaces_violees": "violated_areas",
    "resoudre_avec_surfaces": "solve_with_areas",  # lang-ok: deprecated French alias name
    "MAX_COUPES_PAR_PIECE": "MAX_CUTS_PER_ROOM",
}
_NAMES = {**{name: name for name in _cuts.__all__}, **_RENAMED}

__getattr__ = lazy_aliases(
    __name__,
    {old: Alias(getattr(_cuts, new), f"archlux.lmo.cuts.{new}") for old, new in _NAMES.items()},
)
