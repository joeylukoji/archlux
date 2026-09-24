"""Layer 4, certificate: exact proof, probabilistic bound, dual diagnosis."""

from __future__ import annotations

import warnings
from typing import Any

from archlux.certify.borne import construire_borne
from archlux.certify.dual import traduire_duaux
from archlux.certify.proof import verify_exactly
from archlux.certify.rapport import rendre

__all__ = [
    "construire_borne",
    "rendre",
    "traduire_duaux",
    "verify_exactly",
]


def __getattr__(name: str) -> Any:  # noqa: ANN401 — forwards a renamed attribute
    """Keep ``certify.verifier_exactement`` until 1.0.0, deprecated (ADR 0001)."""
    if name == "verifier_exactement":
        warnings.warn(
            "archlux.certify.verifier_exactement is deprecated, use "
            "archlux.certify.verify_exactly (ADR 0001)",
            DeprecationWarning,
            stacklevel=2,
        )
        return verify_exactly
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
