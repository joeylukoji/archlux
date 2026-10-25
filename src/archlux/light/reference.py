"""Reference evaluators: what a surrogate prediction is checked **against**.

A surrogate is differentiable and fast; a reference is what the paper may call a
measure. The two are kept apart in the types, never only in the prose:

- a **surrogate** (:class:`~archlux.light.protocol.Surrogate`) returns a prediction and a
  gradient. It is never a measure, whatever its accuracy;
- a **reference** (:class:`Reference`) returns a :class:`ReferenceMeasure` that names its
  engine, its unit, its parameters and its :data:`ReferenceKind`.

``ReferenceKind`` is the line that matters for a publication. ``"closed_form"`` (the
frozen split-flux oracle wrapped by :class:`ClosedFormReference`) is **not** a physical
measure: a gain confirmed by it is a gain of one formula confirmed by another formula.
Only a ``"physical"`` reference (a ray tracer such as
:class:`archlux.light.radiance.RadianceReference`) may confirm a daylight gain.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, Protocol, runtime_checkable

from archlux.errors import ArchluxError

if TYPE_CHECKING:
    from archlux.arrays import FloatVector
    from archlux.light.protocol import Glazing, Surrogate
    from archlux.types import Orientation

__all__ = [
    "ClosedFormReference",
    "Reference",
    "ReferenceEvaluator",
    "ReferenceKind",
    "ReferenceMeasure",
    "ReferenceUnavailable",
]

ReferenceKind = Literal["physical", "closed_form"]
"""``"physical"``: a simulation of light transport. ``"closed_form"``: a formula."""


class ReferenceUnavailable(ArchluxError):
    """The reference cannot measure this plan here: missing engine or missing input.

    Raised instead of returning a made-up number. A caller that catches it records
    "not measured", never a value.

    Parameters
    ----------
    detail : str
        Why the reference cannot run.
    """

    def __init__(self, detail: str = "reference unavailable") -> None:
        """Compose the message.

        Parameters
        ----------
        detail : str
            Why the reference cannot run.
        """
        self.detail = detail
        super().__init__(detail)


@dataclass(frozen=True, slots=True)
class ReferenceMeasure:
    """One value measured by a reference, with everything needed to reproduce it.

    Attributes
    ----------
    value : float
        The scalar measured for the plan, in ``unit``.
    unit : str
        Unit of ``value`` (``"lux"``, ``"score"``...). Errors between a surrogate and a
        reference are only computed when both are in the same unit.
    kind : ReferenceKind
        ``"physical"`` or ``"closed_form"``.
    engine : str
        Name and version of the engine.
    parameters : tuple of tuple of str
        Sorted ``(name, value)`` pairs: sky, climate, ambient parameters...
    per_room : tuple of float
        One value per room, in plan order, when the engine provides it.
    """

    value: float
    unit: str
    kind: ReferenceKind
    engine: str
    parameters: tuple[tuple[str, str], ...] = ()
    per_room: tuple[float, ...] = field(default=())


@runtime_checkable
class Reference(Protocol):
    """An evaluator that measures, rather than predicts, a daylight quantity."""

    @property
    def kind(self) -> ReferenceKind:
        """``"physical"`` or ``"closed_form"``."""
        ...

    @property
    def unit(self) -> str:
        """Unit of the measured value."""
        ...

    def measure(
        self, x: FloatVector, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> ReferenceMeasure:
        """Measure the plan encoded by ``x``.

        Parameters
        ----------
        x
            Decision vector, ``(x, y, w, h)`` per room.
        orientation
            Azimuth of the plan.
        glazing
            Openings of the plan, or ``None``.

        Returns
        -------
        ReferenceMeasure
            The measure and its provenance.

        Raises
        ------
        ReferenceUnavailable
            The engine is missing, or the plan lacks an input the engine needs.
        """
        ...


@dataclass(frozen=True, slots=True)
class ClosedFormReference:
    """A frozen closed-form oracle used as a reference, and labelled as such.

    It lets the CI run every comparison end to end; the measures it returns carry
    ``kind="closed_form"``, so that no table built from them can read as a physical
    confirmation.

    Attributes
    ----------
    oracle : Surrogate
        Deterministic closed form, typically
        :class:`~archlux.light.split_flux.SplitFluxOracle`.
    engine : str
        Name written in every measure.
    """

    oracle: Surrogate
    engine: str = "SplitFluxOracle (closed form, not a simulation)"

    @property
    def kind(self) -> ReferenceKind:
        """Always ``"closed_form"``.

        Returns
        -------
        ReferenceKind
            ``"closed_form"``.
        """
        return "closed_form"

    @property
    def unit(self) -> str:
        """The oracle's own score: the same unit as the surrogates trained on it.

        Returns
        -------
        str
            ``"score"``.
        """
        return "score"

    def measure(
        self, x: FloatVector, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> ReferenceMeasure:
        """Evaluate the oracle and label the value as a closed-form reference.

        Parameters
        ----------
        x
            Decision vector of the plan.
        orientation
            Azimuth of the plan.
        glazing
            Passed on to the oracle.

        Returns
        -------
        ReferenceMeasure
            ``kind="closed_form"``, ``unit="score"``.
        """
        value = float(self.oracle.evaluate(x, orientation, glazing=glazing))
        return ReferenceMeasure(
            value=value,
            unit=self.unit,
            kind=self.kind,
            engine=self.engine,
            parameters=(("indicator", str(self.oracle.indicator)),),
        )


@dataclass(frozen=True, slots=True)
class ReferenceEvaluator:
    """Adapter exposing ``Reference.measure(...).value`` as an ``evaluate`` method.

    Finite differences and step audits only need a scalar function; this adapter lets
    them run on any reference without knowing its protocol.

    Attributes
    ----------
    reference : Reference
        The wrapped reference.
    """

    reference: Reference

    def evaluate(
        self, x: FloatVector, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> float:
        """Measured value of the plan.

        Parameters
        ----------
        x
            Decision vector of the plan.
        orientation
            Azimuth of the plan.
        glazing
            Openings of the plan, or ``None``.

        Returns
        -------
        float
            ``reference.measure(x, orientation, glazing=glazing).value``.
        """
        return self.reference.measure(x, orientation, glazing=glazing).value
