"""Edge cases of ``bench.stats``: the refusals and the zero-variance branch (PLAN.md phase 4,
block 15, item 45). Branch coverage was 77 % before these tests."""

from __future__ import annotations

import pytest

from archlux.bench.stats import holm, paired_bootstrap, power, tost
from archlux.errors import InvariantViolation


def test_bootstrap_refuses_mismatched_or_empty_samples() -> None:
    with pytest.raises(InvariantViolation):
        paired_bootstrap([1.0, 2.0], [1.0], seed=0)
    with pytest.raises(InvariantViolation):
        paired_bootstrap([], [], seed=0)


def test_bootstrap_refuses_no_replication() -> None:
    with pytest.raises(InvariantViolation):
        paired_bootstrap([1.0], [0.0], seed=0, n_replications=0)


def test_tost_refuses_mismatched_short_or_nonpositive_margin() -> None:
    with pytest.raises(InvariantViolation):
        tost([1.0, 2.0], [1.0], delta=0.5)
    with pytest.raises(InvariantViolation):
        tost([1.0], [1.0], delta=0.5)
    with pytest.raises(InvariantViolation):
        tost([1.0, 2.0], [1.0, 2.0], delta=0.0)


def test_tost_with_zero_variance_is_decided_by_the_mean_alone() -> None:
    """Every paired difference equal: the standard error is zero, so the test is on the mean."""
    assert tost([3.0, 3.0, 3.0], [1.0, 1.0, 1.0], delta=2.5) == (True, 0.0)
    assert tost([3.0, 3.0, 3.0], [1.0, 1.0, 1.0], delta=0.5) == (False, 1.0)


def test_holm_refuses_empty_family_bad_alpha_or_out_of_range_p() -> None:
    with pytest.raises(InvariantViolation):
        holm([])
    with pytest.raises(InvariantViolation):
        holm([0.01], alpha=1.0)
    with pytest.raises(InvariantViolation):
        holm([1.5])
    with pytest.raises(InvariantViolation):
        holm([float("nan")])


def test_power_refuses_too_few_observations_or_bad_inputs() -> None:
    with pytest.raises(InvariantViolation):
        power(0.5, 1.0, n=1)
    with pytest.raises(InvariantViolation):
        power(0.5, 0.0, n=10)
    with pytest.raises(InvariantViolation):
        power(0.5, 1.0, n=10, alpha=0.0)
