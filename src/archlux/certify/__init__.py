"""Layer 4, certificate: exact proof, probabilistic bound, dual diagnosis."""

from __future__ import annotations

from archlux._deprecation import Alias, lazy_aliases
from archlux.certify.borne import build_bound
from archlux.certify.dual import translate_duals
from archlux.certify.proof import verify_exactly
from archlux.certify.rapport import render

__all__ = [
    "build_bound",
    "render",
    "translate_duals",
    "verify_exactly",
]


__getattr__ = lazy_aliases(
    __name__,
    {
        "verifier_exactement": Alias(verify_exactly, "archlux.certify.verify_exactly"),
        "construire_borne": Alias(build_bound, "archlux.certify.build_bound"),
        "rendre": Alias(render, "archlux.certify.render"),
        "traduire_duaux": Alias(translate_duals, "archlux.certify.translate_duals"),
    },
)
