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

import warnings
from typing import Any

from archlux.certify import proof as _proof

__all__ = ["TOLERANCE_JOUR_M2", "verifier_exactement"]  # noqa: F822 — resolved lazily

_RENAMED = {
    "verifier_exactement": "verify_exactly",
    "TOLERANCE_JOUR_M2": "GAP_TOLERANCE_M2",
}


def __getattr__(name: str) -> Any:  # noqa: ANN401 — forwards any renamed attribute
    """Forward a renamed public name to :mod:`archlux.certify.proof`, with a warning."""
    new = _RENAMED.get(name)
    if new is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    warnings.warn(
        f"archlux.certify.preuve.{name} is deprecated, use archlux.certify.proof.{new} (ADR 0001)",
        DeprecationWarning,
        stacklevel=2,
    )
    return getattr(_proof, new)
