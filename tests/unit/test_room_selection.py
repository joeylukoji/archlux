"""Per-room coverage and the ensemble sigma_hat (spec 1.4): the protocol, not its numbers."""

from __future__ import annotations

import numpy as np
import pytest

from archlux.bench.ensemble import EnsembleSurrogate, fit_dense_ensemble
from archlux.bench.room_selection import (
    ROOM_IDS,
    ROOM_TYPES,
    RoomAffineSurrogate,
    four_room_plan,
    four_room_variants,
    run_room_protocol,
    write_room_rows,
)
from archlux.bench.selection import summarize
from archlux.certify.proof import verify_exactly
from archlux.errors import InvariantViolation
from archlux.geom.polytope import decision_vector
from archlux.light.analytic import AnalyticSurrogate
from archlux.light.split_flux import SplitFluxOracle
from archlux.types import Context, Orientation, Regulation, Structure


def _identity_policy(model, q):  # type: ignore[no-untyped-def]
    return lambda x, orientation: x


@pytest.fixture(scope="module")
def run():  # type: ignore[no-untyped-def]
    return run_room_protocol(
        four_room_variants(80, seed=3),
        base=AnalyticSurrogate(),
        oracle=SplitFluxOracle(),
        make_policy=_identity_policy,
        seed=3,
        repetitions=2,
    )


def test_four_room_plans_are_valid_typed_and_round_trip() -> None:
    variants = four_room_variants(5, seed=1)
    assert len(variants) == 20
    assert four_room_variants(5, seed=1)[7].x.tolist() == variants[7].x.tolist()
    for v in variants:
        plan = four_room_plan(v.x, v.room_types)
        context = Context(Structure(()), v.orientation, Regulation((), 1.0), outline=plan.outline)
        assert verify_exactly(plan, context).valid
        assert decision_vector(plan).tolist() == v.x.tolist()
        assert sorted(v.room_types) == sorted(ROOM_TYPES)


def test_disjoint_pools_have_disjoint_ids() -> None:
    a = {v.id.source for v in four_room_variants(3, seed=1)}
    b = {v.id.source for v in four_room_variants(3, seed=1, prefix="pool")}
    assert not a & b


def test_identity_policy_selects_nothing_and_rows_carry_room_types(run) -> None:  # type: ignore[no-untyped-def]
    rows, info = run
    passive = [r.covered for r in rows if r.procedure == "passive"]
    assert passive == [r.covered for r in rows if r.procedure == "passive_on_selected"]
    assert {r.room_type for r in rows} == set(ROOM_TYPES)
    assert all(r.sample.rsplit("/", 1)[1] in ROOM_IDS for r in rows)
    # 20 test sources x 4 azimuths x 4 rooms x 3 procedures x 2 repetitions
    assert len(rows) == 20 * 4 * 4 * 3 * 2
    for record in info.records:
        # one room of one variant per source in each calibration half
        assert record["n_calibration_passive"] == 10
        assert record["n_calibration_policy"] == 10


def test_summary_by_room_type_and_csv(run, tmp_path) -> None:  # type: ignore[no-untyped-def]
    rows, _ = run
    strata = {s.stratum for s in summarize(rows, seed=1, keys=("room_type",))}
    assert {f"room_type={t}" for t in ROOM_TYPES} <= strata
    out = tmp_path / "rooms.csv"
    write_room_rows(out, rows)
    lines = out.read_text(encoding="utf-8").splitlines()
    assert lines[0].endswith("room_type,covered")
    assert len(lines) == len(rows) + 1


def test_room_affine_plan_value_is_the_sum_of_its_rooms() -> None:
    v = four_room_variants(1, seed=2)[0]
    model = RoomAffineSurrogate(base=AnalyticSurrogate(), scale=2.0, offset=1.5)
    rooms = model.evaluate_rooms(v.x, v.orientation)
    assert model.evaluate(v.x, v.orientation) == pytest.approx(float(rooms.sum()))
    base = AnalyticSurrogate().evaluate_rooms(v.x, v.orientation)
    assert rooms == pytest.approx(1.5 + 2.0 * base)


def test_ensemble_spread_varies_with_the_plan() -> None:
    pool = four_room_variants(40, seed=5, n_azimuths=1, prefix="pool")
    oracle = SplitFluxOracle()
    ensemble = fit_dense_ensemble(
        [v.x for v in pool],
        [oracle.evaluate(v.x, v.orientation) for v in pool],
        [v.orientation for v in pool],
        k=3,
        seed=5,
        epochs=5,
    )
    sigmas = {round(ensemble.uncertainty(v.x, v.orientation), 9) for v in pool[:10]}
    assert len(sigmas) > 1
    v = pool[0]
    grads = [m.gradient(v.x, v.orientation) for m in ensemble.members]
    assert ensemble.gradient(v.x, v.orientation) == pytest.approx(np.mean(grads, axis=0))


def test_an_ensemble_needs_two_members_of_one_indicator() -> None:
    with pytest.raises(InvariantViolation):
        EnsembleSurrogate(members=(AnalyticSurrogate(),))
    with pytest.raises(InvariantViolation):
        fit_dense_ensemble([np.zeros(16)] * 3, [0.0] * 3, [Orientation(0.0)] * 3, k=1, seed=1)
