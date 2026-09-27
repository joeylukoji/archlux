"""A rename must not change what the library computes (PLAN.md 3.9, wave 0).

The reference fingerprints were recorded before the renames (``scripts/neutrality.py``).
A failure here means a change altered the output of ``legalize`` on the fixed corpus:
that is a behaviour change, not a rename. If the change is deliberate, say so in the
CHANGELOG and record a new reference with ``python scripts/neutrality.py --update``.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def current() -> dict[str, object]:
    spec = importlib.util.spec_from_file_location("neutrality", ROOT / "scripts" / "neutrality.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.fingerprints()  # type: ignore[no-any-return]


def reference() -> dict[str, object]:
    path = ROOT / "tests" / "references" / "neutrality.json"
    return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def test_the_corpus_is_deterministic(current: dict[str, object]) -> None:
    """Two runs give the same fingerprints, on any platform."""
    spec = importlib.util.spec_from_file_location("neutrality", ROOT / "scripts" / "neutrality.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.fingerprints() == current


def test_the_corpus_keeps_its_size_and_refusals(current: dict[str, object]) -> None:
    """Refusals are part of the behaviour: a rename must not create or lose one."""
    expected = reference()
    assert current["n_runs"] == expected["n_runs"]
    if current["platform"] == expected["platform"]:
        assert current["n_refused"] == expected["n_refused"]


@pytest.mark.parametrize("kind", ["json", "geometry"])
def test_the_output_matches_the_recorded_reference(current: dict[str, object], kind: str) -> None:
    expected = reference()
    if current["platform"] != expected["platform"]:
        pytest.skip(f"reference recorded on {expected['platform']}, running on {sys.platform}")
    assert current[kind] == expected[kind], (
        f"the {kind} fingerprint changed: legalize no longer gives the recorded output. "
        "A rename must be neutral; for a deliberate change, run "
        "`python scripts/neutrality.py --update` and explain it in the CHANGELOG."
    )
