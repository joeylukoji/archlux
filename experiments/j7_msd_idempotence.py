"""Idempotence of legalize on real MSD plans, milestone 7 (PLAN.md phase 2).

A valid plan must come out unchanged (the L1 optimum is then e = 0). Usage:
python experiments/j7_msd_idempotence.py MSD_CSV [N_APARTMENTS] [OUT_DIR]. MSD is not
redistributed (docs/data/msd.md). Byte-stable: no timing (§9 budgets).
"""

import sys
from pathlib import Path

import numpy as np

import archlux as ax
from archlux.certify import verify_exactly
from archlux.data.loaders import LoadStatistics, load_msd

MSD, N = Path(sys.argv[1]), int(sys.argv[2]) if len(sys.argv) > 2 else 400
OUT = Path(sys.argv[3] if len(sys.argv) > 3 else "results") / "j7_msd_idempotence.md"
stats = LoadStatistics()
valid_before = valid_after = refused = 0
moved: list[float] = []
sizes: list[int] = []
for apartment in load_msd(MSD, stats=stats, limit=N):
    valid_before += verify_exactly(apartment.plan, apartment.context).valid
    sizes.append(len(apartment.plan.rooms))
    try:
        out = ax.legalize(apartment.plan, apartment.context, merges=apartment.merges)
    except ax.ArchluxError:
        refused += 1
        continue
    valid_after += out.certificate.geometry.valid  # type: ignore[union-attr]
    moved.append(out.certificate.geometry.max_displacement)  # type: ignore[union-attr]
n = stats.kept
OUT.write_text(
    "# Milestone 7: idempotence on MSD\n\n"
    f"```\n{stats.summary()}\n```\n\n"
    f"apartments evaluated: {n}\n"
    f"sub-rectangles: median {int(np.median(sizes))}, max {max(sizes)}\n"
    f"valid before legalize: {valid_before}/{n}\n"
    f"valid after legalize: {valid_after}/{n}\n"
    f"refused: {refused}\n"
    f"max displacement: median {np.median(moved):.6f} m, max {max(moved):.6f} m\n",
    encoding="utf-8",
)
