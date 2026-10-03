"""Layer 4, certificate: exact proof, probabilistic bound, dual diagnosis.

A lazy facade (PLAN.md phase 4, block 1): asking for one name imports only the module
that defines it, so a caller who only wants ``render`` does not pay for the proof or
the bound. ``dir()`` lists the public API (``__all__``) on purpose: submodules and
dunders are left out.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from archlux._deprecation import LazyAlias, lazy_aliases, lazy_module_attributes

if TYPE_CHECKING:
    from archlux.certify.borne import build_bound as build_bound
    from archlux.certify.dual import translate_duals as translate_duals
    from archlux.certify.proof import verify_exactly as verify_exactly
    from archlux.certify.rapport import render as render

__all__ = [
    "build_bound",
    "render",
    "translate_duals",
    "verify_exactly",
]

_ATTRS = {
    "build_bound": "archlux.certify.borne",
    "render": "archlux.certify.rapport",
    "translate_duals": "archlux.certify.dual",
    "verify_exactly": "archlux.certify.proof",
}

__getattr__ = lazy_aliases(
    __name__,
    {
        "verifier_exactement": LazyAlias(
            "archlux.certify.proof", "verify_exactly", "archlux.certify.verify_exactly"
        ),
        "construire_borne": LazyAlias(
            "archlux.certify.borne", "build_bound", "archlux.certify.build_bound"
        ),
        "rendre": LazyAlias("archlux.certify.rapport", "render", "archlux.certify.render"),
        "traduire_duaux": LazyAlias(
            "archlux.certify.dual", "translate_duals", "archlux.certify.translate_duals"
        ),
    },
    fallback=lazy_module_attributes(__name__, globals(), _ATTRS),
)


def __dir__() -> list[str]:
    """Expose only the frozen public API."""
    return list(__all__)
