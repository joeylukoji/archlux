"""Perceptron on descriptors — validates the learning chain without ``torch``.

A three-layer dense network is written in a day and **exercises** the loaders,
normalization and logging. If the gradient is already wrong here, the tokenization is
to blame, not the transformer (`MILESTONE-4.md` §4).
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np

from archlux._deprecation import Alias, lazy_aliases, renamed_attributes, renamed_parameters
from archlux.errors import InvariantViolation
from archlux.light.analytic import AnalyticSurrogate
from archlux.light.protocol import Glazing
from archlux.light.tokens import vector_to_tokens
from archlux.orient.circular import encode
from archlux.types import INDICATOR_SENSE, Indicator, Orientation

__all__ = ["DenseSurrogate", "descriptors"]

_EPS = 1e-8

RESIDUAL_SIGMA_FRACTION = 0.15
"""Share of ``sigma_y`` kept as the predictive sigma after training.

**A constant not justified by any measurement.** It assumes that the network absorbs
85 % of the standard deviation of the residual to the analytic surrogate, which is
checked nowhere. It can neither break nor establish conformal coverage: coverage stays
at least 1 minus alpha for *any* strictly positive sigma, since calibration divides by
the same sigma. It only acts on the **adaptivity** of the interval width. Before
publication, replace it by a sigma estimated on a disjoint validation set (absolute
residual regressed on the descriptors, or quantile regression), not by a hand-picked
scalar.
"""

SIGMA_FLOOR = 0.02
"""Floor of the predictive sigma, in the unit of the indicator. Same status: workshop value.
"""


@lru_cache(maxsize=len(INDICATOR_SENSE))
def _analytic(indicator: Indicator) -> AnalyticSurrogate:
    """Shared analytic instance: frozen, stateless, reusable without a copy.

    :meth:`DenseSurrogate.gradient` evaluates ``2 n`` times per gradient; rebuilding the
    surrogate at each evaluation was pure waste on the critical path of
    ``ARCHITECTURE.md`` §9.
    """
    return AnalyticSurrogate(target_indicator=indicator)


@renamed_parameters({"baies": "glazing"})
def descriptors(
    x: np.ndarray, orientation: Orientation, glazing: Glazing | None = None
) -> np.ndarray:
    """Continuous descriptors: room statistics × orientation harmonics.

    Explicitly includes ``area × sin 2θ``, a term present in the synthetic simulator and
    absent from the analytic surrogate — without it the perceptron cannot win.
    """
    tokens, mask = vector_to_tokens(x, orientation, glazing)
    valid = tokens[~mask]
    # Window tokens carry their flag in column 27; separating them avoids averaging
    # rooms and windows into one vector, which makes no dimensional sense.
    is_window = valid[:, 27] > 0.5
    rooms_only = valid[~is_window]
    windows = valid[is_window]
    if rooms_only.size:
        valid = rooms_only
    if valid.size == 0:
        raise InvariantViolation(("empty plan vector: no token",))
    mean = valid.mean(axis=0)
    areas = valid[:, 4]
    enc = encode(orientation.deg, harmonics=3)
    stats = np.array(
        [
            float(valid.shape[0]),
            float(areas.sum()),
            float(valid[:, 2].mean()),
            float(valid[:, 3].mean()),
            float(valid[:, 0].mean()),
            float(valid[:, 1].mean()),
        ],
        dtype=float,
    )
    interaction = np.outer(enc, stats).ravel()
    sin2 = enc[3]
    extra = np.array([float(areas.sum()) * sin2, float(areas.sum()) * enc[2]], dtype=float)
    # Six fenestration descriptors, zero when no glazing is given: the vector therefore
    # keeps the same dimension, and a model trained without glazing stays readable by a
    # model that receives some.
    if windows.size:
        widths = windows[:, 25]
        window_stats = np.array(
            [
                float(windows.shape[0]),
                float(widths.sum()),
                float(widths.mean()),
                float(windows[:, 26].mean()),
                float(np.mean(windows[:, 22])),
                float(np.mean(windows[:, 23])),
            ],
            dtype=float,
        )
    else:
        window_stats = np.zeros(6, dtype=float)
    return np.concatenate([mean, enc, stats, interaction, extra, window_stats])


def _huber_derivative(residual: float, delta: float = 1.0) -> float:
    """Derivative of the Huber loss, bounded outside ``[-delta, delta]``."""
    if abs(residual) <= delta:
        return residual
    return delta * (1.0 if residual > 0.0 else -1.0)


@renamed_attributes(
    {
        "indicateur_vise": "target_indicator",
        "largeur": "width",
        "echelle_base": "base_scale",
        "decalage_base": "base_offset",
    }
)
@dataclass
class DenseSurrogate:
    """Three-layer dense network, numpy weights. Vector input only."""

    target_indicator: Indicator = "sDA"
    width: int = 32
    W1: np.ndarray | None = None
    b1: np.ndarray | None = None
    W2: np.ndarray | None = None
    b2: np.ndarray | None = None
    W3: np.ndarray | None = None
    b3: float = 0.0
    mu: np.ndarray | None = None
    sigma: np.ndarray | None = None
    mu_y: float = 0.0
    sigma_y: float = 1.0
    base_scale: float = 1.0
    base_offset: float = 0.0

    @property
    def indicator(self) -> Indicator:
        """Name of the modelled indicator."""
        return self.target_indicator

    @property
    def weights_fingerprint(self) -> str:
        """Implements :class:`archlux.types.Fingerprintable`.

        ``uq.registry._model_fingerprint`` reads this directly instead of guessing at
        ``W1``/``b1``/... by name, so it survives an internal rename here.
        """
        if (
            self.W1 is None
            or self.b1 is None
            or self.W2 is None
            or self.b2 is None
            or self.W3 is None
        ):
            raise InvariantViolation(("fingerprinting an untrained model",))
        buffers = [
            np.ascontiguousarray(w, dtype=float).tobytes()
            for w in (self.W1, self.b1, self.W2, self.b2, self.W3)
        ]
        buffers.append(np.asarray(float(self.b3), dtype=float).tobytes())
        return hashlib.sha256(b"".join(buffers)).hexdigest()

    def n_parameters(self) -> int:
        """Number of trained scalars."""
        if (
            self.W1 is None
            or self.b1 is None
            or self.W2 is None
            or self.b2 is None
            or self.W3 is None
        ):
            return 0
        return int(self.W1.size + self.b1.size + self.W2.size + self.b2.size + self.W3.size + 1)

    def _normalize(self, feat: np.ndarray) -> np.ndarray:
        if self.mu is None or self.sigma is None:
            return feat
        return np.asarray((feat - self.mu) / np.maximum(self.sigma, _EPS), dtype=float)

    def _forward(self, feat: np.ndarray) -> tuple[float, np.ndarray, np.ndarray]:
        """Forward pass. Explicit guard: ``assert`` disappears under ``python -O``."""
        if (
            self.W1 is None
            or self.b1 is None
            or self.W2 is None
            or self.b2 is None
            or self.W3 is None
        ):
            raise InvariantViolation(("forward pass on an untrained model",))
        z1 = feat @ self.W1 + self.b1
        h1 = np.tanh(z1)
        z2 = h1 @ self.W2 + self.b2
        h2 = np.tanh(z2)
        y_hat = float(h2 @ self.W3 + self.b3)
        return y_hat, h1, h2

    def evaluate(
        self, x: np.ndarray, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> float:
        """Rescaled analytic surrogate + learned residual; untrained, the analytic alone."""
        base = (
            self.base_scale * float(_analytic(self.target_indicator).evaluate(x, orientation))
            + self.base_offset
        )
        if self.W1 is None:
            return base
        feat = self._normalize(descriptors(x, orientation, glazing))
        y_hat, _, _ = self._forward(feat)
        return base + y_hat * self.sigma_y + self.mu_y

    def gradient(
        self, x: np.ndarray, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> np.ndarray:
        """Centred finite differences on the plan vector.

        Cost: ``2 n`` calls to :meth:`evaluate` (``n = 4 × rooms``), i.e. 120 full passes
        for 15 rooms. Over 50 Frank-Wolfe iterations, that is most of the "performance
        legalization < 500 ms" budget (``ARCHITECTURE.md`` §9), and it will not hold for
        a heavier model. Exact backpropagation is possible — the network is
        differentiable and the analytic surrogate has a closed-form gradient — but it
        changes the values returned near the kink ``depth == useful_depth``: substituting
        it requires running :func:`archlux.light.validation.validate_gradient` again.
        """
        x0 = np.asarray(x, dtype=float).ravel().copy()
        g = np.empty_like(x0)
        step = 1e-4
        for i in range(x0.size):
            plus, minus = x0.copy(), x0.copy()
            plus[i] += step
            minus[i] -= step
            g[i] = (
                self.evaluate(plus, orientation, glazing=glazing)
                - self.evaluate(minus, orientation, glazing=glazing)
            ) / (2.0 * step)
        return g

    def uncertainty(
        self, x: np.ndarray, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> float:
        """**Constant** ``σ̂``, derived from ``sigma_y`` by a workshop fraction.

        Depends neither on ``x`` nor on the orientation: it is therefore not a predictive
        uncertainty, only a scale. Conformal coverage stays valid (see
        :data:`RESIDUAL_SIGMA_FRACTION`), but the interval has the same width everywhere:
        no gain in adaptivity, and the figure ``0.15`` is backed by no measurement.
        """
        del x, orientation, glazing
        return float(max(self.sigma_y * RESIDUAL_SIGMA_FRACTION, SIGMA_FLOOR))

    @renamed_parameters({"epoques": "epochs"})
    def fit(
        self,
        xs: tuple[np.ndarray, ...],
        ys: np.ndarray,
        orientations: tuple[Orientation, ...],
        *,
        seed: int,
        epochs: int = 120,
        lr: float = 0.08,
        glazing: tuple[Glazing | None, ...] | None = None,
    ) -> None:
        """Rescale the analytic surrogate, then Huber gradient descent on the **residual**.

        The affine rescaling is not cosmetic. ``AnalyticSurrogate`` returns a score in
        **arbitrary units** — a sum of weighted facades, of the order of a hundred —
        with no physical scale at all. Against ``SplitFluxOracle``, built on the same
        base, the two coincide and the residual is small. Against a real simulation
        (Swiss Dwellings, irradiance of the order of 1), the residual would be the
        opposite of the score: the network would spend its capacity cancelling a scale
        constant instead of learning the physics.

        So ``y ≈ a·f(x) + b`` is first fitted by least squares on the training set, then
        the network learns the residual to this **rescaled** base. ``a = 1``, ``b = 0``
        restores exactly the earlier behaviour.
        """
        if len(xs) != len(ys) or len(xs) != len(orientations):
            raise InvariantViolation(("xs, ys and orientations must have the same length",))
        analytic = _analytic(self.target_indicator)
        raw = np.array(
            [float(analytic.evaluate(x, ori)) for x, ori in zip(xs, orientations, strict=True)]
        )
        raw_target = np.asarray(ys, dtype=float).ravel()
        variance = float(np.var(raw))
        if variance > _EPS:
            slope, intercept = np.polyfit(raw, raw_target, 1)
            self.base_scale = float(slope)
            self.base_offset = float(intercept)
        else:
            self.base_scale = 0.0
            self.base_offset = float(np.mean(raw_target))
        residuals = raw_target - (self.base_scale * raw + self.base_offset)
        fenestration = glazing if glazing is not None else (None,) * len(xs)
        feats = np.stack(
            [descriptors(x, o, b) for x, o, b in zip(xs, orientations, fenestration, strict=True)]
        )
        self.mu = feats.mean(axis=0)
        self.sigma = feats.std(axis=0)
        self.sigma[self.sigma < _EPS] = 1.0
        feats = (feats - self.mu) / self.sigma
        self.mu_y = float(np.mean(residuals))
        self.sigma_y = max(float(np.std(residuals)), _EPS)
        targets = (residuals - self.mu_y) / self.sigma_y
        rng = np.random.default_rng(seed)
        dim = int(feats.shape[1])
        k = self.width
        self.W1 = rng.normal(0.0, 1.0 / math.sqrt(dim), size=(dim, k))
        self.b1 = np.zeros(k)
        self.W2 = rng.normal(0.0, 1.0 / math.sqrt(k), size=(k, k))
        self.b2 = np.zeros(k)
        self.W3 = rng.normal(0.0, 1.0 / math.sqrt(k), size=(k,))
        self.b3 = 0.0
        n = feats.shape[0]
        for _ in range(epochs):
            order = rng.permutation(n)
            for index in order:
                feat = feats[index]
                y_hat, h1, h2 = self._forward(feat)
                residual = y_hat - float(targets[index])
                d_y = _huber_derivative(residual)
                d_h2 = d_y * self.W3 * (1.0 - h2 * h2)
                d_h1 = (d_h2 @ self.W2.T) * (1.0 - h1 * h1)
                self.W3 -= lr * d_y * h2
                self.b3 -= lr * d_y
                self.W2 -= lr * np.outer(h1, d_h2)
                self.b2 -= lr * d_h2
                self.W1 -= lr * np.outer(feat, d_h1)
                self.b1 -= lr * d_h1

    @renamed_parameters({"chemin": "path"})
    def save(self, path: Path) -> str:
        """Write the weights as ``npz``. Returns the SHA-256 of the file **written**.

        ``numpy.savez`` itself appends ``.npz`` when the path does not carry it; the
        suffix is therefore normalized here, otherwise the fingerprint would be computed
        on a file that does not exist. Returning the path actually written is not
        needed: it follows from the same rule.
        """
        if (
            self.W1 is None
            or self.b1 is None
            or self.W2 is None
            or self.b2 is None
            or self.W3 is None
            or self.mu is None
            or self.sigma is None
        ):
            raise InvariantViolation(("saving an untrained model",))
        path = Path(path)
        if path.suffix != ".npz":
            path = path.with_name(path.name + ".npz")
        np.savez(
            path,
            W1=self.W1,
            b1=self.b1,
            W2=self.W2,
            b2=self.b2,
            W3=self.W3,
            b3=np.array(self.b3),
            mu=self.mu,
            sigma=self.sigma,
            mu_y=np.array(self.mu_y),
            sigma_y=np.array(self.sigma_y),
            # The keys of the saved archive are part of the file format: they keep their
            # original spelling so that models saved before the English API still load.
            # mypy matches the ``**`` mapping against ``allow_pickle: bool``
            **{  # type: ignore[arg-type]
                "echelle_base": np.array(self.base_scale),
                "decalage_base": np.array(self.base_offset),
                "indicateur": np.array(self.target_indicator),
            },
        )
        return hashlib.sha256(path.read_bytes()).hexdigest()

    @classmethod
    @renamed_parameters({"chemin": "path"})
    def load(cls, path: Path) -> DenseSurrogate:
        """Read back an ``npz`` written by :meth:`save`."""
        with np.load(Path(path), allow_pickle=False) as archive:
            indicator = str(archive["indicateur"])
            # Matching by equality types the result on every mypy version, without a cast.
            target = next((known for known in INDICATOR_SENSE if known == indicator), None)
            if target is None:
                raise InvariantViolation((f"unknown indicator in the weights: {indicator}",))
            model = cls(target_indicator=target)
            model.W1 = np.array(archive["W1"], dtype=float, copy=True)
            model.b1 = np.array(archive["b1"], dtype=float, copy=True)
            model.W2 = np.array(archive["W2"], dtype=float, copy=True)
            model.b2 = np.array(archive["b2"], dtype=float, copy=True)
            model.W3 = np.array(archive["W3"], dtype=float, copy=True)
            model.b3 = float(archive["b3"])
            model.mu = np.array(archive["mu"], dtype=float, copy=True)
            model.sigma = np.array(archive["sigma"], dtype=float, copy=True)
            model.mu_y = float(archive["mu_y"])
            model.sigma_y = float(archive["sigma_y"])
            # Weights older than the affine rescaling: identity, unchanged behaviour.
            if "echelle_base" in archive:
                model.base_scale = float(archive["echelle_base"])
                model.base_offset = float(archive["decalage_base"])
        return model


__getattr__ = lazy_aliases(
    __name__,
    {
        "FRACTION_SIGMA_RESIDUEL": Alias(
            RESIDUAL_SIGMA_FRACTION, "archlux.light.base.RESIDUAL_SIGMA_FRACTION"
        ),
        "SIGMA_PLANCHER": Alias(SIGMA_FLOOR, "archlux.light.base.SIGMA_FLOOR"),
        "SubstitutDense": Alias(DenseSurrogate, "archlux.light.base.DenseSurrogate"),
        "descripteurs": Alias(descriptors, "archlux.light.base.descriptors"),
    },
)
