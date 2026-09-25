"""Neutrality check of the rename waves (PLAN.md 3.9, wave 0).

A rename must not change what the library computes. This script legalizes a fixed corpus
(the deterministic scenarios of ``benchmarks/guarantees``, in three modes) and fingerprints
the outputs with SHA-256; ``tests/references/neutrality.json`` holds the reference
fingerprints, recorded before the renames began.

The reference records its platform: the LP solver may pick another optimal vertex on
another operating system, so ``tests/test_neutrality.py`` compares strictly only there.

Two fingerprints, because two things can change:

``json``
    The plans as written by ``vers_dict`` (schema v1), floats rounded to a micrometre.
    Waves 1 to 3 (names of exceptions, classes, fields) must keep it **identical**: the
    JSON keys are an explicit v1 mapping, not the Python field names.
``geometry``
    Only what the plans *mean*: the rectangles, the validity flags and the displacement,
    with no key and no type name. Wave 4 (JSON v2, English room types) changes the text of
    the JSON on purpose, and keeps this one identical.

Usage::

    python scripts/neutrality.py            # print the fingerprints
    python scripts/neutrality.py --update   # record them as the new reference
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from benchmarks.guarantees.scenarios import Scenario, generate, perturb  # noqa: E402

from archlux import ArchluxError, Plan, legalize  # noqa: E402
from archlux.io.json_io import vers_dict  # noqa: E402
from archlux.light.analytique import SubstitutAnalytique  # noqa: E402

REFERENCE = ROOT / "tests" / "references" / "neutrality.json"
N_SCENARIOS = 40
SEED = 17
DECIMALS = 6


def _canonical(value: object) -> object:
    """Rounded floats, so that the last bit of an LP solution cannot flip a hash."""
    if isinstance(value, float):
        return round(value, DECIMALS) + 0.0
    if isinstance(value, dict):
        return {key: _canonical(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_canonical(item) for item in value]
    return value


def _geometry(plan: Plan) -> list[object]:
    """What a plan means, with no name in it: rectangles, proof flags, displacement."""
    proof = plan.certificat.geometry if plan.certificat else None  # type: ignore[union-attr]
    rooms = [[round(v, DECIMALS) + 0.0 for v in (p.x, p.y, p.w, p.h)] for p in plan.pieces]
    flags = [] if proof is None else [proof.valide, round(proof.max_displacement, DECIMALS)]
    return [rooms, flags]


def _attempt(mode: str, scenario: Scenario, index: int, surrogate: SubstitutAnalytique) -> Plan:
    """One legalization of the corpus: exact input, noisy input with tiling, or with light."""
    if mode == "noisy":
        noisy = perturb(scenario.plan, seed=index)
        return legalize(noisy, scenario.context, pavage=True)
    if mode == "light":
        return legalize(scenario.plan, scenario.context, objective=surrogate)
    return legalize(scenario.plan, scenario.context)


def _outputs() -> list[tuple[str, Plan | None]]:
    """Every (label, legalized plan or None if refused) of the corpus, in a fixed order."""
    results: list[tuple[str, Plan | None]] = []
    surrogate = SubstitutAnalytique()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for wall in ("full", "partial"):
            for index in range(N_SCENARIOS):
                scenario = generate(SEED, index, wall)  # type: ignore[arg-type]
                for mode in ("valid", "noisy", "light"):
                    label = f"{wall}/{index}/{mode}"
                    try:
                        results.append((label, _attempt(mode, scenario, index, surrogate)))
                    except ArchluxError:
                        results.append((label, None))
    return results


def fingerprints() -> dict[str, object]:
    """The two fingerprints of the corpus, and its size."""
    outputs = _outputs()
    as_json, as_geometry = hashlib.sha256(), hashlib.sha256()
    for label, plan in outputs:
        text = (
            "refused" if plan is None else json.dumps(_canonical(vers_dict(plan)), sort_keys=True)
        )
        as_json.update(f"{label}:{text}\n".encode())
        meaning = "refused" if plan is None else json.dumps(_geometry(plan))
        as_geometry.update(f"{label}:{meaning}\n".encode())
    refused = sum(plan is None for _, plan in outputs)
    return {
        "platform": sys.platform,
        "n_runs": len(outputs),
        "n_refused": refused,
        "json": as_json.hexdigest(),
        "geometry": as_geometry.hexdigest(),
    }


def main(argv: list[str] | None = None) -> int:
    """Print the fingerprints, or record them with ``--update``."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--update", action="store_true", help="record the reference")
    args = parser.parse_args(argv)
    found = fingerprints()
    print(json.dumps(found, indent=2))
    if args.update:
        REFERENCE.write_text(json.dumps(found, indent=2) + "\n", encoding="utf-8")
        print(f"recorded in {REFERENCE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
