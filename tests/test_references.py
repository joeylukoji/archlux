"""Frozen reference cases (PLAN.md §0: at least five), compared byte for byte.

Each case legalizes a fixed plan and records the repaired rooms and the geometric
certificate. Any change of behaviour of the oracle (``lmo``) or of the certificate
(``certify``) changes a file here, so the change is visible in review instead of being
discovered by a user. Coordinates are rounded to the micrometre, below every tolerance
of ``archlux.tolerances``, so that the files do not depend on the last bits of the LP
solver.

To refreeze after an intended change (a major version, see ``CHANGELOG.md``)::

    ARCHLUX_FREEZE=1 pytest tests/test_references.py
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path

import pytest

import archlux as ax
from archlux.data.corruption import corrupt
from archlux.data.synthetic import generate_corpus
from archlux.seeds import derive

ROOT = Path(__file__).resolve().parents[1]
REFERENCES = ROOT / "tests" / "references"
EXAMPLE_AREAS = (("living_room", 14.0), ("bedroom", 9.0), ("kitchen", 4.0), ("bathroom", 3.0))


def _example(name: str) -> tuple[ax.Plan, ax.Context]:
    plan = ax.Plan.from_json(ROOT / "examples" / f"{name}.json")
    walls = tuple(w for w in plan.walls if w.load_bearing)
    regulation = ax.Regulation(min_areas=EXAMPLE_AREAS, min_width=0.90)
    return plan, ax.Context(
        ax.Structure(walls), ax.Orientation(0.0), regulation, outline=plan.outline
    )


def _synthetic(index: int, amplitude: float) -> tuple[ax.Plan, ax.Context]:
    plan_id, plan = sorted(generate_corpus(index + 1, seed=17).items())[index]
    faulty, _ = corrupt(plan, seed=derive(17, f"references/{plan_id}"), amplitude=amplitude)
    kinds = sorted({r.type for r in plan.rooms})
    minima = tuple((t, 0.8 * min(r.w * r.h for r in plan.rooms if r.type == t)) for t in kinds)
    ctx = ax.Context(
        ax.Structure(()), ax.Orientation(0.0), ax.Regulation(minima, 1.0), outline=plan.outline
    )
    return faulty, ctx


CASES: dict[str, Callable[[], tuple[ax.Plan, ax.Context]]] = {
    "t2": lambda: _example("t2"),
    "t3_load_bearing": lambda: _example("t3_load_bearing"),
    "generated": lambda: _example("generated"),
    "synthetic_0_a025": lambda: _synthetic(0, 0.25),
    "synthetic_1_a050": lambda: _synthetic(1, 0.50),
}


def _snapshot(name: str) -> str:
    plan, ctx = CASES[name]()
    fixed = ax.legalize(plan, ctx, tiling=True)
    assert fixed.certificate is not None
    proof = fixed.certificate.geometry
    rooms = [
        {
            "id": r.id,
            "type": r.type,
            **{k: round(getattr(r, k), 6) + 0.0 for k in ("x", "y", "w", "h")},
        }
        for r in sorted(fixed.rooms, key=lambda r: r.id)
    ]
    record = {
        "case": name,
        "valid": proof.valid,
        "max_displacement_m": round(proof.max_displacement, 6),
        "rooms": rooms,
    }
    return json.dumps(record, indent=2, sort_keys=True) + "\n"


@pytest.mark.reference
@pytest.mark.parametrize("name", sorted(CASES))
def test_reference_case(name: str) -> None:
    path = REFERENCES / f"legalize_{name}.json"
    current = _snapshot(name)
    if os.environ.get("ARCHLUX_FREEZE") == "1":
        path.write_text(current, encoding="utf-8", newline="\n")
    assert path.read_text(encoding="utf-8") == current, f"{path.name} changed"
