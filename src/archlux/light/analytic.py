"""Closed-form surrogate — **no learning at all**.

Its point is not accuracy: it is to run the whole chain in the third month rather than
the eighteenth. If the architecture is wrong, it is wrong here, before any money is spent
on simulation or training.

Implements :class:`archlux.light.protocol.Surrogate`. Vector input only.

The orientation factor goes through :func:`archlux.orient.circular.encode_orientation`:
never the raw degree. Formulas: ``docs/formulas/analytic-surrogate.md``.

This module imports neither ``geom`` nor ``lmo`` nor ``solve``: only a vector and an
azimuth (`ARCHITECTURE.md` §5).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import ClassVar

import numpy as np

from archlux._deprecation import Alias, lazy_aliases, renamed_attributes
from archlux.light.protocol import Glazing
from archlux.orient.circular import encode_orientation, sector
from archlux.types import Indicator, Orientation, indicator_sign

__all__ = ["SECTOR_FACTORS", "AnalyticSurrogate", "sector_factor"]

_EPS = 1e-12
_N_FIELDS = 4
"""Same contract as ``geom.polytope.FIELDS``: ``(x, y, w, h)`` per room. Duplicated
here so that ``light`` does not import ``geom``.
"""

SECTOR_FACTORS: tuple[float, ...] = (
    0.45,
    0.55,
    0.70,
    0.90,
    1.00,
    0.90,
    0.70,
    0.55,
)
"""Eight sectors N, NE, E, SE, S, SW, W, NW. South (180 degrees) is the most favourable.

**A workshop table, not a cited source.** These eight weights come from no standard:
CIBSE LG10 gives a limiting depth independent of the azimuth, and the BRE split-flux
works under a CIE overcast sky, hence without azimuth too. They encode the southern
preference of a northern-hemisphere climate so that the optimizer's argmax depends on
the orientation. An article must present them as a modelling prior, calibrated or
replaced by an annual simulation, never as the cited rule.
"""


def sector_factor(orientation: Orientation) -> float:
    """Exposure weight of the 45 degree sector that contains ``orientation``.

    Goes through :func:`archlux.orient.circular.encode_orientation`, never the raw degree:
    the azimuth is rebuilt from ``(cos, sin)``, hence continuous at 0 / 360.

    Parameters
    ----------
    orientation : Orientation
        Azimuth of the building.

    Returns
    -------
    float
        An element of :data:`SECTOR_FACTORS`, in ``[0.45, 1.00]``.
    """
    features = encode_orientation(orientation, harmonics=1)
    azimuth = float(np.degrees(np.arctan2(features[1], features[0]))) % 360.0
    return SECTOR_FACTORS[int(sector(azimuth, 8))]


@renamed_attributes(
    {
        "indicateur_vise": "target_indicator",
        "FACTEUR_PROFONDEUR": "DEPTH_FACTOR",
        "HAUTEUR_LINTEAU": "HEAD_HEIGHT",
        "KAPPA_SUD": "KAPPA_SOUTH",
        "FACTEURS_SECTEUR": "SECTOR_FACTORS",
    }
)
@dataclass(frozen=True, slots=True)
class AnalyticSurrogate:
    """Daylight factor model based on the limiting-depth rule.

    The depth beyond which a room stops being naturally lit depends strongly on the
    exposure: the model modulates this depth by the orientation, encoded circularly,
    and favours rooms placed towards geographic south (otherwise every orientation
    would give the same argmax).

    Attributes
    ----------
    target_indicator : {"sDA", "ASE", "UDI", "vue"}
        Quantity returned by :meth:`evaluate`. ASE is returned *negative* so that
        Frank-Wolfe, which maximizes, reduces glare.
    sigma_nominal : float
        Constant standard deviation. This surrogate does not model its own error.
    """

    target_indicator: Indicator = "sDA"
    sigma_nominal: float = 0.08

    DEPTH_FACTOR: ClassVar[float] = 2.5
    """Usual rule: useful depth ≈ 2.5 times the head height (CIBSE LG10)."""

    HEAD_HEIGHT: ClassVar[float] = 2.15
    """Typical head height, in metres. Uncertainty margin of the rule: ~30 %."""

    KAPPA_SOUTH: ClassVar[float] = 0.15
    """Weight, in 1/m, of a placement towards geographic south."""

    SECTOR_FACTORS: ClassVar[tuple[float, ...]] = SECTOR_FACTORS
    """Class alias of :data:`SECTOR_FACTORS` (public contract kept)."""

    @property
    def indicator(self) -> Indicator:
        """Name of the modelled indicator."""
        return self.target_indicator

    def evaluate(
        self, x: np.ndarray, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> float:
        """Estimate the indicator in closed form.

        ``glazing`` is **ignored**: this surrogate does not model fenestration, it
        assumes a constant glazed band. That is exactly what earns it
        ``R² = −0.000`` against a simulated irradiance.

        Guarantees
        ----------
        - Performance: **no guarantee by itself**. The value becomes bounded only
          after going through :mod:`archlux.uq.conformal`.
        """
        del glazing
        return float(self._score_and_gradient(x, orientation, with_gradient=False)[0])

    def gradient(
        self, x: np.ndarray, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> np.ndarray:
        """Analytic gradient, derived by hand then validated by finite differences.

        **Exact** everywhere except in two places, both of measure zero: at the kink
        ``depth == useful_depth`` (the left derivative is kept) and below the thresholds
        ``w < 1e-12`` / ``h < 1e-12``, where ``evaluate`` clips but the written
        derivative ignores the clipping. Outside these points, the symbolic check gives
        strict equality with ``∂ evaluate / ∂ x``.
        """
        del glazing
        return self._score_and_gradient(x, orientation, with_gradient=True)[1]

    def uncertainty(
        self, x: np.ndarray, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> float:
        """Constant nominal standard deviation: this surrogate does not model its error."""
        del x, orientation, glazing
        return float(self.sigma_nominal)

    def evaluate_rooms(
        self, x: np.ndarray, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> np.ndarray:
        """Contribution of each room, before summation.

        ``evaluate`` is their sum, up to the sign of ASE. See
        :class:`~archlux.light.protocol.PerRoomSurrogate`: 92 % of the variance of real
        daylight lives at this granularity.
        """
        del glazing
        return self._parts(x, orientation) * indicator_sign(self.target_indicator)

    def _parts(self, x: np.ndarray, orientation: Orientation) -> np.ndarray:
        """Positive score of each room, without the sign of the indicator."""
        vector = np.asarray(x, dtype=float).ravel()
        n_rooms = vector.size // _N_FIELDS
        features = encode_orientation(orientation, harmonics=1)
        cos_t, sin_t = float(features[0]), float(features[1])
        cos2, sin2 = cos_t * cos_t, sin_t * sin_t
        useful_depth = self.DEPTH_FACTOR * self.HEAD_HEIGHT * self._orientation_factor(orientation)
        parts = np.zeros(n_rooms, dtype=float)
        for i in range(n_rooms):
            base = i * _N_FIELDS
            pos_x, pos_y = float(vector[base]), float(vector[base + 1])
            width = max(float(vector[base + 2]), _EPS)
            height = max(float(vector[base + 3]), _EPS)
            south_facade = width * cos2 + height * sin2
            depth = width * sin2 + height * cos2
            penetration = min(depth, useful_depth)
            sudness = -pos_x * sin_t - pos_y * cos_t
            parts[i] = south_facade * penetration * math.exp(self.KAPPA_SOUTH * sudness)
        return parts

    def _orientation_factor(self, orientation: Orientation) -> float:
        """Eight-sector table. Delegates to :func:`sector_factor`, stateless."""
        return sector_factor(orientation)

    def _score_and_gradient(
        self, x: np.ndarray, orientation: Orientation, *, with_gradient: bool
    ) -> tuple[float, np.ndarray]:
        """Scalar score and, if asked, ∇x of the same scalar."""
        vector = np.asarray(x, dtype=float).ravel()
        n_rooms = vector.size // _N_FIELDS
        gradient = np.zeros_like(vector, dtype=float)

        features = encode_orientation(orientation, harmonics=1)
        cos_t = float(features[0])
        sin_t = float(features[1])
        cos2 = cos_t * cos_t
        sin2 = sin_t * sin_t
        useful_depth = self.DEPTH_FACTOR * self.HEAD_HEIGHT * self._orientation_factor(orientation)

        total = 0.0
        for i in range(n_rooms):
            base = i * _N_FIELDS
            pos_x, pos_y = float(vector[base]), float(vector[base + 1])
            width, height = float(vector[base + 2]), float(vector[base + 3])
            width = max(width, _EPS)
            height = max(height, _EPS)

            south_facade = width * cos2 + height * sin2
            depth = width * sin2 + height * cos2
            # min(depth, useful_depth): the penetration is continuous but **not
            # differentiable** at depth == useful_depth. The convention kept is the LEFT
            # derivative (d_pen_d_p = 1); on the right it is 0. At the exact kink, no
            # centred finite difference can recover the declared value: validate_gradient
            # checks signs there, not an equality.
            if depth <= useful_depth:
                penetration = depth
                d_pen_d_p = 1.0
            else:
                penetration = useful_depth
                d_pen_d_p = 0.0
            useful = south_facade * penetration

            sudness = -pos_x * sin_t - pos_y * cos_t
            south_weight = math.exp(self.KAPPA_SOUTH * sudness)
            score = useful * south_weight
            total += score

            if not with_gradient:
                continue

            d_u_d_l = penetration
            d_u_d_p = south_facade * d_pen_d_p
            d_u_d_w = d_u_d_l * cos2 + d_u_d_p * sin2
            d_u_d_h = d_u_d_l * sin2 + d_u_d_p * cos2

            kappa = self.KAPPA_SOUTH
            gradient[base] = score * kappa * (-sin_t)
            gradient[base + 1] = score * kappa * (-cos_t)
            gradient[base + 2] = d_u_d_w * south_weight
            gradient[base + 3] = d_u_d_h * south_weight

        sign = indicator_sign(self.target_indicator)
        return total * sign, gradient * sign


__getattr__ = lazy_aliases(
    __name__,
    {
        "FACTEURS_SECTEUR": Alias(SECTOR_FACTORS, "archlux.light.analytic.SECTOR_FACTORS"),
        "facteur_secteur": Alias(sector_factor, "archlux.light.analytic.sector_factor"),
        "SubstitutAnalytique": Alias(AnalyticSurrogate, "archlux.light.analytic.AnalyticSurrogate"),
    },
)
