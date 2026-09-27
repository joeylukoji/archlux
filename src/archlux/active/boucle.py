"""Active loop: select -> simulate -> retrain -> recalibrate.

The delicate point is the **training / calibration separation**. A point simulated
by the loop cannot serve both purposes: `ARCHITECTURE.md` §10 makes it the only
silent error capable of invalidating a publication. Two modes follow from this:

- ``run(..., calibration=...)`` -- an **independent** set, drawn outside the loop.
  The only mode whose coverage is publishable;
- otherwise, a fraction ``part_calibration`` of the acquired points is set aside and
  never enters ``fit``. The separation holds, but the points remain *selected*
  by the acquisition: ``ActiveReport.calibration_independante`` is then ``False``.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np
import structlog

from archlux._deprecation import Alias, lazy_aliases
from archlux.active.densite import kernel_density
from archlux.active.selection import AcquisitionStrategy
from archlux.errors import InvariantViolation
from archlux.seeds import derive
from archlux.uq.conforme import ConformalCalibrator, minimal_n_conformal

if TYPE_CHECKING:
    from archlux.light.protocole import Surrogate
    from archlux.types import Orientation

__all__ = ["ActiveReport", "Loop"]

_LOG = structlog.get_logger("archlux.active.boucle")


@dataclass(frozen=True, slots=True)
class ActiveReport:
    """Result of a campaign with a fixed simulation budget.

    Attributes
    ----------
    calibration_independante : bool
        True if the calibration comes from a set drawn **outside** the loop. False
        if it was drawn from the acquired points: the points are then chosen by
        the acquisition strategy, hence not exchangeable with a randomly drawn
        test set, and the associated coverage **is not publishable**.
    """

    n_simulations: int
    largeur_intervalle_finale: float
    q_final: float
    n_calibration: int
    historique_largeur: tuple[float, ...]
    calibration_independante: bool = False


def _empiler(xs: list[np.ndarray]) -> np.ndarray:
    """Stack plan vectors into a ``(n, d)`` matrix."""
    return np.stack([np.asarray(x, dtype=float).ravel() for x in xs])


def _incertitudes_acquisition(
    surrogate: Surrogate,
    xs: list[np.ndarray],
    orientations: list[Orientation],
    xs_labeled: list[np.ndarray],
) -> np.ndarray:
    """Surrogate σ̂ x (1 + distance to the nearest already-simulated point).

    A constant ``incertitude`` (e.g. ``DenseSurrogate``) does not discriminate:
    the distance to the already-labeled points forces exploration.
    """
    base = np.array(
        [float(surrogate.uncertainty(x, o)) for x, o in zip(xs, orientations, strict=True)],
        dtype=float,
    )
    if not xs_labeled:
        return np.asarray(np.maximum(base, 1e-12), dtype=float)
    ref = _empiler(xs_labeled)
    cand = _empiler(xs)
    dist2 = np.sum((cand[:, None, :] - ref[None, :, :]) ** 2, axis=2)
    dist = np.sqrt(np.min(dist2, axis=1))
    echelle = float(np.median(dist) + 1e-9)
    return np.asarray(np.maximum(base, 1e-12) * (1.0 + dist / echelle), dtype=float)


def _largeur_moyenne(
    calibrateur: ConformalCalibrator,
    surrogate: Surrogate,
    xs: list[np.ndarray],
    orientations: list[Orientation],
) -> float:
    """Mean width of the conformal intervals on the held-out set."""
    largeurs: list[float] = []
    for x, o in zip(xs, orientations, strict=True):
        pred = float(surrogate.evaluate(x, o))
        sigma = float(surrogate.uncertainty(x, o))
        # Held-out plans, never chosen by an optimizer: exchangeable by construction.
        borne = calibrateur.borne(pred, sigma, regime="exchangeable")
        largeurs.append(float(borne.upper - borne.lower))
    return float(np.mean(largeurs))


@dataclass(slots=True)
class Loop:
    """Acquisition campaign with a fixed simulation budget.

    Parameters
    ----------
    surrogate : Substitut
        Model to improve. If it exposes ``fit``, it is retrained every cycle.
    simulateur : Substitut
        Frozen oracle (e.g. ``SplitFluxOracle``).
    acquire : AcquisitionStrategy
        ``UncertaintyTimesDensity`` or ``RandomStrategy``.
    budget : int
        Total number of oracle evaluations **consumed by the acquisition**. The
        simulation of an independent ``calibration=`` set is counted separately.
    batch : int, optional
        Batch size per acquisition cycle.
    seed : int
        Root seed of the campaign. **Required, no default**, and keyword-only
        (`ARCHITECTURE.md` §7): ``Loop`` samples (``RandomStrategy``, ``fit``, the
        training / calibration split), and a default of ``17`` let campaigns pass
        silently that could not be replayed.
    alpha : float, optional
        Target conformal level (default 0.10 -> 90% coverage). Also sets the
        minimum calibration size, via :func:`~archlux.uq.conforme.minimal_n_conformal`.
    part_calibration : float, optional
        Fraction of the acquired points set aside for calibration when no
        independent set is supplied. ``0.0`` disables the set-aside -- ``calibration=``
        must then be passed, otherwise ``run`` raises.

    Warnings
    --------
    Without ``calibration=``, the calibration points are **chosen by the acquisition
    strategy**. They are indeed disjoint from those seen by ``fit`` -- the §10
    fault is avoided -- but they are not exchangeable with a randomly drawn test
    set. In this mode, ``run`` measures an **interval width**, a legitimate quantity
    for comparing two strategies at equal budget, and **not** a coverage.
    ``ActiveReport.calibration_independante`` carries the distinction.
    """

    surrogate: Surrogate
    simulateur: Surrogate
    acquire: AcquisitionStrategy
    budget: int
    batch: int = 5
    seed: int = field(kw_only=True)
    alpha: float = field(default=0.10, kw_only=True)
    part_calibration: float = field(default=0.30, kw_only=True)

    def __post_init__(self) -> None:
        """Validate budget, batch size, level, and calibration fraction."""
        if self.budget < 1:
            raise InvariantViolation(("budget must be >= 1",))
        if self.batch < 1:
            raise InvariantViolation(("batch must be >= 1",))
        if not 0.0 < self.alpha < 1.0:
            raise InvariantViolation((f"alpha out of ]0, 1[: {self.alpha}",))
        if not 0.0 <= self.part_calibration < 1.0:
            raise InvariantViolation((f"part_calibration out of [0, 1[: {self.part_calibration}",))

    def _calibrer(
        self,
        calibrateur: ConformalCalibrator,
        xs: list[np.ndarray],
        ys: list[float],
        orientations: list[Orientation],
    ) -> None:
        """Fit the conformal quantile on the calibration set, and only that set."""
        preds = np.array(
            [float(self.surrogate.evaluate(x, o)) for x, o in zip(xs, orientations, strict=True)]
        )
        sigmas = np.array(
            [float(self.surrogate.uncertainty(x, o)) for x, o in zip(xs, orientations, strict=True)]
        )
        calibrateur.fit(preds, np.asarray(ys, dtype=float), sigmas, alpha=self.alpha)

    def _repartir(self, n_acquis: int, rng: np.random.Generator, *, independante: bool) -> set[int]:
        """Ranks of the current batch to divert to calibration rather than training.

        The draw is **internal to the batch**: it therefore does not depend on the
        acquisition order, which goes from most exploratory to most exploitative.
        """
        if independante or self.part_calibration <= 0.0 or n_acquis < 1:
            return set()
        n_cal = min(n_acquis, max(1, round(self.part_calibration * n_acquis)))
        return {int(j) for j in rng.permutation(n_acquis)[:n_cal]}

    def run(
        self,
        propositions: list[np.ndarray],
        orientations: list[Orientation],
        *,
        reference_optimiseur: list[np.ndarray],
        holdout: list[np.ndarray] | None = None,
        holdout_orientations: list[Orientation] | None = None,
        calibration: list[np.ndarray] | None = None,
        calibration_orientations: list[Orientation] | None = None,
    ) -> ActiveReport:
        """Run the loop until the budget is exhausted.

        Parameters
        ----------
        propositions :
            Pool of candidates (vectorized).
        orientations :
            One orientation per candidate.
        reference_optimiseur :
            Typical plans produced by the optimizer -- basis of the density.
        holdout, holdout_orientations :
            Set used to measure the final interval width. Default: the candidates.
        calibration, calibration_orientations :
            **Independent** calibration set, simulated once at start-up and never
            passed to ``fit``. The only mode whose coverage is publishable.

        Returns
        -------
        ActiveReport
            ``calibration_independante`` says whether the associated coverage is
            publishable.

        Raises
        ------
        InvariantViolation
            Inconsistent inputs, or calibration too small for ``alpha``: it needs
            ``n >= n_minimal_conforme(alpha)``, i.e. 9 points at 90% coverage.
        """
        if len(propositions) != len(orientations):
            raise InvariantViolation(("propositions and orientations have distinct lengths",))
        if len(propositions) < self.batch:
            raise InvariantViolation(("pool smaller than the batch",))
        if not reference_optimiseur:
            raise InvariantViolation(("reference_optimiseur is empty",))

        hold_x = holdout if holdout is not None else propositions
        hold_o = holdout_orientations if holdout_orientations is not None else orientations
        if len(hold_x) != len(hold_o):
            raise InvariantViolation(("holdout and orientations have distinct lengths",))
        if not hold_x:
            raise InvariantViolation(("holdout is empty",))

        n_min = minimal_n_conformal(self.alpha)
        independante = calibration is not None
        xs_cal: list[np.ndarray] = []
        os_cal: list[Orientation] = []
        if calibration is not None:
            if calibration_orientations is None or len(calibration) != len(
                calibration_orientations
            ):
                raise InvariantViolation(
                    ("calibration and calibration_orientations have distinct lengths",)
                )
            if len(calibration) < n_min:
                raise InvariantViolation(
                    (f"calibration n={len(calibration)} < {n_min} required for alpha={self.alpha}",)
                )
            xs_cal = [np.asarray(x, dtype=float).copy() for x in calibration]
            os_cal = list(calibration_orientations)
        # Ground truth of the independent set: simulated once, outside the acquisition budget.
        ys_cal: list[float] = [
            float(self.simulateur.evaluate(x, o)) for x, o in zip(xs_cal, os_cal, strict=True)
        ]

        dens = kernel_density(_empiler(propositions), _empiler(reference_optimiseur))
        xs_lab: list[np.ndarray] = []
        ys_lab: list[float] = []
        os_lab: list[Orientation] = []
        exclus: list[int] = []
        historique: list[float] = []
        restantes = self.budget
        cycle = 0
        calibrateur = ConformalCalibrator(indicator="sDA")
        # Named sub-streams (AUDIT.md Q-M5): with ``seed + cycle`` the campaign of seed 17
        # at cycle 1 replayed the selection of the campaign of seed 18 at cycle 0.
        rng = np.random.default_rng(derive(self.seed, "split"))

        while restantes > 0:
            n_prendre = min(self.batch, restantes, len(propositions) - len(exclus))
            if n_prendre < 1:
                break
            inc = _incertitudes_acquisition(self.surrogate, propositions, orientations, xs_lab)
            idxs = self.acquire.selectionner(
                inc,
                dens,
                n=n_prendre,
                seed=derive(self.seed, f"selection/{cycle}"),
                exclus=np.asarray(exclus, dtype=int) if exclus else None,
            )
            acquis = [int(i) for i in idxs]
            # Split BEFORE any fitting: this is what physically prevents ``fit``
            # from ever seeing a calibration point.
            vers_calibration = self._repartir(len(acquis), rng, independante=independante)
            for rang, i in enumerate(acquis):
                x = np.asarray(propositions[i], dtype=float).copy()
                o = orientations[i]
                y = float(self.simulateur.evaluate(x, o))
                if rang in vers_calibration:
                    xs_cal.append(x)
                    ys_cal.append(y)
                    os_cal.append(o)
                else:
                    xs_lab.append(x)
                    ys_lab.append(y)
                    os_lab.append(o)
                exclus.append(i)
            restantes -= len(acquis)

            fit = getattr(self.surrogate, "fit", None)
            legacy_fit = getattr(self.surrogate, "ajuster", None)
            if fit is None and legacy_fit is not None:
                # A surrogate written before the English rename: still retrained, with a
                # warning, never silently left untrained (review of the stack, #12).
                warnings.warn(
                    f"{type(self.surrogate).__name__}.ajuster is deprecated, rename it fit",
                    DeprecationWarning,
                    stacklevel=2,
                )
                fit = legacy_fit
            if fit is not None and len(xs_lab) >= 2:
                fit(
                    tuple(xs_lab),
                    np.asarray(ys_lab, dtype=float),
                    tuple(os_lab),
                    seed=derive(self.seed, f"fit/{cycle}"),
                    epoques=40,
                    lr=0.12,
                )

            # Recalibrate after every cycle: the model has changed, the old q̂
            # no longer bounds anything. Scores come from ``xs_cal``, never from ``xs_lab``.
            if len(xs_cal) >= n_min:
                try:
                    self._calibrer(calibrateur, xs_cal, ys_cal, os_cal)
                    historique.append(_largeur_moyenne(calibrateur, self.surrogate, hold_x, hold_o))
                except InvariantViolation as echec:
                    # Degenerate scores early in the campaign: keep the current
                    # calibrator and retry next cycle. The fallback is logged --
                    # ``errors.InvariantViolation`` forbids swallowing it silently --
                    # and stays bounded: if no cycle ever succeeds, ``calibrateur.n < 1``
                    # and the fallback below relays the failure.
                    _LOG.warning(
                        "calibration_cycle_ignoree",
                        cycle=cycle,
                        n_calibration=len(xs_cal),
                        violations=echec.violations,
                    )
            cycle += 1

        if calibrateur.n < 1:
            if len(xs_cal) < n_min:
                raise InvariantViolation(
                    (
                        f"insufficient calibration: n={len(xs_cal)} < {n_min} for "
                        f"alpha={self.alpha}; increase budget or part_calibration, "
                        f"or pass an independent calibration= set",
                    )
                )
            self._calibrer(calibrateur, xs_cal, ys_cal, os_cal)
            historique.append(_largeur_moyenne(calibrateur, self.surrogate, hold_x, hold_o))

        largeur = historique[-1] if historique else float("nan")
        return ActiveReport(
            n_simulations=len(xs_lab) + len(xs_cal),
            largeur_intervalle_finale=largeur,
            q_final=float(calibrateur.q),
            n_calibration=int(calibrateur.n),
            historique_largeur=tuple(historique),
            calibration_independante=independante,
        )


__getattr__ = lazy_aliases(
    __name__,
    {
        "RapportActif": Alias(ActiveReport, "archlux.active.boucle.ActiveReport"),
    },
)
