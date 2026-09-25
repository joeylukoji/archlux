"""Regenerate every figure of ``resultats/`` with one command (PLAN.md phase 2 exit gate).

Usage (from the repository root)::

    python scripts/resultats.py                 # synthetic experiments + SHA256SUMS
    python scripts/resultats.py --check         # regenerate elsewhere, compare fingerprints
    python scripts/resultats.py --msd CSV       # + milestone 7 on the MSD corpus
    python scripts/resultats.py --hd JSONL --label etoile   # + milestones 8 and 9

``make resultats``, ``make check-resultats`` and ``make resultats-corpus`` call it. The
synthetic experiments take a few minutes (IFC validation: about 4); the corpora are not
redistributed (``docs/donnees/``). Every script has a fixed seed and writes no timing, so
its output is byte-stable on one platform; ``SHA256SUMS`` records it.
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "experiences"
SYNTHETIC: dict[str, tuple[str, ...]] = {
    "j2_validity.py": ("j2_validity_raw.csv",),
    "j3_orientation.py": (
        "j3_orientation.csv",
        "j3_orientation_min0.svg",
        "j3_orientation_min12.svg",
    ),
    "j4_gradient.py": ("j4_gradient.csv",),
    "j5_coverage.py": ("j5_coverage.csv",),
    "j6_active.py": ("j6_active.csv",),
    "j6_ifc.py": ("j6_ifc.csv",),
}
"""Script -> files it writes into its output directory."""
SUMS = "SHA256SUMS"


def _run(script: str, *args: str) -> None:
    print(f"== {script} {' '.join(args)}", flush=True)
    subprocess.run([sys.executable, str(EXPERIMENTS / script), *args], cwd=ROOT, check=True)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def synthetic(out: Path) -> dict[str, str]:
    """Run every synthetic experiment into ``out``; return name -> SHA-256."""
    out.mkdir(parents=True, exist_ok=True)
    for script in SYNTHETIC:
        _run(script, str(out))
    return {name: _digest(out / name) for names in SYNTHETIC.values() for name in names}


def _write_sums(digests: dict[str, str], path: Path) -> None:
    lines = [f"{digest}  {name}" for name, digest in sorted(digests.items())]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _read_sums(path: Path) -> dict[str, str]:
    pairs = (line.split("  ", 1) for line in path.read_text("utf-8").splitlines() if line)
    return {name: digest for digest, name in pairs}


def check() -> int:
    """Regenerate into a temporary directory and compare with ``resultats/SHA256SUMS``."""
    expected = _read_sums(ROOT / "resultats" / SUMS)
    with tempfile.TemporaryDirectory() as tmp:
        found = synthetic(Path(tmp))
    differ = sorted(name for name in expected if found.get(name) != expected[name])
    for name in differ:
        print(f"DIFFERS: {name}")
    print("all figures reproduced" if not differ else f"{len(differ)} file(s) differ")
    return 1 if differ else 0


def corpus(msd: Path | None, hd: Path | None, label: str) -> None:
    """Milestones 7 (MSD) and 8-9 (HouseDiffusion outputs), when their data is given."""
    out = ROOT / "resultats"
    if msd is not None:
        _run("j7_msd_repair.py", str(msd), "300", str(out))
        _run("j7_msd_summary.py", str(out / "j7_repair_raw.csv"), str(out / "j7_repair.md"))
        _run("j7_msd_idempotence.py", str(msd), "400", str(out))
    if hd is not None:
        _run("j8_generation.py", str(hd), str(10**9), label)
        _run("j9_orientation.py", str(hd))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="compare, do not overwrite")
    parser.add_argument("--msd", type=Path, help="MSD CSV (milestone 7)")
    parser.add_argument("--hd", type=Path, help="HouseDiffusion plans JSONL (milestones 8-9)")
    parser.add_argument("--label", default="etoile", help="label of the JSONL set")
    args = parser.parse_args()
    if args.check:
        return check()
    _write_sums(synthetic(ROOT / "resultats"), ROOT / "resultats" / SUMS)
    corpus(args.msd, args.hd, args.label)
    return 0


if __name__ == "__main__":
    sys.exit(main())
