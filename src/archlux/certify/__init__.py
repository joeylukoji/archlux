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
    from archlux.certify.bound import build_bound as build_bound
    from archlux.certify.dual import translate_duals as translate_duals
    from archlux.certify.proof import verify_exactly as verify_exactly
    from archlux.certify.repair import RoomChange as RoomChange
    from archlux.certify.repair import render_repair as render_repair
    from archlux.certify.repair import room_changes as room_changes
    from archlux.certify.report import render as render
    from archlux.certify.run import RunReport as RunReport
    from archlux.certify.run import run_repair as run_repair
    from archlux.certify.run import tally as tally
    from archlux.certify.validation import ValidationReport as ValidationReport
    from archlux.certify.validation import validate_plan as validate_plan

__all__ = [
    "RoomChange",
    "RunReport",
    "ValidationReport",
    "build_bound",
    "render",
    "render_repair",
    "room_changes",
    "run_repair",
    "tally",
    "translate_duals",
    "validate_plan",
    "verify_exactly",
]

_ATTRS = {
    "build_bound": "archlux.certify.bound",
    "render": "archlux.certify.report",
    "render_repair": "archlux.certify.repair",
    "room_changes": "archlux.certify.repair",
    "RoomChange": "archlux.certify.repair",
    "RunReport": "archlux.certify.run",
    "run_repair": "archlux.certify.run",
    "tally": "archlux.certify.run",
    "ValidationReport": "archlux.certify.validation",
    "validate_plan": "archlux.certify.validation",
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
            "archlux.certify.bound", "build_bound", "archlux.certify.build_bound"
        ),
        "rendre": LazyAlias("archlux.certify.report", "render", "archlux.certify.render"),
        "traduire_duaux": LazyAlias(
            "archlux.certify.dual", "translate_duals", "archlux.certify.translate_duals"
        ),
    },
    fallback=lazy_module_attributes(__name__, globals(), _ATTRS),
)


def __dir__() -> list[str]:
    """Expose only the frozen public API.

    Returns
    -------
    list of str
        The public names of the package.
    """
    return list(__all__)
