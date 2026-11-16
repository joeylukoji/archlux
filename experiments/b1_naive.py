"""Naive local repair against legalize on the B1 corpus (same plans, faults and seed as
``j2_validity.py``): does a global optimisation beat moving each room on its own? Raw
rows, seed 17, byte-stable. Validity is the exact validator's verdict."""

import csv
import sys
from pathlib import Path

from archlux.bench.naive import naive_repair
from archlux.certify import verify_exactly
from archlux.data.corruption import corrupt
from archlux.data.synthetic import MAX_SIZE, b1_context, generate_corpus
from archlux.seeds import derive

SEED = 17


OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "results") / "b1_naive_raw.csv"

with OUT.open("w", newline="", encoding="utf-8") as handle:
    writer = csv.writer(handle, lineterminator="\n")
    writer.writerow(("plan_id", "amplitude_m", "valid_before", "naive_valid", "seed"))
    for plan_id, plan in sorted(generate_corpus(MAX_SIZE, seed=SEED).items()):
        ctx = b1_context(plan)
        for amplitude in (0.1, 0.25, 0.5):
            seed = derive(SEED, f"j2/{plan_id}/{amplitude}")
            faulty, _ = corrupt(plan, seed=seed, amplitude=amplitude)
            fixed = naive_repair(faulty)
            row = (plan_id, amplitude, verify_exactly(faulty, ctx).valid)
            writer.writerow((*row, verify_exactly(fixed, ctx).valid, seed))
