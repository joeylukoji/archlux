"""Couche 2b — substituts d'éclairement, seule couche apprise du projet.

N'importe jamais ``geom``, ``lmo`` ni ``solve`` : ne voit qu'un vecteur et un azimut.

``import archlux.light`` ne charge **pas** ``torch`` : ``appris`` reste un import
explicite ``archlux.light.appris``.
"""

from __future__ import annotations

from archlux.light.analytique import SubstitutAnalytique
from archlux.light.objectif import Daylight
from archlux.light.protocole import Substitut
from archlux.light.simulateur import SimulateurExact

ExactSimulator = SimulateurExact

__all__ = [
    "Daylight",
    "ExactSimulator",
    "SimulateurExact",
    "Substitut",
    "SubstitutAnalytique",
]
