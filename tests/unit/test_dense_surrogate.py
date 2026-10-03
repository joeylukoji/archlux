"""Perceptron dense et point de contrôle — `MILESTONE-4.md` §4–7."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from archlux.errors import InvariantViolation
from archlux.light.analytic import AnalyticSurrogate
from archlux.light.base import DenseSurrogate
from archlux.light.learned import MAX_PARAMETRES, LearnedSurrogate
from archlux.light.protocol import Surrogate
from archlux.light.split_flux import SplitFluxOracle
from archlux.light.validation import validate_gradient
from archlux.types import Fingerprintable, Orientation
from archlux.uq.registry import DataManagement, _model_fingerprint, freeze_and_issue

_SIM = SplitFluxOracle()
_ANA = AnalyticSurrogate()


def _jeu(
    *, seed: int, n: int = 40
) -> tuple[tuple[np.ndarray, ...], np.ndarray, tuple[Orientation, ...]]:
    rng = np.random.default_rng(seed)
    xs: list[np.ndarray] = []
    ys: list[float] = []
    orients: list[Orientation] = []
    for _ in range(n):
        coupe = float(rng.uniform(4.0, 8.0))
        x = np.array([0.0, 0.0, coupe, 4.5, coupe, 0.0, 12.0 - coupe, 4.5])
        deg = float(rng.uniform(0.0, 360.0))
        ori = Orientation(deg=deg)
        xs.append(x)
        orients.append(ori)
        ys.append(_SIM.evaluate(x, ori))
    return tuple(xs), np.array(ys), tuple(orients)


def _entraine(tmp_path: Path) -> LearnedSurrogate:
    xs, ys, oris = _jeu(seed=17, n=48)
    dense = DenseSurrogate()
    dense.fit(xs, ys, oris, seed=17, epochs=40, lr=0.12)
    path = tmp_path / "dense.npz"
    fingerprint = dense.save(path)
    return LearnedSurrogate(path, fingerprint, frozen=True)


def test_dense_respecte_le_protocole() -> None:
    assert isinstance(DenseSurrogate(), Surrogate)


def test_meilleur_que_analytique(tmp_path: Path) -> None:
    reseau = _entraine(tmp_path)
    xs, ys, oris = _jeu(seed=99, n=24)

    def mae(model) -> float:
        return float(
            np.mean([abs(model.evaluate(x, o) - y) for x, o, y in zip(xs, oris, ys, strict=True)])
        )

    assert mae(reseau) < mae(_ANA)


def test_taille_raisonnable(tmp_path: Path) -> None:
    reseau = _entraine(tmp_path)
    assert reseau.n_parameters() < MAX_PARAMETRES


def test_erreur_stratifiee_par_orientation(tmp_path: Path) -> None:
    reseau = _entraine(tmp_path)
    xs, ys, oris = _jeu(seed=5, n=32)
    noms = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
    errors: dict[str, list[float]] = {name: [] for name in noms}
    for x, y, ori in zip(xs, ys, oris, strict=True):
        sector = noms[int(((ori.deg % 360.0) + 22.5) // 45.0) % 8]
        errors[sector].append(abs(reseau.evaluate(x, ori) - y))
    for sector, vals in errors.items():
        if not vals:
            continue
        assert float(np.mean(vals)) < 25.0, f"échec sur {sector}"


def test_accord_de_signe_point_de_controle(tmp_path: Path) -> None:
    reseau = _entraine(tmp_path)
    sud = Orientation(deg=180.0)
    points = np.stack(
        [np.array([0.0, 0.0, c, 4.5, c, 0.0, 12.0 - c, 4.5]) for c in (4.5, 5.5, 6.5, 7.5)]
    )
    rapport = validate_gradient(
        reseau,
        points,
        sud,
        seed=17,
        reference=_SIM,
        step=0.10,
        sign_threshold=0.80,
    )
    assert rapport.sign_agreement > 0.80
    assert rapport.passed


def test_empreinte_divergente_leve(tmp_path: Path) -> None:
    xs, ys, oris = _jeu(seed=3, n=12)
    dense = DenseSurrogate()
    dense.fit(xs, ys, oris, seed=3, epochs=8, lr=0.12)
    path = tmp_path / "dense.npz"
    dense.save(path)
    reseau = LearnedSurrogate(path, "0" * 64, frozen=True)
    with pytest.raises(InvariantViolation):
        reseau.n_parameters()


def test_dense_implements_fingerprintable() -> None:
    """PLAN.md phase 4, block 6, item 23: an explicit fingerprint, not attribute guessing."""
    xs, ys, oris = _jeu(seed=5, n=12)
    dense = DenseSurrogate()
    dense.fit(xs, ys, oris, seed=5, epochs=8, lr=0.12)
    assert isinstance(dense, Fingerprintable)
    # Same bytes as the old guessing fallback in ``uq.registry._model_fingerprint``,
    # run on a plain object without ``weights_fingerprint``: tokens issued before the
    # protocol existed still verify.
    legacy = SimpleNamespace(
        W1=dense.W1, b1=dense.b1, W2=dense.W2, b2=dense.b2, W3=dense.W3, b3=float(dense.b3)
    )
    assert dense.weights_fingerprint == _model_fingerprint(legacy)


def test_freezing_an_untrained_dense_model_raises(tmp_path: Path) -> None:
    """Behaviour change (block 6): no token from an untrained model, no silent mismatch."""
    with pytest.raises(InvariantViolation):
        freeze_and_issue(DenseSurrogate(), timestamp="2026-09-29T00:00:00Z")
    xs, ys, oris = _jeu(seed=7, n=12)
    dense = DenseSurrogate()
    dense.fit(xs, ys, oris, seed=7, epochs=8, lr=0.12)
    token = freeze_and_issue(dense, timestamp="2026-09-29T00:00:00Z")
    with pytest.raises(InvariantViolation):
        DataManagement(tmp_path).for_calibration(token, DenseSurrogate())


def test_an_untrained_model_refuses_to_fingerprint() -> None:
    with pytest.raises(InvariantViolation):
        _ = DenseSurrogate().weights_fingerprint


def test_freeze_and_issue_uses_the_explicit_fingerprint(tmp_path: Path) -> None:
    """``uq.registry._model_fingerprint`` takes the ``weights_fingerprint`` fast path."""
    xs, ys, oris = _jeu(seed=7, n=12)
    dense = DenseSurrogate()
    dense.fit(xs, ys, oris, seed=7, epochs=8, lr=0.12)
    token = freeze_and_issue(dense, timestamp="2026-09-29T00:00:00Z")
    assert token.weights_fingerprint == dense.weights_fingerprint
