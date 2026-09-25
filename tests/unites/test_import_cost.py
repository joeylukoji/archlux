"""``import archlux`` stays light: the solver stack loads on first use (PLAN.md 3.13).

The gate of phase 3 asks for an import under 0.5 s. ``numpy``, ``scipy.sparse``, ``shapely``
and ``ortools`` alone cost about 1 s, and only ``legalize`` needs them, so the package
exposes ``legalize`` as a lazy attribute, like ``light``, ``bench`` and ``feasibility``.
The first call of ``legalize`` pays for them; ``import archlux`` does not.
"""

from __future__ import annotations

import subprocess
import sys

HEAVY = ("numpy", "scipy", "shapely", "ortools", "networkx", "structlog", "torch")


def run(code: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-W", "ignore", "-c", code], capture_output=True, text=True, check=False
    )


def test_importing_the_package_loads_no_solver_dependency() -> None:
    code = (
        "import sys, archlux\n"
        f"loaded = [m for m in {HEAVY!r} if m in sys.modules]\n"
        "assert not loaded, loaded\n"
    )
    result = run(code)
    assert result.returncode == 0, result.stderr


def test_legalize_is_still_reachable_from_the_package() -> None:
    code = (
        "import archlux\n"
        "from archlux import legalize as imported\n"
        "import archlux.api\n"
        "assert archlux.legalize is archlux.api.legalize is imported\n"
        "assert 'legalize' in archlux.__all__ and 'legalize' in dir(archlux)\n"
    )
    result = run(code)
    assert result.returncode == 0, result.stderr


def test_an_unknown_attribute_still_raises() -> None:
    result = run("import archlux\narchlux.nothing_here\n")
    assert result.returncode != 0
    assert "AttributeError" in result.stderr


def test_the_import_is_fast_enough() -> None:
    """Best of three, in a fresh interpreter: robust to one noisy run."""
    code = "import time; t = time.perf_counter(); import archlux; print(time.perf_counter() - t)"
    best = min(float(run(code).stdout) for _ in range(3))
    assert best < 0.5, f"import archlux took {best:.2f} s (budget 0.5 s)"
