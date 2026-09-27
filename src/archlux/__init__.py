"""archlux: correct a generated plan towards geometric validity.

Public interface **only**. This file is deliberately short: anything that is not listed
here is internal and may change without notice.

Two guarantees of different kinds, never confused:

===============  =============  ==============================
Guarantee        Kind           Verification
===============  =============  ==============================
Geometric        **exact**      finite inspection, ``O(n²)``
Performance      probabilistic  conformal prediction, ≥ 1 − α
===============  =============  ==============================

Examples
--------
>>> import archlux as ax
>>> plan = ax.Plan.from_json("proposed.json")    # doctest: +SKIP
>>> q = ax.legalize(plan, ctx)                   # doctest: +SKIP
>>> q.certificate.geometry.valid                 # doctest: +SKIP
True
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from archlux._deprecation import Alias, lazy_aliases
from archlux._version import __version__
from archlux.errors import (
    DEPRECATED_NAMES as _DEPRECATED_EXCEPTIONS,
)
from archlux.errors import (
    ArchluxError,
    CalibrationLocked,
    GapNeedsTiling,
    GridNotRecoverable,
    InconsistentOrder,
    Infeasible,
    InvalidInput,
    InvalidSurrogate,
    InvariantViolation,
    MissingSeparation,
    ModelModified,
    UnsupportedInput,
)
from archlux.types import DEPRECATED_NAMES as _DEPRECATED_MODEL
from archlux.types import (
    Certificate,
    Context,
    GeometricProof,
    Opening,
    Orientation,
    PerformanceBound,
    Plan,
    Regulation,
    Room,
    Structure,
    Wall,
)

# Grouped by role, not sorted alphabetically: the structure of this list *is* the map of
# the public API. An alphabetical sort would mix exceptions and the data model.
# ``light`` / ``bench`` / ``feasibility``: loaded lazily through ``__getattr__`` so that
# ``import archlux`` pulls neither ``torch`` nor the benchmark.
__all__ = [  # noqa: RUF022
    # the public function: only one, that is the thesis of the project in the API
    "legalize",
    # data model; input and output go through Plan.from_json / Plan.to_json and not
    # through free functions: one single way to load a plan.
    "Plan",
    "Room",
    "Wall",
    "Opening",
    "Context",
    "Structure",
    "Orientation",
    "Regulation",
    "Certificate",
    "GeometricProof",
    "PerformanceBound",
    # exceptions
    "ArchluxError",
    "InconsistentOrder",
    "MissingSeparation",
    "Infeasible",
    "InvalidInput",
    "UnsupportedInput",
    "GridNotRecoverable",
    "GapNeedsTiling",
    "InvariantViolation",
    "CalibrationLocked",
    "ModelModified",
    "InvalidSurrogate",
    # public packages (lazy)
    "light",
    "bench",
    "feasibility",
    "__version__",
]

_LAZY = frozenset({"light", "bench", "feasibility"})

if TYPE_CHECKING:
    # For mypy and IDEs only: the runtime resolves these on first use (``__getattr__``).
    # Without them ``ax.light.Daylight`` was invisible to type checkers (PLAN.md 3.8).
    # ``bench`` is not listed: no module may import it (ARCHITECTURE.md §5), so it stays
    # dynamic (``Any``) for type checkers.
    import archlux.feasibility as feasibility
    import archlux.light as light
    from archlux.api import legalize as legalize

# ``legalize`` drags in numpy, scipy.sparse, shapely and ortools (about 1 s): it is
# resolved on first use, so that ``import archlux`` stays under 0.5 s (PLAN.md 3.13).
_LAZY_FUNCTIONS = {"legalize": "archlux.api"}


def _lazy_attribute(name: str) -> Any:  # noqa: ANN401 - a lazy module or function
    """Load ``light``, ``bench``, ``feasibility`` and ``legalize`` on first use."""
    # Local import: do not pollute ``dir(archlux)`` with ``importlib``.
    import importlib

    if name in _LAZY:
        return importlib.import_module(f"archlux.{name}")
    if name in _LAZY_FUNCTIONS:
        function = getattr(importlib.import_module(_LAZY_FUNCTIONS[name]), name)
        globals()[name] = function  # resolved once: later lookups skip __getattr__
        return function
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# The former French exception names (ADR 0001): deprecated aliases until 1.0.0, then the
# lazy attributes above for everything else, so a from-import warns only once.
__getattr__ = lazy_aliases(
    __name__,
    {
        old: Alias(globals()[new], f"archlux.{new}")
        for old, new in {**_DEPRECATED_EXCEPTIONS, **_DEPRECATED_MODEL}.items()
        if new in globals()  # only what the root exports (not Manifest, ModelTrace)
    },
    fallback=_lazy_attribute,
)


def __dir__() -> list[str]:
    """Expose only the frozen public API (lazy packages included)."""
    return list(__all__)


# Note: ``light.appris``, ``solve`` and ``uq`` are NOT imported here.
# ``import archlux`` must load neither ``torch`` nor a model: this is checked by
# ``tests/test_dependances.py`` and blocks the CI.
