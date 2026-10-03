"""Derived seeds and manifest: what makes a run replayable.

`ARCHITECTURE.md` §7 requires a mandatory seed without a default, and the README a
manifest at every run. Both requirements are worth something only if they are tested.
"""

from __future__ import annotations

import datetime as dt

import pytest

from archlux.bench.manifest import emit
from archlux.bench.seeds import derive


class TestDerive:
    """Derivation of named sub-seeds from a root seed."""

    def test_is_deterministic(self) -> None:
        """Two identical calls return the same sub-seed."""
        assert derive(17, "calibration") == derive(17, "calibration")

    def test_two_streams_do_not_share_their_randomness(self) -> None:
        """The point of the derivation: `calibration` and `permutation` diverge.

        Without it, two components draw the same sequence and their results are
        correlated without anything showing it.
        """
        assert derive(17, "calibration") != derive(17, "permutation")

    def test_two_runs_do_not_share_their_randomness(self) -> None:
        """Changing the root seed changes every stream."""
        assert derive(17, "calibration") != derive(18, "calibration")

    def test_returns_a_usable_seed(self) -> None:
        """A non-negative integer, in the range accepted by ``numpy.random``."""
        seed = derive(17, "calibration")
        assert isinstance(seed, int)
        assert 0 <= seed < 2**32

    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("calibration", 313_024_199),
            ("permutation", 2_943_214_233),
            ("entrainement", 2_097_524_390),
        ],
    )
    def test_the_values_are_frozen(self, name: str, expected: int) -> None:
        """**Pinned** values: changing the derivation changes every published result.

        This test has no external source of truth, and cannot have one. Its role is to
        force a change to this file, hence to see the break in review, the day someone
        modifies the hash function. An archived run must stay replayable; these three
        numbers are what enforces it.
        """
        assert derive(17, name) == expected


class TestManifest:
    """Reproducibility manifest emitted at every run."""

    def test_reports_the_seed(self) -> None:
        """The seed is the first thing one reads again six months later."""
        assert emit(seed=17).seed == 17

    def test_the_seed_is_mandatory(self) -> None:
        """No default value: an implicit seed is a lost seed."""
        with pytest.raises(TypeError):
            emit()  # type: ignore[call-arg]

    def test_readable_utc_timestamp(self) -> None:
        """The timestamp is ISO 8601 in UTC, not an ambiguous local time."""
        timestamp = emit(seed=17).timestamp
        instant = dt.datetime.fromisoformat(timestamp)
        assert instant.tzinfo is not None
        assert instant.utcoffset() == dt.timedelta(0)

    def test_reports_the_environment(self) -> None:
        """The Python version is in the manifest; without it, it identifies nothing."""
        environment = dict(emit(seed=17).environment)
        assert "python" in environment

    def test_the_parameters_are_frozen_and_ordered(self) -> None:
        """The parameters become sorted pairs: the fingerprint must be stable."""
        manifest = emit(seed=17, parameters={"max_iter": "50", "budget": "0.25"})
        assert manifest.parameters == (("budget", "0.25"), ("max_iter", "50"))
