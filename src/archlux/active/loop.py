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
from archlux.uq.conformal import ConformalCalibrator, minimal_n_conformal

if TYPE_CHECKING:
    from archlux.light.protocol import Surrogate
    from archlux.types import Orientation

__all__ = ["ActiveReport", "Loop"]

_LOG = structlog.get_logger("archlux.active.loop")


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


@dataclass(frozen=True, slots=True)
class Batch:
    """A set of candidate plans and their orientations, kept in sync by construction.

    Replaces the parallel ``xs``/``orientations`` lists :class:`Loop` passed around
    internally (PLAN.md phase 4, block 12, item 33). Scoped to internal use: changing
    ``Loop.run``'s own public parameter list (``propositions``/``orientations``,
    ``holdout``/``holdout_orientations``, ``calibration``/``calibration_orientations``)
    would break every existing caller for a cosmetic gain. Not in ``__all__``.
    """

    x: tuple[np.ndarray, ...]
    orientations: tuple[Orientation, ...]

    def __post_init__(self) -> None:
        """Keep ``x`` and ``orientations`` the same length, by construction."""
        if len(self.x) != len(self.orientations):
            raise InvariantViolation(("x and orientations have distinct lengths",))

    def __len__(self) -> int:
        """Number of candidates."""
        return len(self.x)


@dataclass(slots=True)
class _CampaignState:
    """The lists one ``Loop.run`` campaign grows in place, cycle after cycle.

    ``*_lab`` feed ``fit``; ``*_cal`` feed the conformal calibration only, never
    ``fit``; ``exclus`` holds the pool indices already acquired.
    """

    xs_cal: list[np.ndarray]
    ys_cal: list[float]
    os_cal: list[Orientation]
    xs_lab: list[np.ndarray] = field(default_factory=list)
    ys_lab: list[float] = field(default_factory=list)
    os_lab: list[Orientation] = field(default_factory=list)
    exclus: list[int] = field(default_factory=list)


def _stack(xs: list[np.ndarray]) -> np.ndarray:
    """Stack plan vectors into a ``(n, d)`` matrix."""
    return np.stack([np.asarray(x, dtype=float).ravel() for x in xs])


def _acquisition_uncertainties(
    surrogate: Surrogate,
    pool: Batch,
    xs_labeled: list[np.ndarray],
) -> np.ndarray:
    """Surrogate σ̂ x (1 + distance to the nearest already-simulated point).

    A constant ``incertitude`` (e.g. ``DenseSurrogate``) does not discriminate:
    the distance to the already-labeled points forces exploration.
    """
    base = np.array(
        [
            float(surrogate.uncertainty(x, o))
            for x, o in zip(pool.x, pool.orientations, strict=True)
        ],
        dtype=float,
    )
    if not xs_labeled:
        return np.asarray(np.maximum(base, 1e-12), dtype=float)
    ref = _stack(xs_labeled)
    cand = _stack(list(pool.x))
    dist2 = np.sum((cand[:, None, :] - ref[None, :, :]) ** 2, axis=2)
    dist = np.sqrt(np.min(dist2, axis=1))
    scale = float(np.median(dist) + 1e-9)
    return np.asarray(np.maximum(base, 1e-12) * (1.0 + dist / scale), dtype=float)


def _mean_width(
    calibrator: ConformalCalibrator,
    surrogate: Surrogate,
    holdout: Batch,
) -> float:
    """Mean width of the conformal intervals on the held-out set."""
    widths: list[float] = []
    for x, o in zip(holdout.x, holdout.orientations, strict=True):
        pred = float(surrogate.evaluate(x, o))
        sigma = float(surrogate.uncertainty(x, o))
        # Held-out plans, never chosen by an optimizer: exchangeable by construction.
        borne = calibrator.borne(pred, sigma, regime="exchangeable")
        widths.append(float(borne.upper - borne.lower))
    return float(np.mean(widths))


def _validate_run_inputs(
    propositions: list[np.ndarray],
    orientations: list[Orientation],
    batch: int,
    reference_optimiseur: list[np.ndarray],
    holdout: list[np.ndarray] | None,
    holdout_orientations: list[Orientation] | None,
) -> Batch:
    """Validate ``Loop.run``'s inputs; return the holdout batch (default: the pool).

    Extracted from :meth:`Loop.run` (PLAN.md phase 4, block 12, item 36).
    """
    if len(propositions) != len(orientations):
        raise InvariantViolation(("propositions and orientations have distinct lengths",))
    if len(propositions) < batch:
        raise InvariantViolation(("pool smaller than the batch",))
    if not reference_optimiseur:
        raise InvariantViolation(("reference_optimiseur is empty",))
    hold_x = holdout if holdout is not None else propositions
    hold_o = holdout_orientations if holdout_orientations is not None else orientations
    if len(hold_x) != len(hold_o):
        raise InvariantViolation(("holdout and orientations have distinct lengths",))
    if not hold_x:
        raise InvariantViolation(("holdout is empty",))
    return Batch(tuple(hold_x), tuple(hold_o))


def _seed_calibration(
    simulateur: Surrogate,
    calibration: list[np.ndarray] | None,
    calibration_orientations: list[Orientation] | None,
    n_min: int,
    alpha: float,
) -> tuple[list[np.ndarray], list[float], list[Orientation], bool]:
    """The independent calibration set, ground-truthed once, outside the budget.

    Extracted from :meth:`Loop.run` (PLAN.md phase 4, block 12, item 36).
    """
    independent = calibration is not None
    xs_cal: list[np.ndarray] = []
    os_cal: list[Orientation] = []
    if calibration is not None:
        if calibration_orientations is None or len(calibration) != len(calibration_orientations):
            raise InvariantViolation(
                ("calibration and calibration_orientations have distinct lengths",)
            )
        if len(calibration) < n_min:
            raise InvariantViolation(
                (f"calibration n={len(calibration)} < {n_min} required for alpha={alpha}",)
            )
        xs_cal = [np.asarray(x, dtype=float).copy() for x in calibration]
        os_cal = list(calibration_orientations)
    ys_cal: list[float] = [
        float(simulateur.evaluate(x, o)) for x, o in zip(xs_cal, os_cal, strict=True)
    ]
    return xs_cal, ys_cal, os_cal, independent


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
        minimum calibration size, via :func:`~archlux.uq.conformal.minimal_n_conformal`.
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

    def _calibrate(
        self,
        calibrator: ConformalCalibrator,
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
        calibrator.fit(preds, np.asarray(ys, dtype=float), sigmas, alpha=self.alpha)

    def _split_acquired(
        self, n_acquired: int, rng: np.random.Generator, *, independent: bool
    ) -> set[int]:
        """Ranks of the current batch to divert to calibration rather than training.

        The draw is **internal to the batch**: it therefore does not depend on the
        acquisition order, which goes from most exploratory to most exploitative.
        """
        if independent or self.part_calibration <= 0.0 or n_acquired < 1:
            return set()
        n_cal = min(n_acquired, max(1, round(self.part_calibration * n_acquired)))
        return {int(j) for j in rng.permutation(n_acquired)[:n_cal]}

    def _fit_cycle(
        self,
        cycle: int,
        xs_lab: list[np.ndarray],
        ys_lab: list[float],
        os_lab: list[Orientation],
    ) -> None:
        """Retrain ``surrogate`` on the labeled set, if it is adjustable and large enough.

        Extracted from :meth:`run` (PLAN.md phase 4, block 12, item 36).
        :class:`~archlux.light.protocol.Adjustable` (item 34) documents the contract,
        but the runtime test stays a callable ``fit`` attribute: ``isinstance`` on the
        protocol would also demand ``gradient`` (never called here) and, on Python
        >= 3.12, ignore a wrapper's ``__getattr__`` -- silently skipping retraining.
        A surrogate written before the English rename (only ``ajuster``) is still
        retrained, with a deprecation warning.
        """
        fit = getattr(self.surrogate, "fit", None)
        if not callable(fit):
            fit = None
        legacy_fit = getattr(self.surrogate, "ajuster", None)
        if fit is None and legacy_fit is not None:
            # stacklevel: _fit_cycle -> _run_cycle -> run -> the caller of run.
            warnings.warn(
                f"{type(self.surrogate).__name__}.ajuster is deprecated, rename it fit",
                DeprecationWarning,
                stacklevel=4,
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

    def _run_cycle(
        self,
        cycle: int,
        pool: Batch,
        dens: np.ndarray,
        rng: np.random.Generator,
        n_take: int,
        state: _CampaignState,
        *,
        independent: bool,
    ) -> list[int]:
        """Select, simulate, split and (re)fit for one acquisition cycle.

        ``state``'s lists are mutated in place. Returns the acquired pool indices (for
        the caller's remaining-budget bookkeeping).

        Extracted from :meth:`run` (PLAN.md phase 4, block 12, item 36).
        """
        inc = _acquisition_uncertainties(self.surrogate, pool, state.xs_lab)
        idxs = self.acquire.selectionner(
            inc,
            dens,
            n=n_take,
            seed=derive(self.seed, f"selection/{cycle}"),
            exclus=np.asarray(state.exclus, dtype=int) if state.exclus else None,
        )
        acquired = [int(i) for i in idxs]
        # Split BEFORE any fitting: this is what physically prevents ``fit``
        # from ever seeing a calibration point.
        to_calibration = self._split_acquired(len(acquired), rng, independent=independent)
        for rank, i in enumerate(acquired):
            x = np.asarray(pool.x[i], dtype=float).copy()
            o = pool.orientations[i]
            y = float(self.simulateur.evaluate(x, o))
            if rank in to_calibration:
                state.xs_cal.append(x)
                state.ys_cal.append(y)
                state.os_cal.append(o)
            else:
                state.xs_lab.append(x)
                state.ys_lab.append(y)
                state.os_lab.append(o)
            state.exclus.append(i)
        self._fit_cycle(cycle, state.xs_lab, state.ys_lab, state.os_lab)
        return acquired

    def _recalibrate_cycle(
        self,
        cycle: int,
        calibrator: ConformalCalibrator,
        xs_cal: list[np.ndarray],
        ys_cal: list[float],
        os_cal: list[Orientation],
        n_min: int,
        holdout: Batch,
        history: list[float],
    ) -> None:
        """Recalibrate and measure the held-out interval width, if enough points exist.

        The model has changed since the last cycle, so the old ``q_hat`` no longer
        bounds anything; scores come from ``xs_cal``, never from the training set.
        Degenerate scores early in a campaign are logged and retried next cycle,
        never swallowed silently (``errors.InvariantViolation`` forbids it): if no
        cycle ever succeeds, ``calibrateur.n < 1`` and :meth:`run`'s own fallback
        relays the failure.

        Extracted from :meth:`run` (PLAN.md phase 4, block 12, item 36).
        """
        if len(xs_cal) < n_min:
            return
        try:
            self._calibrate(calibrator, xs_cal, ys_cal, os_cal)
            history.append(_mean_width(calibrator, self.surrogate, holdout))
        except InvariantViolation as failure:
            _LOG.warning(
                "calibration_cycle_ignoree",
                cycle=cycle,
                n_calibration=len(xs_cal),
                violations=failure.violations,
            )

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
        hold = _validate_run_inputs(
            propositions,
            orientations,
            self.batch,
            reference_optimiseur,
            holdout,
            holdout_orientations,
        )
        n_min = minimal_n_conformal(self.alpha)
        xs_cal, ys_cal, os_cal, independent = _seed_calibration(
            self.simulateur, calibration, calibration_orientations, n_min, self.alpha
        )
        state = _CampaignState(xs_cal, ys_cal, os_cal)

        pool = Batch(tuple(propositions), tuple(orientations))
        dens = kernel_density(_stack(propositions), _stack(reference_optimiseur))
        history: list[float] = []
        remaining = self.budget
        cycle = 0
        calibrator = ConformalCalibrator(indicator="sDA")
        # Named sub-streams (AUDIT.md Q-M5): with ``seed + cycle`` the campaign of seed 17
        # at cycle 1 replayed the selection of the campaign of seed 18 at cycle 0.
        rng = np.random.default_rng(derive(self.seed, "split"))

        while remaining > 0:
            n_take = min(self.batch, remaining, len(pool) - len(state.exclus))
            if n_take < 1:
                break
            acquired = self._run_cycle(
                cycle, pool, dens, rng, n_take, state, independent=independent
            )
            remaining -= len(acquired)
            self._recalibrate_cycle(
                cycle,
                calibrator,
                state.xs_cal,
                state.ys_cal,
                state.os_cal,
                n_min,
                hold,
                history,
            )
            cycle += 1

        if calibrator.n < 1:
            if len(state.xs_cal) < n_min:
                raise InvariantViolation(
                    (
                        f"insufficient calibration: n={len(state.xs_cal)} < {n_min} for "
                        f"alpha={self.alpha}; increase budget or part_calibration, "
                        f"or pass an independent calibration= set",
                    )
                )
            self._calibrate(calibrator, state.xs_cal, state.ys_cal, state.os_cal)
            history.append(_mean_width(calibrator, self.surrogate, hold))

        largeur = history[-1] if history else float("nan")
        return ActiveReport(
            n_simulations=len(state.xs_lab) + len(state.xs_cal),
            largeur_intervalle_finale=largeur,
            q_final=float(calibrator.q),
            n_calibration=int(calibrator.n),
            historique_largeur=tuple(history),
            calibration_independante=independent,
        )


__getattr__ = lazy_aliases(
    __name__,
    {
        "RapportActif": Alias(ActiveReport, "archlux.active.loop.ActiveReport"),
    },
)
