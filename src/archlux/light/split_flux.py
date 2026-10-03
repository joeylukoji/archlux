"""Daylight oracle — BRE split-flux, same ``Surrogate`` protocol.

The CI uses this closed form, **richer** than the analytic surrogate (CIBSE depth), so
that the network can beat it and the gradient checkpoint can run. A ray-tracing engine
(Radiance) is off the critical path.

The mean DF of a room follows Littlefair / BRE: window = WWR × lit facade (already in
the vector ``(w, h)``), without widening the ``Surrogate`` protocol.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

import numpy as np

from archlux._deprecation import Alias, lazy_aliases, renamed_attributes
from archlux.errors import InvariantViolation
from archlux.light.analytic import AnalyticSurrogate, sector_factor
from archlux.light.protocol import Glazing
from archlux.light.tokens import FIELDS_PER_ROOM
from archlux.orient.circular import encode_orientation
from archlux.types import Indicator, Orientation, indicator_sign

__all__ = ["SplitFluxOracle", "daylight_factor"]

_EPS = 1e-12
_TRANSMITTANCE = 0.70
_REFLECTANCE = 0.50
_SKY_THETA_DEG = 65.0
_CEILING_HEIGHT = 2.70
_GLAZING_HEIGHT = 1.15
_DEFAULT_WWR = 0.30
_REFLECTION_DENOM = 1.0 - _REFLECTANCE * _REFLECTANCE


def _south_facade(w: float, h: float, orientation: Orientation) -> float:
    """Facade length towards geographic south, same convention as the analytic surrogate."""
    features = encode_orientation(orientation, harmonics=1)
    cos2 = float(features[0]) ** 2
    sin2 = float(features[1]) ** 2
    return w * cos2 + h * sin2


def _facade_derivatives(orientation: Orientation) -> tuple[float, float]:
    """∂L/∂w and ∂L/∂h of the south facade."""
    features = encode_orientation(orientation, harmonics=1)
    cos2 = float(features[0]) ** 2
    sin2 = float(features[1]) ** 2
    return cos2, sin2


def daylight_factor(
    w: float,
    h: float,
    orientation: Orientation,
    *,
    wwr: float = _DEFAULT_WWR,
) -> float:
    """Mean daylight factor (a fraction, not an LM-83 sDA).

    BRE / Littlefair split-flux formula, overcast sky, window on the south facade:

    ``DF = T A_w θ / (A_surf (1 − R²))`` in percent, returned here as a fraction.

    Parameters
    ----------
    w, h : float
        Sides of the rectangle, in metres, same contract as the polytope.
    orientation : Orientation
        Azimuth of the building. Modulates the sky angle through the 8 sectors.
    wwr : float, optional
        Glazed band factor, in ``]0, 1]``. Default 0.30 (milestone 4 imputation).

    Returns
    -------
    float
        Mean relative daylight, in ``[0, 1]`` (2 % → ``0.02``).

    Notes
    -----
    Two deliberate departures from the cited source, to be declared in any publication:

    1. **θ depends on the azimuth here.** In BRE / Littlefair, θ is the visible sky
       angle, a purely geometric quantity (obstructions), and the CIE overcast sky is
       isotropic: the mean DF is **independent of the orientation** there. The
       ``sector_factor`` factor is a modelling prior added by archlux so that the
       optimizer tells azimuths apart; it takes the formula outside the frame where it
       is validated. ``θ = 65°`` (instead of 90° without obstruction) is likewise an
       unmeasured urban-obstruction assumption.
    2. **``wwr`` is not a window-to-wall ratio.** The window area here is
       ``wwr × 1.15 m × facade_length``: the height of the band is already in the
       formula, so ``wwr`` modulates it a second time. The effective WWR of
       ``wwr = 0.30`` on a 2.70 m storey is ``0.30 × 1.15 / 2.70 ≈ 0.13``. The parameter
       is a band coefficient, and should be renamed.
    """
    return _split_flux(w, h, orientation, wwr, with_gradient=False)[0]


def _split_flux(
    w: float,
    h: float,
    orientation: Orientation,
    wwr: float,
    *,
    with_gradient: bool,
) -> tuple[float, float, float]:
    """Fractional DF and, if asked, ∂DF/∂w and ∂DF/∂h."""
    if wwr <= 0.0 or wwr > 1.0:
        raise InvariantViolation((f"wwr outside ]0, 1]: {wwr}",))
    w = max(float(w), _EPS)
    h = max(float(h), _EPS)
    theta = _SKY_THETA_DEG * sector_factor(orientation)
    facade = max(_south_facade(w, h, orientation), _EPS)
    window_area = wwr * _GLAZING_HEIGHT * facade
    surface_area = 2.0 * w * h + 2.0 * (w + h) * _CEILING_HEIGHT
    numerator = _TRANSMITTANCE * window_area * theta
    denominator = max(surface_area * _REFLECTION_DENOM, _EPS)
    df_pct = numerator / denominator
    df = df_pct / 100.0
    if not with_gradient:
        return df, 0.0, 0.0
    dL_dw, dL_dh = _facade_derivatives(orientation)
    dAw_dw = wwr * _GLAZING_HEIGHT * dL_dw
    dAw_dh = wwr * _GLAZING_HEIGHT * dL_dh
    dAs_dw = 2.0 * h + 2.0 * _CEILING_HEIGHT
    dAs_dh = 2.0 * w + 2.0 * _CEILING_HEIGHT
    dnum_dw = _TRANSMITTANCE * theta * dAw_dw
    dnum_dh = _TRANSMITTANCE * theta * dAw_dh
    dden_dw = _REFLECTION_DENOM * dAs_dw
    dden_dh = _REFLECTION_DENOM * dAs_dh
    d_pct_dw = (dnum_dw * denominator - numerator * dden_dw) / (denominator * denominator)
    d_pct_dh = (dnum_dh * denominator - numerator * dden_dh) / (denominator * denominator)
    return df, d_pct_dw / 100.0, d_pct_dh / 100.0


@renamed_attributes({"indicateur_vise": "target_indicator", "ECHELLE_DF": "DF_SCALE"})
@dataclass(frozen=True, slots=True)
class SplitFluxOracle:
    """Frozen deterministic oracle: CIBSE analytic surrogate plus BRE split-flux daylight.

    A closed form, **not** a simulation and not ground truth: it lets the CI exercise
    the whole chain against a fixed reference. Formerly ``SimulateurExact``.

    The area × sin 2θ term (a toy) is replaced by a cited DF. For ``ASE``, the analytic
    surrogate already returns the opposite; the split-flux term is negated only once.
    """

    target_indicator: Indicator = "sDA"
    sigma_nominal: float = 0.04
    wwr: float = _DEFAULT_WWR
    DF_SCALE: ClassVar[float] = 100.0
    """Weight in m²·%: ``100 * DF * area`` to stay at the scale of the analytic surrogate.

    This ``100`` **exactly cancels** the division by 100 in ``daylight_factor``, which
    converts the DF from percent to a fraction. The term added to the score is therefore
    ``DF[%] * area[m2]``: a composite unit (m2 percent), not a normalized indicator. The
    fraction / percent round trip exists only to keep the public API of
    ``daylight_factor`` in fractions. The constant is therefore not a free setting:
    changing it would put the two scales out of step.
    """

    @property
    def indicator(self) -> Indicator:
        """Name of the target label. The scalar returned is not an LM-83 sDA."""
        return self.target_indicator

    def evaluate(
        self, x: np.ndarray, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> float:
        """Deterministic score. Two identical calls return the same float.

        ``glazing`` is ignored: the WWR is a constant of the model, not a reading of the
        actual fenestration.
        """
        del glazing
        return float(self._score_and_gradient(x, orientation, with_gradient=False)[0])

    def gradient(
        self, x: np.ndarray, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> np.ndarray:
        """Analytic gradient of the same score (CIBSE + split-flux)."""
        del glazing
        return self._score_and_gradient(x, orientation, with_gradient=True)[1]

    def uncertainty(
        self, x: np.ndarray, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> float:
        """Constant nominal standard deviation: no learned error."""
        del x, orientation, glazing
        return float(self.sigma_nominal)

    def evaluate_rooms(
        self, x: np.ndarray, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> np.ndarray:
        """Contribution of each room: analytic + split-flux, before summation.

        ``evaluate`` is their sum. See :class:`~archlux.light.protocol.PerRoomSurrogate`.
        """
        del glazing
        base = AnalyticSurrogate(target_indicator=self.target_indicator)
        parts = np.asarray(base.evaluate_rooms(x, orientation), dtype=float).copy()
        vector = np.asarray(x, dtype=float).ravel()
        sign = indicator_sign(self.target_indicator)
        for i in range(vector.size // FIELDS_PER_ROOM):
            width = float(vector[i * FIELDS_PER_ROOM + 2])
            height = float(vector[i * FIELDS_PER_ROOM + 3])
            df, _, _ = _split_flux(width, height, orientation, self.wwr, with_gradient=False)
            area = max(width, _EPS) * max(height, _EPS)
            parts[i] += sign * self.DF_SCALE * df * area
        return parts

    def _score_and_gradient(
        self, x: np.ndarray, orientation: Orientation, *, with_gradient: bool
    ) -> tuple[float, np.ndarray]:
        base = AnalyticSurrogate(target_indicator=self.target_indicator)
        value = float(base.evaluate(x, orientation))
        gradient = (
            np.asarray(base.gradient(x, orientation), dtype=float).copy()
            if with_gradient
            else np.zeros_like(np.asarray(x, dtype=float).ravel())
        )
        vector = np.asarray(x, dtype=float).ravel()
        n_rooms = vector.size // FIELDS_PER_ROOM
        extra_sign = indicator_sign(self.target_indicator)
        extra = 0.0
        for i in range(n_rooms):
            width = float(vector[i * FIELDS_PER_ROOM + 2])
            height = float(vector[i * FIELDS_PER_ROOM + 3])
            df, d_df_dw, d_df_dh = _split_flux(
                width, height, orientation, self.wwr, with_gradient=with_gradient
            )
            area = max(width, _EPS) * max(height, _EPS)
            extra += df * area
            if with_gradient:
                d_area_dw = max(height, _EPS)
                d_area_dh = max(width, _EPS)
                gradient[i * FIELDS_PER_ROOM + 2] += (
                    extra_sign * self.DF_SCALE * (d_df_dw * area + df * d_area_dw)
                )
                gradient[i * FIELDS_PER_ROOM + 3] += (
                    extra_sign * self.DF_SCALE * (d_df_dh * area + df * d_area_dh)
                )
        value += extra_sign * self.DF_SCALE * extra
        return value, gradient


__getattr__ = lazy_aliases(
    __name__,
    {
        "facteur_lumiere_jour": Alias(daylight_factor, "archlux.light.split_flux.daylight_factor"),
        "SimulateurExact": Alias(
            SplitFluxOracle,
            "SplitFluxOracle",
            note="a frozen split-flux oracle, neither a simulation nor ground truth",
        ),
    },
)
