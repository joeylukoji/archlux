"""Coverage before and after selection (spec 1.4): the protocol, not its numbers."""

from __future__ import annotations

import math

import numpy as np
import pytest

from archlux.bench.selection import (
    PROCEDURES,
    AffineSurrogate,
    below_target,
    fit_affine,
    guarantee,
    run_selection_protocol,
    summarize,
    to_markdown,
    two_room_variants,
)
from archlux.errors import InvariantViolation
from archlux.light.analytic import AnalyticSurrogate
from archlux.light.split_flux import SplitFluxOracle
from archlux.types import Orientation


def _identity_policy(model, q):  # type: ignore[no-untyped-def]
    return lambda x, orientation: x


@pytest.fixture(scope="module")
def run():  # type: ignore[no-untyped-def]
    return run_selection_protocol(
        two_room_variants(120, seed=3),
        base=AnalyticSurrogate(),
        oracle=SplitFluxOracle(),
        make_policy=_identity_policy,
        seed=3,
        repetitions=2,
    )


def test_identity_policy_selects_nothing(run) -> None:  # type: ignore[no-untyped-def]
    rows, _ = run
    passive = [r.covered for r in rows if r.procedure == "passive"]
    selected = [r.covered for r in rows if r.procedure == "passive_on_selected"]
    assert passive == selected
    assert all(r.displacement == 0.0 for r in rows)


def test_every_test_row_comes_from_a_test_source(run) -> None:  # type: ignore[no-untyped-def]
    rows, info = run
    assert {r.procedure for r in rows} == set(PROCEDURES)
    for record in info.records:
        assert record["n_calibration_passive"] >= 9
        assert record["guarantee_passive_on_selected"].startswith("not guaranteed")
    # 30 test sources x 4 azimuths x 3 procedures x 2 repetitions
    assert len(rows) == 30 * 4 * 3 * 2


def test_summary_reports_repetition_intervals(run) -> None:  # type: ignore[no-untyped-def]
    rows, info = run
    summaries = summarize(rows, seed=1)
    overall = [s for s in summaries if s.stratum == "all"]
    assert [s.procedure for s in overall] == list(PROCEDURES)
    assert all(s.rep_low <= s.mean_over_repetitions <= s.rep_high for s in overall)
    assert "Guarantee of each procedure" in to_markdown(summaries, info, alpha=0.1)


def test_guarantee_refuses_too_small_calibration() -> None:
    assert guarantee("policy", 5, 0.10).startswith("refused")
    assert guarantee("passive", 50, 0.10).startswith("guaranteed")
    with pytest.raises(InvariantViolation):
        guarantee("other", 50, 0.10)


def test_below_target_needs_several_repetitions(run) -> None:  # type: ignore[no-untyped-def]
    rows, _ = run
    one = [r for r in rows if r.repetition == 0]
    assert not any(below_target(s, 0.10) for s in summarize(one, seed=1))
    assert all(math.isnan(s.rep_high) for s in summarize(one, seed=1))


def test_same_seed_same_rows_other_seed_other_split() -> None:
    kwargs = {
        "base": AnalyticSurrogate(),
        "oracle": SplitFluxOracle(),
        "make_policy": _identity_policy,
        "repetitions": 1,
    }
    variants = two_room_variants(80, seed=4)
    first, _ = run_selection_protocol(variants, seed=9, **kwargs)
    again, _ = run_selection_protocol(variants, seed=9, **kwargs)
    other, _ = run_selection_protocol(variants, seed=10, **kwargs)
    assert first == again
    assert {r.source for r in first} != {r.source for r in other}


def test_affine_rescaling_scales_value_gradient_and_sigma() -> None:
    base = AnalyticSurrogate()
    x, o = np.array([0.0, 0.0, 6.0, 4.5, 6.0, 0.0, 6.0, 4.5]), Orientation(30.0)
    wrapped = AffineSurrogate(base=base, scale=2.0, offset=1.0)
    assert wrapped.evaluate(x, o) == pytest.approx(1.0 + 2.0 * base.evaluate(x, o))
    assert np.allclose(wrapped.gradient(x, o), 2.0 * np.asarray(base.gradient(x, o)))
    assert wrapped.uncertainty(x, o) == pytest.approx(2.0 * base.uncertainty(x, o))
    xs = [np.array([0.0, 0.0, c, 4.5, c, 0.0, 12.0 - c, 4.5]) for c in (4.0, 8.0)]
    values = [base.evaluate(v, o) for v in xs]
    reversed_truth = -np.array(values)  # the reference decreases where the surrogate grows
    with pytest.raises(InvariantViolation, match="non-positive"):
        fit_affine(base, xs, [o, o], reversed_truth)
