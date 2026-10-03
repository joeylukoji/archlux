"""Layer 2b — daylight surrogates, the only learned layer of the project.

Never imports ``geom``, ``lmo`` or ``solve``: it sees only a vector and an azimuth.

A lazy facade (PLAN.md phase 4, block 1): asking for one name imports only the module
that defines it. ``import archlux.light`` still loads no ``torch``; ``learned`` stays an
explicit import, ``archlux.light.learned``. ``dir()`` lists the public API (``__all__``)
on purpose: submodules and dunders are left out.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from archlux._deprecation import LazyAlias, lazy_aliases, lazy_module_attributes

if TYPE_CHECKING:
    from archlux.light.analytic import AnalyticSurrogate as AnalyticSurrogate
    from archlux.light.objective import Daylight as Daylight
    from archlux.light.protocol import Surrogate as Surrogate
    from archlux.light.split_flux import SplitFluxOracle as SplitFluxOracle

__all__ = [
    "AnalyticSurrogate",
    "Daylight",
    "SplitFluxOracle",
    "Surrogate",
]

_ATTRS = {
    "AnalyticSurrogate": "archlux.light.analytic",
    "Daylight": "archlux.light.objective",
    "Surrogate": "archlux.light.protocol",
    "SplitFluxOracle": "archlux.light.split_flux",
}

_NOTE = "a frozen split-flux oracle, neither a simulation nor ground truth"
"""Former names of :class:`SplitFluxOracle`: it is a frozen closed-form oracle, not a
simulator and not exact (PLAN.md batch 1.8). Kept until 1.0.0 (ADR 0001)."""

__getattr__ = lazy_aliases(
    __name__,
    {
        **{
            old: LazyAlias(
                "archlux.light.split_flux",
                "SplitFluxOracle",
                "archlux.light.SplitFluxOracle",
                note=_NOTE,
            )
            for old in ("SimulateurExact", "ExactSimulator")
        },
        "Substitut": LazyAlias("archlux.light.protocol", "Surrogate", "archlux.light.Surrogate"),
        "SubstitutAnalytique": LazyAlias(
            "archlux.light.analytic", "AnalyticSurrogate", "archlux.light.AnalyticSurrogate"
        ),
    },
    fallback=lazy_module_attributes(__name__, globals(), _ATTRS),
)


def __dir__() -> list[str]:
    """Expose only the frozen public API."""
    return list(__all__)
