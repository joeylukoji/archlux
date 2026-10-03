"""Learned surrogate — the only module of the project allowed to import ``torch``.

The import is local and lazy: ``import archlux`` must never load ``torch``, and
``tests/test_dependances.py`` makes that a blocking CI test.

This module knows neither ``geom``, nor ``lmo``, nor ``solve``: it sees only a vector
and an orientation, and returns a number, a gradient and an uncertainty.

As long as the weights are an ``npz`` of the perceptron
(:class:`~archlux.light.base.DenseSurrogate`), ``torch`` is not loaded. A ``.pt`` file
triggers the transformer.

Actual state of the transformer
-------------------------------
**It does not exist.** No architecture, no weights, no training in this repository.
:meth:`LearnedSurrogate._load_torch` **always** raises
:class:`~archlux.errors.InvariantViolation`, whatever the content of the ``.pt``: its
return type is ``NoReturn``, so the size check against :data:`MAX_PARAMETERS` it runs
first can only change the error message, never let a model through. The only learned
surrogate :class:`LearnedSurrogate` actually serves is the numpy perceptron of
:mod:`archlux.light.base`, loaded from an ``npz``.

Consequence for reading the results: every "learned surrogate" figure produced by this
repository comes from the dense perceptron on descriptors, never from a transformer on
tokens. Milestone 4 describes a target, not a delivered state.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn

from archlux._deprecation import Alias, lazy_aliases, renamed_attributes
from archlux.errors import InvariantViolation
from archlux.light.base import DenseSurrogate
from archlux.light.protocol import Glazing
from archlux.types import Indicator

if TYPE_CHECKING:
    import numpy as np

    from archlux.types import Indicator, Orientation

__all__ = ["MAX_PARAMETERS", "LearnedSurrogate"]

MAX_PARAMETERS = 2_000_000
"""Ceiling of `MILESTONE-4.md`: beyond it, the model memorizes out of distribution."""


@lru_cache(maxsize=8)
def _dense_from_disk(path: str, fingerprint: str) -> DenseSurrogate:
    """Load an ``npz`` once per ``(path, fingerprint)``, after a SHA-256 check."""
    current = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    if current != fingerprint:
        raise InvariantViolation((f"weights fingerprint mismatch for {path}",))
    return DenseSurrogate.load(Path(path))


@renamed_attributes(
    {
        "chemin_poids": "weights_path",
        "empreinte_poids": "weights_fingerprint",
        "gele": "frozen",
        "indicateur_vise": "target_indicator",
    }
)
@dataclass(frozen=True, slots=True)
class LearnedSurrogate:
    """Public head of the trained surrogate.

    Attributes
    ----------
    weights_fingerprint : str
        ``sha256`` of the weights, recorded in the manifest. Without it, a published
        result is not reproducible.
    frozen : bool
        Once the weights are frozen, access to the calibration set becomes possible —
        and not before (see :mod:`archlux.uq.registry`).
    """

    weights_path: Path
    weights_fingerprint: str
    frozen: bool = False
    target_indicator: Indicator = "sDA"

    @property
    def indicator(self) -> Indicator:
        """Name of the modelled indicator."""
        return self.target_indicator

    def _backend(self) -> DenseSurrogate:
        path = Path(self.weights_path)
        if path.suffix.lower() == ".pt":
            self._load_torch()
        return _dense_from_disk(str(path.resolve()), self.weights_fingerprint)

    def _load_torch(self) -> NoReturn:
        """Refuse a ``.pt``. ``torch`` is imported here only, and only then.

        Raises **unconditionally**: the transformer does not exist (see the module
        header). The check against :data:`MAX_PARAMETERS` is kept so that the error
        names the real cause when the file is also too large, but it gates no success
        path.
        """
        import torch

        state = torch.load(self.weights_path, map_location="cpu", weights_only=True)
        n_params = int(sum(p.numel() for p in state.values())) if isinstance(state, dict) else 0
        if n_params >= MAX_PARAMETERS:
            raise InvariantViolation((f"model too large: {n_params} ≥ {MAX_PARAMETERS}",))
        raise InvariantViolation(
            (".pt weights: the transformer is only served outside CI; use a dense npz",)
        )

    def evaluate(
        self, x: np.ndarray, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> float:
        """Estimate the indicator. Loads ``torch`` only for a ``.pt`` file."""
        return self._backend().evaluate(x, orientation, glazing=glazing)

    def gradient(
        self, x: np.ndarray, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> np.ndarray:
        """Finite-difference gradient of the backend, returned as ``numpy``."""
        return self._backend().gradient(x, orientation, glazing=glazing)

    def uncertainty(
        self, x: np.ndarray, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> float:
        """Learned predictive standard deviation."""
        return self._backend().uncertainty(x, orientation, glazing=glazing)

    def n_parameters(self) -> int:
        """Size of the loaded model."""
        return self._backend().n_parameters()


__getattr__ = lazy_aliases(
    __name__,
    {
        "MAX_PARAMETRES": Alias(MAX_PARAMETERS, "archlux.light.learned.MAX_PARAMETERS"),
        "SubstitutAppris": Alias(LearnedSurrogate, "archlux.light.learned.LearnedSurrogate"),
    },
)
