"""Deprecated module name: use :mod:`archlux.certify.proof` (ADR 0001).

The French public names stay available until 1.0.0 and emit a ``DeprecationWarning``:

=======================  =============================
Old name                 New name
=======================  =============================
``verifier_exactement``  ``proof.verify_exactly``
``TOLERANCE_JOUR_M2``    ``proof.GAP_TOLERANCE_M2``
=======================  =============================
"""

from __future__ import annotations

from archlux._deprecation import Alias, lazy_aliases
from archlux.certify import proof as _proof

__all__ = ["TOLERANCE_JOUR_M2", "verifier_exactement"]  # noqa: F822 — resolved lazily

__getattr__ = lazy_aliases(
    __name__,
    {
        "verifier_exactement": Alias(_proof.verify_exactly, "archlux.certify.proof.verify_exactly"),
        "TOLERANCE_JOUR_M2": Alias(
            _proof.GAP_TOLERANCE_M2, "archlux.certify.proof.GAP_TOLERANCE_M2"
        ),
    },
)
