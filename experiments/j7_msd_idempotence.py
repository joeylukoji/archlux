"""Idempotence of legalize on real MSD plans, milestone 7 (PLAN.md phase 2).

A valid plan must come out unchanged (the L1 optimum is then e = 0). Usage:
python experiments/j7_msd_idempotence.py MSD_CSV [N_APARTMENTS] [OUT_DIR]. MSD is not
redistributed (docs/data/msd.md). Byte-stable: no timing (§9 budgets).

Each apartment goes through ``certify.run_repair``; one raw row per apartment goes to
``j7_msd_idempotence_raw.csv`` so the apartment behind the maximum displacement is named.
"""

import csv
import sys
from pathlib import Path

import numpy as np

import archlux as ax
from archlux.certify import run_repair, verify_exactly
from archlux.data.loaders import LoadStatistics, load_msd

MSD, N = Path(sys.argv[1]), int(sys.argv[2]) if len(sys.argv) > 2 else 400
OUT = Path(sys.argv[3] if len(sys.argv) > 3 else "results") / "j7_msd_idempotence.md"
RAW = OUT.with_name("j7_msd_idempotence_raw.csv")
FIELDS = ("plan_id", "n_rooms", "valid_before", "outcome", "validator_valid", "evidence")
stats = LoadStatistics()
valid_before = valid_after = refused = 0
moved: list[tuple[float, str]] = []
sizes: list[int] = []
with RAW.open("w", newline="", encoding="utf-8") as handle:
    writer = csv.writer(handle, lineterminator="\n")
    writer.writerow((*FIELDS, "max_displacement_m"))
    for apartment in load_msd(MSD, stats=stats, limit=N):
        before = verify_exactly(apartment.plan, apartment.context).valid
        valid_before += before
        sizes.append(len(apartment.plan.rooms))
        report = run_repair(
            apartment.plan,
            apartment.context,
            legalize=ax.legalize,
            plan_id=apartment.id,
            merges=apartment.merges,
        )
        final = report.final
        row = (apartment.id, len(apartment.plan.rooms), before, report.status)
        row += (final.valid if final else False, final.evidence if final else "-")
        if report.status != "repaired":
            refused += 1
            writer.writerow((*row, ""))
            continue
        valid_after += 1
        distance = report.max_displacement_m or 0.0
        moved.append((distance, apartment.id))
        writer.writerow((*row, f"{distance:.6f}"))
n = stats.kept
largest, worst = max(moved) if moved else (0.0, "-")
median = float(np.median([d for d, _ in moved])) if moved else 0.0
OUT.write_text(
    "# Milestone 7: idempotence on MSD\n\n"
    f"```\n{stats.summary()}\n```\n\n"
    f"apartments evaluated: {n}\n"
    f"sub-rectangles: median {int(np.median(sizes))}, max {max(sizes)}\n"
    f"valid before legalize: {valid_before}/{n}\n"
    f"valid after legalize: {valid_after}/{n} (independent validator)\n"
    f"refused: {refused}\n"
    f"max displacement: median {median:.6f} m, max {largest:.6f} m (apartment {worst})\n"
    f"raw rows: {RAW.name}\n",
    encoding="utf-8",
)
