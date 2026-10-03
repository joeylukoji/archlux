"""Array type alias shared by every layer (PLAN.md 3.8).

``np.ndarray`` appears about 170 times in ``src/`` with no dtype: a bool mask, an int index
and a float vector read the same. ``FloatVector`` names the case that matters, a float64
array (decision vector, gradient, dual prices, scores), in the signatures of the numerical
core.

**Limit, measured**: mypy 1.19 with numpy 2.4 does not compare dtypes at all (it accepts
``NDArray[np.str_] = np.zeros(3)``), so today this alias documents the intent and is
checked by dtype-aware checkers (pyright), not by ``mypy --strict``.

A leaf module: it imports only numpy, and every layer may import it (numpy is already a
dependency of the whole core).
"""

from __future__ import annotations

import warnings
from typing import TypeAlias

import numpy as np
from numpy.typing import NDArray

__all__ = ["FloatVector"]

FloatVector: TypeAlias = NDArray[np.float64]
"""A float64 array of any shape: a vector, or a matrix. numpy's typing does not track the
number of dimensions, so one alias serves both."""


def __getattr__(name: str) -> object:
    """Serve the French name ``VecteurF`` until 1.0.0, with a ``DeprecationWarning``.

    Written by hand rather than with :func:`archlux._deprecation.lazy_aliases`: this
    module is a leaf and imports nothing from archlux.
    """
    if name == "VecteurF":  # lang-ok: deprecated French alias (ADR 0001, rule 6)
        warnings.warn(
            "archlux.arrays.VecteurF is deprecated, use archlux.arrays.FloatVector (ADR 0001)",
            DeprecationWarning,
            stacklevel=2,
        )
        return FloatVector
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
