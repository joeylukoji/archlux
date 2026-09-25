"""Deprecated module name: use :mod:`archlux.errors` (ADR 0001, PLAN.md 3.9).

Every name of the old module stays reachable until 1.0.0 and emits a
``DeprecationWarning``: the classes under their English names, and under the French names
they had before wave 1 (``Infaisable`` is ``Infeasible``, and so on).
"""

from __future__ import annotations

import archlux.errors as _errors
from archlux._deprecation import Alias, lazy_aliases

__all__: list[str] = []

_NAMES = {**{name: name for name in _errors.__all__}, **_errors.DEPRECATED_NAMES}

__getattr__ = lazy_aliases(
    __name__,
    {old: Alias(getattr(_errors, new), f"archlux.errors.{new}") for old, new in _NAMES.items()},
)
