"""Couche 2b — substituts d'éclairement, seule couche apprise du projet.

N'importe jamais ``geom``, ``lmo`` ni ``solve`` : ne voit qu'un vecteur et un azimut.

``import archlux.light`` ne charge **pas** ``torch`` : ``appris`` reste un import
explicite ``archlux.light.appris``.
"""

from __future__ import annotations

from archlux._deprecation import Alias, lazy_aliases
from archlux.light.analytique import SubstitutAnalytique
from archlux.light.objectif import Daylight
from archlux.light.protocole import Surrogate
from archlux.light.simulateur import SplitFluxOracle

__all__ = [
    "Daylight",
    "SplitFluxOracle",
    "SubstitutAnalytique",
    "Surrogate",
]

_NOTE = "a frozen split-flux oracle, neither a simulation nor ground truth"
"""Former names of :class:`SplitFluxOracle`: it is a frozen closed-form oracle, not a
simulator and not exact (PLAN.md batch 1.8). Kept until 1.0.0 (ADR 0001)."""

__getattr__ = lazy_aliases(
    __name__,
    {
        **{
            old: Alias(SplitFluxOracle, "archlux.light.SplitFluxOracle", note=_NOTE)
            for old in ("SimulateurExact", "ExactSimulator")
        },
        "Substitut": Alias(Surrogate, "archlux.light.Surrogate"),
    },
)
