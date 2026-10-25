"""Out-of-distribution flag and model card of a surrogate (spec 1.3)."""

from __future__ import annotations

import math

import numpy as np

from archlux.light.base import DenseSurrogate
from archlux.light.card import SurrogateCard, surrogate_card, training_fingerprint
from archlux.light.ood import fit_envelope, flagged_prediction
from archlux.light.reference import ClosedFormReference
from archlux.light.split_flux import SplitFluxOracle
from archlux.types import Orientation


def _plan(c: float) -> np.ndarray:
    return np.array([0.0, 0.0, c, 4.5, c, 0.0, 12.0 - c, 4.5])


def _draw(rng: np.random.Generator, n: int) -> tuple[list[np.ndarray], list[Orientation]]:
    xs = [_plan(c) for c in rng.uniform(5.0, 7.0, n)]
    return xs, [Orientation(deg=float(d)) for d in rng.uniform(0.0, 360.0, n)]


TRAIN, ORIS = _draw(np.random.default_rng(3), 60)
HELD = _draw(np.random.default_rng(4), 60)


def test_an_extrapolated_plan_is_flagged_uncertain() -> None:
    envelope = fit_envelope(TRAIN, ORIS, calibration=HELD, alpha=0.05)
    assert not envelope.calibrated_on_training and math.isfinite(envelope.threshold)
    inside = envelope.check(_plan(6.0), Orientation(deg=30.0))
    outside = envelope.check(_plan(11.5), Orientation(deg=30.0))
    assert not inside.uncertain
    assert outside.uncertain and outside.distance > inside.distance


def test_held_out_plans_stay_mostly_within_the_envelope() -> None:
    envelope = fit_envelope(TRAIN, ORIS, calibration=HELD, alpha=0.10)
    fresh, oris = _draw(np.random.default_rng(5), 200)
    flagged = [envelope.check(x, o).uncertain for x, o in zip(fresh, oris, strict=True)]
    assert np.mean(flagged) < 0.25


def test_a_too_small_calibration_set_flags_everything() -> None:
    envelope = fit_envelope(TRAIN[:5], ORIS[:5], alpha=0.05)
    assert math.isinf(envelope.threshold) and envelope.calibrated_on_training
    assert envelope.check(TRAIN[0], ORIS[0]).uncertain


def test_the_flag_travels_with_the_prediction() -> None:
    envelope = fit_envelope(TRAIN, ORIS, calibration=HELD)
    oracle = SplitFluxOracle()
    flagged = flagged_prediction(oracle, envelope, _plan(11.5), Orientation(deg=0.0))
    assert flagged.uncertain
    assert flagged.mu == oracle.evaluate(_plan(11.5), Orientation(deg=0.0))


def test_the_card_round_trips_and_ties_the_data() -> None:
    oracle = SplitFluxOracle()
    ys = np.array([oracle.evaluate(x, o) for x, o in zip(TRAIN, ORIS, strict=True)])
    net = DenseSurrogate()
    net.fit(tuple(TRAIN), ys, tuple(ORIS), seed=17, epochs=2, lr=0.1)
    card = surrogate_card(
        net,
        xs=TRAIN,
        ys=ys,
        orientations=ORIS,
        training_ids=[f"t{k}" for k in range(60)],
        label=ClosedFormReference(oracle).measure(TRAIN[0], ORIS[0]),
        seed=17,
        hyperparameters={"epochs": 2, "lr": 0.1},
        metrics={"mae_test": 1.5},
    )
    assert card.model == "DenseSurrogate" and card.label_kind == "closed_form"
    assert card.weights_fingerprint == net.weights_fingerprint
    assert SurrogateCard.from_json(card.to_json()) == card
    assert training_fingerprint(TRAIN, ys, ORIS) == card.training_fingerprint
    assert training_fingerprint(TRAIN, ys + 1.0, ORIS) != card.training_fingerprint
