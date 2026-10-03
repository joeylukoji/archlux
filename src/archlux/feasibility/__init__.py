"""Geometric feasibility of a program (exact proof, no daylight).

Business logic lives in :mod:`archlux.feasibility.verdict`; this root re-exports it
(PLAN.md phase 4, block 10, item 29).
"""

from __future__ import annotations

from archlux._deprecation import Alias, lazy_aliases
from archlux.feasibility.verdict import FeasibilityCertificate, Verdict, is_feasible

__all__ = ["FeasibilityCertificate", "Verdict", "is_feasible"]

__getattr__ = lazy_aliases(
    __name__,
    {
        "CertificatFaisabilite": Alias(
            FeasibilityCertificate, "archlux.feasibility.FeasibilityCertificate"
        ),
    },
)
