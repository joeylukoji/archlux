"""``light`` and ``certify`` are lazy facades (PLAN.md phase 4, block 1).

Asking for one name of the package must import only the module that defines it (plus
whatever that module itself genuinely needs), not every sibling submodule. Each check
runs in a fresh interpreter (``subprocess``, like ``test_import_cost.py``): importing
``archlux`` earlier in the same process would already have loaded numpy and friends,
masking a regression.
"""

from __future__ import annotations

import subprocess
import sys


def run(code: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-W", "ignore", "-c", code], capture_output=True, text=True, check=False
    )


def test_light_daylight_does_not_load_the_other_surrogates() -> None:
    code = (
        "import sys\n"
        "from archlux import light\n"
        "_ = light.Daylight\n"
        "loaded = [m for m in sys.modules if m.startswith('archlux.light.')]\n"
        "assert 'archlux.light.analytic' not in loaded, loaded\n"
        "assert 'archlux.light.split_flux' not in loaded, loaded\n"
    )
    result = run(code)
    assert result.returncode == 0, result.stderr


def test_light_analytic_surrogate_is_still_reachable() -> None:
    code = (
        "from archlux import light\n"
        "from archlux.light.analytic import AnalyticSurrogate\n"
        "assert light.AnalyticSurrogate is AnalyticSurrogate\n"
    )
    result = run(code)
    assert result.returncode == 0, result.stderr


def test_certify_render_does_not_load_the_proof_or_the_bound() -> None:
    code = (
        "import sys\n"
        "from archlux import certify\n"
        "_ = certify.render\n"
        "loaded = [m for m in sys.modules if m.startswith('archlux.certify.')]\n"
        "assert 'archlux.certify.proof' not in loaded, loaded\n"
        "assert 'archlux.certify.bound' not in loaded, loaded\n"
    )
    result = run(code)
    assert result.returncode == 0, result.stderr


def test_certify_verify_exactly_is_still_reachable() -> None:
    code = (
        "from archlux import certify\n"
        "from archlux.certify.proof import verify_exactly\n"
        "assert certify.verify_exactly is verify_exactly\n"
    )
    result = run(code)
    assert result.returncode == 0, result.stderr
