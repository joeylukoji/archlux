"""Couche 2b — substituts d'éclairement, seule couche apprise du projet.

N'importe jamais ``geom``, ``lmo`` ni ``solve`` : ne voit qu'un vecteur et un azimut.

``import archlux.light`` ne charge **pas** ``torch`` : ``appris`` reste un import
explicite ``archlux.light.appris``.
"""

from __future__ import annotations

import sys
import warnings
from typing import Any

from archlux.light.analytique import SubstitutAnalytique
from archlux.light.objectif import Daylight
from archlux.light.protocole import Substitut
from archlux.light.simulateur import SplitFluxOracle

__all__ = [
    "Daylight",
    "SplitFluxOracle",
    "Substitut",
    "SubstitutAnalytique",
]

_DEPRECATED = frozenset({"SimulateurExact", "ExactSimulator"})
"""Former names of :class:`SplitFluxOracle`: it is a frozen closed-form oracle, not a
simulator and not exact (PLAN.md batch 1.8). Kept until 1.0.0 (ADR 0001)."""


def __getattr__(name: str) -> Any:  # noqa: ANN401 — forwards a renamed attribute
    """Keep ``SimulateurExact`` and ``ExactSimulator`` until 1.0.0, deprecated."""
    if name in _DEPRECATED:
        if sys._getframe(1).f_code.co_filename.startswith("<frozen importlib"):
            # `from module import name` probes with hasattr first: warn only once.
            return SplitFluxOracle
        warnings.warn(
            f"archlux.light.{name} is deprecated, use archlux.light.SplitFluxOracle: "
            "a frozen split-flux oracle, neither a simulation nor ground truth (ADR 0001)",
            DeprecationWarning,
            stacklevel=2,
        )
        return SplitFluxOracle
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
