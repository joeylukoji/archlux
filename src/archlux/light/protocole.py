"""``Surrogate`` protocol: the **only** interface between the pure core and the learned part.

Three methods, not one more. That narrowness is what allows three interchangeable
implementations (analytic with closed forms, learned with a transformer, and the
split-flux oracle) without ``solve`` knowing which one it handles.

`solve` depends on **this file**, never on :mod:`archlux.light.appris`. The dependency
test (`tests/test_dependances.py`) fails the CI if this rule is crossed.

**Vector input only.** A surrogate taking an image as input has a gradient of zero almost
everywhere: the optimizer goes blind and the project is impossible (`ARCHITECTURE.md`
§10, first anti-pattern).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from archlux._deprecation import Alias, lazy_aliases, renamed_parameters
from archlux.types import Indicator

if TYPE_CHECKING:
    from archlux.arrays import VecteurF
    from archlux.types import Opening, Orientation, Wall

__all__ = ["Glazing", "PerRoomSurrogate", "Surrogate", "WrapsSurrogate", "point_prediction"]


@dataclass(frozen=True, slots=True)
class Glazing:
    """Glazing of a plan, **invariant** during the optimization.

    The decision vector only carries ``(x, y, w, h)`` per room: it says **nothing** about
    the openings. Yet they are what determines daylight. Measured on 369 Swiss
    apartments, target = irradiance simulated by ray tracing, split by site: the analytic
    surrogate gets ``R² = −0.000`` and the perceptron ``R² = −0.667``, both at or below
    the plain mean. No model can do better from rectangles without windows; this is not a
    capacity defect, it is an input defect.

    Openings are described **relatively to their wall** (`ARCHITECTURE.md` §10) and do not
    move during Frank-Wolfe: only the partitions move, and the openings follow without
    synchronization. This object is therefore built once, at the start, and passed on
    unchanged to every iteration.

    Attributes
    ----------
    walls : tuple of Wall
        Walls carrying the openings. Needed to derive an absolute position on demand,
        never to store it.
    openings : tuple of Opening
        Openings, in relative coordinates ``(wall_id, s, relative_width)``.
    """

    walls: tuple[Wall, ...] = ()
    openings: tuple[Opening, ...] = ()

    @property
    def empty(self) -> bool:
        """Say whether no glazing is described.

        A surrogate that receives empty glazing must behave **exactly** as if it had
        received none: that is what makes the extension of the protocol backward
        compatible.
        """
        return not self.openings


@runtime_checkable
class PerRoomSurrogate(Protocol):
    """Surrogate that exposes its values **per room**, not only their sum.

    Why this protocol exists
    ------------------------
    :class:`Surrogate` returns **one scalar per plan**. Daylight is a **per-room**
    quantity, and the measurement is unambiguous: over 367,466 rooms of Swiss Dwellings,
    **92 % of the variance is within the apartment**. The identity of the building, which
    carries urban mask, climate and sun position, explains only 2.6 %.

    Aggregating to a dwelling mean therefore amounts to predicting a quantity whose
    variance is only 7.7 % of the phenomenon. That explains the measured ``R² ≈ 0``, more
    than the poverty of the inputs does.

    Consequence: **no sDA-type indicator is representable** by a plan scalar. The sDA is
    defined per room (share of the floor above 300 lux), never per dwelling.

    This protocol is **optional** and **additive**. ``solve`` keeps using only
    :class:`Surrogate`: the scalarization stays explicit and is the caller's job, which
    keeps an implicit mean from slipping into the optimization objective.
    """

    def evaluate_rooms(
        self, x: VecteurF, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> VecteurF:
        """Return one value per room, in the order of ``Polytope.index``.

        Returns
        -------
        numpy.ndarray
            Dimension ``len(x) // 4``: one value per room.

        Guarantees
        ----------
        - Consistency: the scalarization chosen by the implementation must give back
          :meth:`Surrogate.evaluate`. For the analytic surrogates of the repository this
          is the **sum**, checked by a test.
        """
        ...


@runtime_checkable
class Surrogate(Protocol):
    """Differentiable model of a daylight indicator.

    Every implementation honours three obligations:

    1. the input is the decision vector of the polytope, never a raster and, since the
       extension of the protocol, the :class:`Glazing` that goes with it;
    2. :meth:`gradient` is consistent with :meth:`evaluate`, checked by
       :func:`archlux.light.validation.validate_gradient`;
    3. :meth:`uncertainty` never returns a bare scalar without its scale.
    """

    @property
    def indicator(self) -> Indicator:
        """Name of the modelled indicator (``"sDA"``, ``"ASE"``, ...)."""
        ...

    def evaluate(
        self, x: VecteurF, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> float:
        """Estimate the indicator for the plan encoded by ``x``.

        Parameters
        ----------
        x : numpy.ndarray
            Decision vector, ordered by ``Polytope.index``.
        orientation : Orientation
            Azimuth, treated as a circular variable.
        glazing : Glazing or None, optional
            Glazing, constant during the optimization. ``None``, the default, means
            "information absent": the implementation must then fall back on its default
            assumption, as before the extension of the protocol. An implementation may
            ignore it.

        Returns
        -------
        float
            Point estimate. **No guarantee** in itself: the guarantee comes from
            :mod:`archlux.uq`, which attaches a conformal interval to it.

        Guarantees
        ----------
        - Performance: **probabilistic only**, and only once the value has gone through
          the conformal calibration. This method alone guarantees nothing.
        """
        ...

    def gradient(
        self, x: VecteurF, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> VecteurF:
        """Return ∂indicator/∂x, in the basis of the polytope.

        This is **all** that learning provides to the system: a direction. The generator
        decides the order, the solver decides the dimensions.

        Returns
        -------
        numpy.ndarray
            Same dimension as ``x``.
        """
        ...

    def uncertainty(
        self, x: VecteurF, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> float:
        """Predictive standard deviation, in the unit of the indicator.

        Serves as the non-conformity score of :mod:`archlux.uq.conforme` and as the
        sampling criterion of the active learning of milestone 6.
        """
        ...


@runtime_checkable
class WrapsSurrogate(Protocol):
    """An objective built on a surrogate, such as the pessimistic ``Daylight``.

    Its :meth:`Surrogate.evaluate` may return ``mu - q sigma`` rather than a prediction;
    ``surrogate`` gives access to the prediction itself (PLAN.md batch 1.6).
    """

    @property
    def surrogate(self) -> Surrogate:
        """The wrapped surrogate, whose ``evaluate`` is a point prediction."""
        ...


@renamed_parameters({"baies": "glazing"})
def point_prediction(
    objective: Surrogate, x: VecteurF, orientation: Orientation, *, glazing: Glazing | None = None
) -> tuple[float, float]:
    """Point prediction ``mu`` and uncertainty ``sigma`` behind an objective.

    ``mu`` is in the sign of the indicator (see below).

    A conformal interval is centred on the prediction, never on a pessimistic objective:
    centring it on ``mu - q sigma`` would subtract the margin twice. Every wrapping layer
    is removed, so that ``Daylight(Daylight(s))`` does not keep one margin.

    Surrogates return ASE **negated**, so that Frank-Wolfe, which maximizes, reduces
    glare (:class:`archlux.light.analytique.AnalyticSurrogate`). The prediction is
    given back as a positive ASE, the quantity the calibration and the report read.
    """
    surrogate: Surrogate = objective
    while isinstance(surrogate, WrapsSurrogate):
        surrogate = surrogate.surrogate
    mu = float(surrogate.evaluate(x, orientation, glazing=glazing))
    sigma = float(surrogate.uncertainty(x, orientation, glazing=glazing))
    if surrogate.indicator == "ASE":
        mu = -mu
    return mu, sigma


__getattr__ = lazy_aliases(
    __name__,
    {
        "Substitut": Alias(Surrogate, "archlux.light.protocole.Surrogate"),
        "Baies": Alias(Glazing, "archlux.light.protocole.Glazing"),
        "SubstitutParPiece": Alias(PerRoomSurrogate, "archlux.light.protocole.PerRoomSurrogate"),
    },
)
