"""Naive local repair against legalize on the B1 corpus (same plans, faults and seed as
``j2_validity.py``): does a global optimisation beat moving each room on its own? Raw
rows, seed 17, byte-stable. Validity is the exact validator's verdict."""

import csv
import sys
from pathlib import Path

import archlux as ax
from archlux.bench.naive import naive_repair
from archlux.certify import verify_exactly
from archlux.data.corruption import corrupt
from archlux.data.synthetic import MAX_SIZE, generate_corpus
from archlux.seeds import derive

SEED = 17


def context(plan: ax.Plan) -> ax.Context:
    """The B1 context: load-bearing wall on the cut, minima at 80 % per type."""
    cut = next(r.x + r.w for r in plan.rooms if r.id == "sw")
    wall = ax.Wall(id="lb", a=(cut, 0.0), b=(cut, 9.0), load_bearing=True)
    kinds = sorted({r.type for r in plan.rooms})
    minima = tuple((t, 0.8 * min(r.w * r.h for r in plan.rooms if r.type == t)) for t in kinds)
    return ax.Context(
        structure=ax.Structure((wall,)),
        orientation=ax.Orientation(0.0),
        outline=plan.outline,
        regulation=ax.Regulation(minima, 1.0),
    )


OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "results") / "b1_naive_raw.csv"

with OUT.open("w", newline="", encoding="utf-8") as handle:
    writer = csv.writer(handle, lineterminator="\n")
    writer.writerow(("plan_id", "amplitude_m", "valid_before", "naive_valid", "seed"))
    for plan_id, plan in sorted(generate_corpus(MAX_SIZE, seed=SEED).items()):
        ctx = context(plan)
        for amplitude in (0.1, 0.25, 0.5):
            seed = derive(SEED, f"j2/{plan_id}/{amplitude}")
            faulty, _ = corrupt(plan, seed=seed, amplitude=amplitude)
            fixed = naive_repair(faulty)
            row = (plan_id, amplitude, verify_exactly(faulty, ctx).valid)
            writer.writerow((*row, verify_exactly(fixed, ctx).valid, seed))
