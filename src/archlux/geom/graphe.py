"""Deprecated module name: use :mod:`archlux.geom.graph` (ADR 0001).

Every public name of the new module, and every former French name it still serves, stays
reachable here until 1.0.0 and emits a ``DeprecationWarning`` naming the new path.
"""

from __future__ import annotations

from archlux._deprecation import module_shim

__all__: list[str] = []

__getattr__ = module_shim(__name__, "archlux.geom.graph")
