"""Round-2 integration: the certificate carries what was checked and how the run stopped.

- the independent validator's summary is attached to every legalized plan, and the
  report's geometry banner follows its evidence (``[EXACT]`` / ``[NUMERIC]``);
- the Frank-Wolfe stop status is surfaced; a guarded surrogate that refuses its
  gradient stops the run as ``untrusted_gradient``, never as ``converged``;
- ``max_iter``, ``penalty`` and ``stall_window`` reach Frank-Wolfe through ``legalize``;
- a calibration fitted on the frozen policy's outputs gives the ``policy_calibrated``
  regime, and is refused under other settings;
- the run report records the out-of-distribution check and the gain status.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np
import pytest

import archlux
from archlux.api import legalize_policy_settings
from archlux.certify.bound import PolicyCalibration, calibrate_policy, policy_settings
from archlux.certify.run import RunReport, run_repair
from archlux.errors import InvalidInput
from archlux.io.json_io import from_dict, to_dict
from archlux.light.analytic import AnalyticSurrogate
from archlux.light.objective import Daylight
from archlux.light.split_flux import SplitFluxOracle
from archlux.light.trust import GuardedSurrogate
from archlux.types import Certificate, GeometricProof, OptimizationStatus, ValidationSummary
from tests.properties.strategies import DEFAULT_CONTEXT


def _plan() -> archlux.Plan:
    """Two rooms tiling the default 12 m x 9 m outline, off-centre."""
    return archlux.Plan(
        rooms=(
            archlux.Room(id="a", type="living_room", x=0.0, y=0.0, w=5.0, h=9.0),
            archlux.Room(id="b", type="bedroom", x=5.0, y=0.0, w=7.0, h=9.0),
        ),
        walls=(),
        openings=(),
        outline=DEFAULT_CONTEXT.outline,
    )


def _proof() -> GeometricProof:
    return GeometricProof(True, False, False, True, True, 0.0)


def _objective() -> Daylight:
    return Daylight(AnalyticSurrogate(), q_hat=1.0)


def _certificate(plan: archlux.Plan) -> Certificate:
    assert plan.certificate is not None
    return plan.certificate


class Negated(SplitFluxOracle):
    """The oracle with its gradient flipped: right values, wrong direction."""

    def gradient(self, x, orientation, *, glazing=None):  # type: ignore[no-untyped-def]
        return -super().gradient(x, orientation, glazing=glazing)


# --- Validation on the certificate, honest banner ---------------------------------------


def test_every_legalized_plan_carries_the_validator_summary() -> None:
    certificate = _certificate(archlux.legalize(_plan(), DEFAULT_CONTEXT))
    summary = certificate.validation
    assert summary is not None and summary.valid and summary.evidence == "exact"
    assert "rooms.no_overlap" in summary.checked and not summary.failing
    assert "fire safety" in summary.scope
    assert certificate.optimization is None  # classic mode: no Frank-Wolfe


def test_the_report_states_the_independent_check() -> None:
    text = _certificate(archlux.legalize(_plan(), DEFAULT_CONTEXT)).report()
    assert "[EXACT]" in text and "Independent check" in text


def test_a_numeric_validation_is_not_stamped_exact() -> None:
    numeric = ValidationSummary(evidence="numeric", plan_fingerprint="f", checked=("a",))
    text = Certificate(geometry=_proof(), validation=numeric).report()
    assert "[EXACT]" not in text and "[NUMERIC]" in text
    assert "not an exact proof" in text


def test_a_certificate_without_validation_keeps_its_historical_banner() -> None:
    assert "[EXACT]" in Certificate(geometry=_proof()).report()


def test_a_refused_summary_needs_a_failing_constraint() -> None:
    with pytest.raises(InvalidInput):
        ValidationSummary(evidence="refused", plan_fingerprint="f")
    with pytest.raises(InvalidInput):
        ValidationSummary(evidence="exact", plan_fingerprint="f", failing=("x",))


def test_validation_and_optimization_survive_json() -> None:
    out = archlux.legalize(_plan(), DEFAULT_CONTEXT, objective=_objective())
    again = from_dict(to_dict(out))
    assert again.certificate == out.certificate
    assert _certificate(again).optimization is not None


def test_an_old_certificate_without_the_new_keys_still_reads() -> None:
    data = to_dict(replace(_plan(), certificate=Certificate(geometry=_proof())))
    assert "validation" not in data["certificate"]  # absent, not null: bytes unchanged
    assert _certificate(from_dict(data)).validation is None


def test_an_infinite_gap_round_trips_as_null() -> None:
    status = OptimizationStatus(status="oracle_inconsistent", iterations=2, gap=float("inf"))
    plan = replace(_plan(), certificate=Certificate(geometry=_proof(), optimization=status))
    data = to_dict(plan)
    assert data["certificate"]["optimization"]["gap"] is None
    assert from_dict(data).certificate == plan.certificate


# --- Untrusted gradient and stop status ---------------------------------------------------


def test_a_refused_gradient_stops_as_untrusted_not_converged() -> None:
    guard = GuardedSurrogate(Negated(), SplitFluxOracle())
    out, trace = archlux.legalize_trace(_plan(), DEFAULT_CONTEXT, objective=guard)
    assert guard.refusals >= 1
    assert trace is not None and trace.status == "untrusted_gradient" and not trace.converged
    status = _certificate(out).optimization
    assert status is not None and status.status == "untrusted_gradient"
    assert not status.converged
    assert "NOT an optimised plan" in _certificate(out).report()


def test_a_trusted_guard_is_not_flagged() -> None:
    oracle = SplitFluxOracle()
    guard = GuardedSurrogate(oracle, oracle)
    _, trace = archlux.legalize_trace(_plan(), DEFAULT_CONTEXT, objective=guard)
    assert trace is not None and trace.status != "untrusted_gradient"


# --- Frank-Wolfe settings through legalize ------------------------------------------------


def test_max_iter_reaches_frank_wolfe() -> None:
    _, trace = archlux.legalize_trace(_plan(), DEFAULT_CONTEXT, objective=_objective(), max_iter=1)
    assert trace is not None and len(trace.iterations) <= 2  # k = -1 plus one step
    assert dict(trace.parameters)["max_iter"] == "1"


def test_stall_window_and_penalty_reach_frank_wolfe() -> None:
    _, trace = archlux.legalize_trace(
        _plan(), DEFAULT_CONTEXT, objective=_objective(), penalty=0.5, stall_window=3
    )
    assert trace is not None
    assert dict(trace.parameters)["stall_window"] == "3"
    assert float(dict(trace.parameters)["penalty"]) == 0.5


def test_a_penalty_never_moves_the_plan_further() -> None:
    free = archlux.legalize(_plan(), DEFAULT_CONTEXT, objective=_objective(), budget=1.0)
    tied = archlux.legalize(
        _plan(), DEFAULT_CONTEXT, objective=_objective(), budget=1.0, penalty=10.0
    )
    moved = [_certificate(p).geometry.max_displacement for p in (free, tied)]
    assert moved[1] <= moved[0] + 1e-9


@pytest.mark.parametrize(
    ("option", "value"),
    [
        ("max_iter", 0),
        ("max_iter", 2.5),
        ("penalty", -1.0),
        ("penalty", float("nan")),
        ("stall_window", 1),
    ],
)
def test_bad_optimizer_settings_are_refused_before_solving(option: str, value: object) -> None:
    with pytest.raises(InvalidInput) as refusal:
        archlux.legalize(_plan(), DEFAULT_CONTEXT, objective=_objective(), **{option: value})  # type: ignore[arg-type]
    assert refusal.value.field == option


# --- Policy-calibrated regime -------------------------------------------------------------


def _policy_calibration(**settings: object) -> PolicyCalibration:
    rng = np.random.default_rng(3)
    predictions = rng.normal(50.0, 5.0, 60)
    truths = predictions + rng.normal(0.0, 1.0, 60)
    objective = _objective()
    return calibrate_policy(
        predictions,
        truths,
        np.ones(60),
        indicator=objective.indicator,
        settings=legalize_policy_settings(objective, **settings),  # type: ignore[arg-type]
    )


def test_a_policy_calibration_gives_a_guaranteed_policy_regime() -> None:
    calibration = _policy_calibration()
    out = archlux.legalize(
        _plan(), DEFAULT_CONTEXT, objective=_objective(), calibration=calibration
    )
    bound = _certificate(out).performance
    assert bound is not None and bound.regime == "policy_calibrated"
    assert bound.coverage_guaranteed and bound.n_calibration == 60
    assert "policy-calibrated" in _certificate(out).report()


def test_a_policy_calibration_of_another_policy_is_refused() -> None:
    calibration = _policy_calibration(max_iter=10)
    with pytest.raises(InvalidInput, match="policy"):
        archlux.legalize(_plan(), DEFAULT_CONTEXT, objective=_objective(), calibration=calibration)


def test_a_passive_calibration_still_reads_selected() -> None:
    passive = _policy_calibration().calibration
    out = archlux.legalize(_plan(), DEFAULT_CONTEXT, objective=_objective(), calibration=passive)
    bound = _certificate(out).performance
    assert bound is not None and bound.regime == "selected"


def test_policy_settings_are_sorted_and_name_the_objective() -> None:
    pairs = policy_settings(_objective(), budget=None, max_iter=50)
    assert list(pairs) == sorted(pairs)
    assert dict(pairs)["objective"] == "Daylight" and dict(pairs)["budget"] == "None"


# --- Run report: out-of-distribution flag and gain status ---------------------------------


@dataclass(frozen=True)
class _Verdict:
    distance: float
    uncertain: bool


def test_the_run_report_records_ood_and_gain_status() -> None:
    report = run_repair(
        _plan(),
        DEFAULT_CONTEXT,
        legalize=archlux.legalize,
        plan_id="p0",
        objective=_objective(),
        ood_check=lambda plan: _Verdict(distance=4.2, uncertain=True),
        gain_status="closed_form_only",
    )
    assert report.status == "repaired"
    assert report.ood_distance == 4.2 and report.ood_uncertain is True
    assert report.gain_status == "closed_form_only"
    assert any("training distribution" in w for w in report.warnings)
    # Without a trace, iterations and stop status come from the certificate.
    assert report.iterations is not None and report.stop_status is not None
    assert RunReport.from_dict(report.to_dict()) == report


def test_a_run_report_without_the_new_keys_still_reads() -> None:
    report = run_repair(_plan(), DEFAULT_CONTEXT, legalize=archlux.legalize, plan_id="p1")
    data = report.to_dict()
    for key in ("ood_distance", "ood_uncertain", "gain_status"):
        del data[key]
    assert RunReport.from_dict(data) == report
