"""Layer 4, certificate: exact proof, probabilistic bound, dual diagnosis."""

from __future__ import annotations

from archlux._deprecation import Alias, lazy_aliases
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


__getattr__ = lazy_aliases(
    __name__,
    {"verifier_exactement": Alias(verify_exactly, "archlux.certify.verify_exactly")},
)
