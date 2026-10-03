"""Active learning: `MILESTONE-6.md` §3."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pytest

from archlux.active.density import kernel_density
from archlux.active.loop import Batch, Loop
from archlux.active.selection import RandomStrategy, UncertaintyTimesDensity
from archlux.errors import InvariantViolation
from archlux.light.protocol import Adjustable
from archlux.types import Orientation


def test_a_zero_product_discards_the_candidate() -> None:
    """Zero density → zero score → last in the ranking."""
    inc = np.array([10.0, 1.0, 5.0])
    dens = np.array([0.0, 1.0, 0.5])
    # scores = (0, 1, 2.5) → order 2, 1, 0
    idxs = UncertaintyTimesDensity().select(inc, dens, n=3, seed=0)
    assert list(idxs) == [2, 1, 0]


def test_random_is_deterministic_with_a_seed() -> None:
    inc = np.ones(20)
    dens = np.ones(20)
    a = RandomStrategy().select(inc, dens, n=5, seed=42)
    b = RandomStrategy().select(inc, dens, n=5, seed=42)
    assert np.array_equal(a, b)


def test_density_is_higher_near_the_reference() -> None:
    ref = np.array([[0.0, 0.0], [0.1, 0.0], [-0.1, 0.05]])
    cand = np.array([[0.0, 0.0], [5.0, 5.0]])
    d = kernel_density(cand, ref)
    assert d[0] > d[1]


@dataclass
class _RegionOracle:
    """Truth: y = x[0]; low noise near 0, high far away (|x[0]| > 2)."""

    indicator: str = "sDA"

    def evaluate(self, x: np.ndarray, orientation: Orientation, *, glazing: object = None) -> float:
        del orientation, glazing
        z = float(np.asarray(x, dtype=float).ravel()[0])
        noise = 0.05 if abs(z) <= 2.0 else 2.0
        # Deterministic: "noise" = a fixed offset per region (reproducible).
        return z + (0.01 if noise < 1.0 else 1.5)

    def gradient(
        self, x: np.ndarray, orientation: Orientation, *, glazing: object = None
    ) -> np.ndarray:
        g = np.zeros_like(np.asarray(x, dtype=float).ravel())
        g[0] = 1.0
        return g

    def uncertainty(
        self, x: np.ndarray, orientation: Orientation, *, glazing: object = None
    ) -> float:
        del x, orientation, glazing
        return 1.0


@dataclass
class _LocalModel:
    """Local constant regression: mean of the nearby labelled y."""

    indicator: str = "sDA"
    xs: list[np.ndarray] = field(default_factory=list)
    ys: list[float] = field(default_factory=list)
    _sigma: float = 1.0

    def evaluate(self, x: np.ndarray, orientation: Orientation, *, glazing: object = None) -> float:
        del orientation, glazing
        if not self.ys:
            return 0.0
        z = float(np.asarray(x, dtype=float).ravel()[0])
        zs = np.array([float(np.asarray(v, dtype=float).ravel()[0]) for v in self.xs])
        weights = np.exp(-0.5 * (zs - z) ** 2)
        return float(np.average(self.ys, weights=weights))

    def gradient(
        self, x: np.ndarray, orientation: Orientation, *, glazing: object = None
    ) -> np.ndarray:
        return np.zeros_like(np.asarray(x, dtype=float).ravel())

    def uncertainty(
        self, x: np.ndarray, orientation: Orientation, *, glazing: object = None
    ) -> float:
        """Distance to the nearest labelled point (explores the unknown)."""
        del orientation, glazing
        if not self.xs:
            return 1.0
        z = float(np.asarray(x, dtype=float).ravel()[0])
        zs = np.array([float(np.asarray(v, dtype=float).ravel()[0]) for v in self.xs])
        return float(np.min(np.abs(zs - z)) + self._sigma * 0.1)

    def fit(
        self,
        xs: tuple[np.ndarray, ...],
        ys: np.ndarray,
        orientations: tuple[Orientation, ...],
        *,
        seed: int,
        epochs: int = 1,
        lr: float = 0.1,
    ) -> None:
        del orientations, seed, epochs, lr
        self.xs = [np.asarray(x, dtype=float).copy() for x in xs]
        self.ys = [float(y) for y in ys]
        preds = np.array([self.evaluate(x, Orientation(0.0)) for x in self.xs])
        self._sigma = float(max(np.std(preds - np.asarray(ys)), 0.05))


def test_active_beats_random() -> None:
    """At equal budget, active learning bounds the useful region better (optimizer density).

    Mixed pool: useful region |z|≤2 (low noise) and far region |z|>3 (structural noise).
    The optimizer density is concentrated on the useful region; random sampling wastes
    simulations far away → a wider q.
    """
    rng = np.random.default_rng(0)
    useful = [np.array([float(z)]) for z in rng.uniform(-1.5, 1.5, size=30)]
    far = [np.array([float(z)]) for z in rng.choice([-4.0, -3.5, 3.5, 4.0], size=30)]
    pool = useful + far
    oris = [Orientation(0.0) for _ in pool]
    ref = [np.array([float(z)]) for z in np.linspace(-1.0, 1.0, 15)]
    hold = [np.array([float(z)]) for z in np.linspace(-1.2, 1.2, 12)]
    hold_o = [Orientation(0.0) for _ in hold]
    # INDEPENDENT calibration: drawn outside the acquisition pool, from the same law as
    # the holdout. It is the only mode whose coverage can be published, and the only one
    # that makes the comparison between strategies honest (same q-hat).
    cal_rng = np.random.default_rng(99)
    calib = [np.array([float(z)]) for z in cal_rng.uniform(-1.5, 1.5, size=16)]
    calib_o = [Orientation(0.0) for _ in calib]

    def _campaign(acquire: object) -> float:
        model = _LocalModel()
        # Warm-up: 4 useful points.
        xs0 = tuple(useful[:4])
        ys0 = np.array([_RegionOracle().evaluate(x, Orientation(0.0)) for x in xs0])
        model.fit(xs0, ys0, tuple(Orientation(0.0) for _ in xs0), seed=0)
        loop = Loop(
            surrogate=model,
            simulator=_RegionOracle(),
            acquire=acquire,  # type: ignore[arg-type]
            budget=20,
            batch=4,
            seed=3,
        )
        report = loop.run(
            pool,
            oris,
            optimizer_reference=ref,
            holdout=hold,
            holdout_orientations=hold_o,
            calibration=calib,
            calibration_orientations=calib_o,
        )
        assert report.independent_calibration
        assert report.n_calibration == len(calib)
        return report.final_interval_width

    random_width = _campaign(RandomStrategy())
    active_width = _campaign(UncertaintyTimesDensity())
    assert active_width < random_width, f"active={active_width:.4f} random={random_width:.4f}"


def test_a_surrogate_that_still_has_ajuster_is_retrained_with_a_warning() -> None:
    """Review of the stack (#12): the loop looked up ``fit`` only, and silently stopped
    retraining a surrogate written before the rename."""
    calls: list[int] = []

    class Legacy(_LocalModel):
        fit = None  # type: ignore[assignment]

        def ajuster(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            calls.append(1)
            kwargs["epochs"] = kwargs.pop("epoques")  # the keyword of a pre-English surrogate
            return _LocalModel.fit(self, *args, **kwargs)

    rng = np.random.default_rng(0)
    pool = [np.array([float(z)]) for z in rng.uniform(-1.5, 1.5, size=16)]
    oris = [Orientation(0.0) for _ in pool]
    calib = [np.array([float(z)]) for z in rng.uniform(-1.5, 1.5, size=12)]
    loop = Loop(
        surrogate=Legacy(),
        simulator=_RegionOracle(),
        acquire=RandomStrategy(),
        budget=8,
        batch=4,
        seed=3,
    )
    with pytest.warns(DeprecationWarning, match="ajuster is deprecated"):
        loop.run(
            pool,
            oris,
            optimizer_reference=pool[:4],
            calibration=calib,
            calibration_orientations=[Orientation(0.0) for _ in calib],
        )
    assert calls, "the legacy surrogate was never retrained"


def test_batch_rejects_mismatched_lengths() -> None:
    """PLAN.md phase 4, block 12, item 33: `x` and `orientations` stay in sync."""
    with pytest.raises(InvariantViolation):
        Batch(x=(np.zeros(4),), orientations=())


def test_batch_len_is_the_candidate_count() -> None:
    batch = Batch(x=(np.zeros(4), np.ones(4)), orientations=(Orientation(0.0), Orientation(90.0)))
    assert len(batch) == 2


def test_a_trainable_surrogate_satisfies_adjustable() -> None:
    """PLAN.md phase 4, block 12, item 34: `fit` makes a surrogate `Adjustable`."""
    assert isinstance(_LocalModel(), Adjustable)


def test_a_frozen_surrogate_does_not_satisfy_adjustable() -> None:
    assert not isinstance(_RegionOracle(), Adjustable)


def _short_campaign(surrogate: object) -> None:
    """Run a small campaign with an independent calibration set."""
    rng = np.random.default_rng(0)
    pool = [np.array([float(z)]) for z in rng.uniform(-1.5, 1.5, size=16)]
    calib = [np.array([float(z)]) for z in rng.uniform(-1.5, 1.5, size=12)]
    loop = Loop(
        surrogate=surrogate,  # type: ignore[arg-type]
        simulator=_RegionOracle(),
        acquire=RandomStrategy(),
        budget=8,
        batch=4,
        seed=3,
    )
    loop.run(
        pool,
        [Orientation(0.0) for _ in pool],
        optimizer_reference=pool[:4],
        calibration=calib,
        calibration_orientations=[Orientation(0.0) for _ in calib],
    )


def test_the_ajuster_deprecation_points_at_the_caller_of_run() -> None:
    """Review of block 12: the warning moved two frames deeper with the ``run`` split,
    so it was attributed to ``loop.py`` and hidden by Python's default filters."""

    class Legacy(_LocalModel):
        fit = None  # type: ignore[assignment]

        def ajuster(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            kwargs["epochs"] = kwargs.pop("epoques")  # the keyword of a pre-English surrogate
            return _LocalModel.fit(self, *args, **kwargs)

    rng = np.random.default_rng(0)
    pool = [np.array([float(z)]) for z in rng.uniform(-1.5, 1.5, size=16)]
    calib = [np.array([float(z)]) for z in rng.uniform(-1.5, 1.5, size=12)]
    loop = Loop(
        surrogate=Legacy(),
        simulator=_RegionOracle(),
        acquire=RandomStrategy(),
        budget=8,
        batch=4,
        seed=3,
    )
    with pytest.warns(DeprecationWarning, match="ajuster is deprecated") as caught:
        loop.run(
            pool,
            [Orientation(0.0) for _ in pool],
            optimizer_reference=pool[:4],
            calibration=calib,
            calibration_orientations=[Orientation(0.0) for _ in calib],
        )
    assert {w.filename for w in caught} == {__file__}


def test_a_surrogate_with_fit_but_no_gradient_is_retrained() -> None:
    """Review of block 12: ``Loop`` never calls ``gradient``, so a surrogate lacking it
    must still be retrained -- ``isinstance(..., Adjustable)`` silently skipped it."""
    calls: list[int] = []

    class NoGradient:
        indicator = "sDA"

        def __init__(self) -> None:
            self._inner = _LocalModel()

        def evaluate(self, x: np.ndarray, o: Orientation, *, glazing: object = None) -> float:
            return self._inner.evaluate(x, o)

        def uncertainty(self, x: np.ndarray, o: Orientation, *, glazing: object = None) -> float:
            return self._inner.uncertainty(x, o)

        def fit(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            calls.append(1)
            self._inner.fit(*args, **kwargs)

    _short_campaign(NoGradient())
    assert calls, "a surrogate with fit but no gradient was never retrained"


def test_a_getattr_forwarding_wrapper_is_retrained() -> None:
    """Review of block 12: on Python >= 3.12 a runtime-checkable protocol check ignores
    ``__getattr__``, so a forwarding wrapper around a trainable surrogate was skipped."""
    calls: list[int] = []

    class Counting(_LocalModel):
        def fit(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            calls.append(1)
            super().fit(*args, **kwargs)

    class Wrapper:
        def __init__(self, inner: object) -> None:
            self._inner = inner

        def __getattr__(self, name: str) -> object:
            return getattr(self._inner, name)

    _short_campaign(Wrapper(Counting()))
    assert calls, "a __getattr__-forwarding wrapper was never retrained"


def test_a_fit_with_the_old_epochs_keyword_is_retrained_with_a_warning() -> None:
    """A third-party ``fit(..., epoques=)`` written before the rename kept failing with a
    ``TypeError`` once ``Loop`` passed ``epochs=``: it is retrained, with a warning
    attributed to the caller of ``run``."""
    calls: list[int] = []

    class OldKeyword(_LocalModel):
        def fit(  # type: ignore[override]
            self,
            xs: tuple[np.ndarray, ...],
            ys: np.ndarray,
            orientations: tuple[Orientation, ...],
            *,
            seed: int,
            lr: float,
            epoques: int,  # lang-ok: the pre-English keyword under test
        ) -> None:
            calls.append(1)
            _LocalModel.fit(self, xs, ys, orientations, seed=seed, lr=lr, epochs=epoques)

    rng = np.random.default_rng(0)
    pool = [np.array([float(z)]) for z in rng.uniform(-1.5, 1.5, size=16)]
    calib = [np.array([float(z)]) for z in rng.uniform(-1.5, 1.5, size=12)]
    loop = Loop(
        surrogate=OldKeyword(),
        simulator=_RegionOracle(),
        acquire=RandomStrategy(),
        budget=8,
        batch=4,
        seed=3,
    )
    with pytest.warns(DeprecationWarning, match="rename the keyword epochs") as caught:
        loop.run(
            pool,
            [Orientation(0.0) for _ in pool],
            optimizer_reference=pool[:4],
            calibration=calib,
            calibration_orientations=[Orientation(0.0) for _ in calib],
        )
    assert calls
    assert {w.filename for w in caught} == {__file__}
