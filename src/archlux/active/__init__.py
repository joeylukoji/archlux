"""Public exports of the ``active`` package."""

from __future__ import annotations

from archlux._deprecation import Alias, lazy_aliases
from archlux.active.densite import kernel_density
from archlux.active.loop import ActiveReport, Loop
from archlux.active.selection import RandomStrategy, UncertaintyTimesDensity

__all__ = [
    "ActiveReport",
    "Loop",
    "RandomStrategy",
    "UncertaintyTimesDensity",
    "kernel_density",
]

__getattr__ = lazy_aliases(
    __name__,
    {
        "Aleatoire": Alias(RandomStrategy, "archlux.active.RandomStrategy"),
        "RapportActif": Alias(ActiveReport, "archlux.active.ActiveReport"),
        "densite_noyau": Alias(kernel_density, "archlux.active.kernel_density"),
    },
)
