"""Model card of a surrogate: what was trained, on what, and measured against what.

A published number about a surrogate ("MAE 1.19", "sign agreement 0.68") is only
checkable if one can tell which weights, which training data and which reference
produced it. :class:`SurrogateCard` records exactly that, and round-trips through JSON
so that it can sit next to the results it describes.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING

import numpy as np

from archlux._version import __version__

if TYPE_CHECKING:
    from archlux.arrays import FloatVector
    from archlux.light.reference import ReferenceMeasure
    from archlux.types import Orientation

__all__ = ["SurrogateCard", "surrogate_card", "training_fingerprint"]


def training_fingerprint(
    xs: Sequence[FloatVector], ys: FloatVector, orientations: Sequence[Orientation]
) -> str:
    """SHA-256 of the training data, independent of the platform's float formatting.

    Parameters
    ----------
    xs : sequence of numpy.ndarray
        Decision vectors.
    ys : numpy.ndarray
        Targets.
    orientations : sequence of Orientation
        Azimuths.

    Returns
    -------
    str
        Hex digest over the float64 bytes of every array, in order.
    """
    digest = hashlib.sha256()
    for x in xs:
        digest.update(np.ascontiguousarray(x, dtype=np.float64).tobytes())
    digest.update(np.ascontiguousarray(ys, dtype=np.float64).tobytes())
    digest.update(np.array([o.deg for o in orientations], dtype=np.float64).tobytes())
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class SurrogateCard:
    """Provenance of a surrogate and of the metrics reported about it.

    Attributes
    ----------
    model : str
        Class name of the surrogate.
    archlux_version : str
        Library version that trained it.
    weights_fingerprint : str
        SHA-256 of the frozen weights, ``""`` for a closed form.
    training_fingerprint : str
        :func:`training_fingerprint` of the training set.
    n_train : int
        Training plans.
    training_ids : tuple of str
        Their ids: the cases :func:`~archlux.light.evaluation.evaluate_surrogate` refuses.
    label_engine : str
        Engine that produced the training labels.
    label_kind : str
        ``"physical"`` or ``"closed_form"``.
    label_parameters : tuple of tuple of str
        Parameters of the label engine.
    seed : int
        Training seed.
    hyperparameters : tuple of tuple of str
        Sorted ``(name, value)`` of the training.
    metrics : tuple of tuple of (str, float)
        Held-out metrics, by name.
    """

    model: str
    archlux_version: str
    weights_fingerprint: str
    training_fingerprint: str
    n_train: int
    training_ids: tuple[str, ...]
    label_engine: str
    label_kind: str
    label_parameters: tuple[tuple[str, str], ...]
    seed: int
    hyperparameters: tuple[tuple[str, str], ...] = ()
    metrics: tuple[tuple[str, float], ...] = ()

    def to_json(self) -> str:
        """Serialize, keys sorted.

        Returns
        -------
        str
            JSON text.
        """
        return json.dumps(asdict(self), sort_keys=True, indent=2)

    @classmethod
    def from_json(cls, text: str) -> SurrogateCard:
        """Read a card written by :meth:`to_json`.

        Parameters
        ----------
        text : str
            JSON text.

        Returns
        -------
        SurrogateCard
            The card, tuples restored.
        """
        raw = json.loads(text)
        for key in ("label_parameters", "hyperparameters", "metrics"):
            raw[key] = tuple(tuple(pair) for pair in raw[key])
        raw["training_ids"] = tuple(raw["training_ids"])
        return cls(**raw)


def surrogate_card(
    surrogate: object,
    *,
    xs: Sequence[FloatVector],
    ys: FloatVector,
    orientations: Sequence[Orientation],
    training_ids: Sequence[str],
    label: ReferenceMeasure,
    seed: int,
    hyperparameters: Mapping[str, object] | None = None,
    metrics: Mapping[str, float] | None = None,
) -> SurrogateCard:
    """Build the card of a trained surrogate.

    Parameters
    ----------
    surrogate : object
        The trained model; its ``weights_fingerprint`` is read when it has one.
    xs, ys, orientations : sequences
        Training data, as passed to ``fit``.
    training_ids : sequence of str
        Ids of the training plans.
    label : ReferenceMeasure
        One measure of the label engine, for its engine, kind and parameters.
    seed : int
        Training seed.
    hyperparameters : mapping, optional
        Training settings (epochs, learning rate...).
    metrics : mapping, optional
        Held-out metrics.

    Returns
    -------
    SurrogateCard
        The card.
    """
    weights = getattr(surrogate, "weights_fingerprint", "")
    return SurrogateCard(
        model=type(surrogate).__name__,
        archlux_version=__version__,
        weights_fingerprint=str(weights() if callable(weights) else weights),
        training_fingerprint=training_fingerprint(xs, ys, orientations),
        n_train=len(xs),
        training_ids=tuple(training_ids),
        label_engine=label.engine,
        label_kind=label.kind,
        label_parameters=label.parameters,
        seed=seed,
        hyperparameters=tuple(sorted((k, str(v)) for k, v in (hyperparameters or {}).items())),
        metrics=tuple(sorted((k, float(v)) for k, v in (metrics or {}).items())),
    )
