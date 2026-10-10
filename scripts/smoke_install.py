"""Smoke test of an installed archlux, run by CI against the wheel (PLAN.md phase 5).

The exit gate of phase 5 asks for ``pip install archlux`` in a clean environment,
followed by the README example, on Linux, Windows and macOS. This script runs, against
whatever ``archlux`` is importable (CI installs the built wheel in a fresh virtual
environment, so the repository's ``src/`` is not on the path):

1. every ``python`` block of README.md, in order, in a temporary directory;
2. ``examples/legalize_examples.py``;
3. the ``archlux`` console script on each example plan (``verify``, ``legalize``).

Usage: ``python scripts/smoke_install.py`` from the repository root. Exits non-zero on
the first failure.
"""

from __future__ import annotations

import os
import re
import runpy
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_PYTHON_BLOCK = re.compile(r"^```python\n(.*?)^```", re.MULTILINE | re.DOTALL)


def _check_installed_copy() -> None:
    """Refuse to run against the source tree: the point is to test the wheel."""
    import archlux

    location = Path(archlux.__file__).resolve()
    if ROOT / "src" in location.parents:
        sys.exit(f"archlux is imported from the source tree ({location}), not from a wheel")
    print(f"archlux {archlux.__version__} from {location.parent}")


def _run_readme(workdir: Path) -> None:
    """Run the README's python blocks in order, in one namespace, inside ``workdir``.

    Parameters
    ----------
    workdir : Path
        Empty directory the examples may write into.
    """
    blocks = _PYTHON_BLOCK.findall((ROOT / "README.md").read_text("utf-8"))
    namespace: dict[str, object] = {"__name__": "__readme__"}
    cwd = Path.cwd()
    os.chdir(workdir)
    try:
        for index, source in enumerate(blocks, start=1):
            exec(compile(source, f"README.md [block {index}/{len(blocks)}]", "exec"), namespace)
    finally:
        os.chdir(cwd)
    print(f"README: {len(blocks)} blocks ran")


def _run_cli(workdir: Path) -> None:
    """Run the ``archlux`` console script on every example plan.

    Parameters
    ----------
    workdir : Path
        Directory for the legalized output files.
    """
    exe = shutil.which("archlux")
    if exe is None:
        sys.exit("the archlux console script is not on PATH")
    for plan in sorted((ROOT / "examples").glob("*.json")):
        fixed = workdir / f"fixed-{plan.name}"
        legalize = [exe, "legalize", str(plan), "--tiling", "--min-width", "0.9", "-o", str(fixed)]
        subprocess.run(legalize, check=True)
        subprocess.run([exe, "verify", str(fixed), "--min-width", "0.9"], check=True)
        print(f"CLI: {plan.name} legalized and verified")


def main() -> None:
    """Run the three smoke checks against the installed package."""
    _check_installed_copy()
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        _run_readme(work)
        runpy.run_path(str(ROOT / "examples" / "legalize_examples.py"), run_name="__main__")
        _run_cli(work)
    print("smoke test passed")


if __name__ == "__main__":
    main()
