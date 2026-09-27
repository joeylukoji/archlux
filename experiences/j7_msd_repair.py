"""Repair of corrupted MSD plans, milestone 7 (PLAN.md phase 2): raw rows, root seed 17,
the derived seeds of the published run. Usage: j7_msd_repair.py MSD_CSV [N] [OUT_DIR]. MSD is
not redistributed (docs/donnees/msd.md). No timing column (§9). Summary: j7_msd_summary.py."""

import csv
import sys
from pathlib import Path

import archlux as ax
from archlux.certify import verify_exactly
from archlux.data.chargeurs import load_msd
from archlux.data.corruption import MODES, corrupt
from archlux.seeds import derive

MSD, N = Path(sys.argv[1]), int(sys.argv[2]) if len(sys.argv) > 2 else 300
OUT = Path(sys.argv[3] if len(sys.argv) > 3 else "resultats") / "j7_repair_raw.csv"
FIELDS = ("plan_id", "fault", "amplitude_m", "pavage", "n_rooms", "valid_before", "status")
with OUT.open("w", newline="", encoding="utf-8") as handle:
    writer = csv.writer(handle, lineterminator="\n")
    writer.writerow((*FIELDS, "valid_after", "max_displacement_m", "seed"))
    for apartment in load_msd(MSD, limit=N):
        for fault in MODES:
            for amplitude in (0.10, 0.25, 0.50, 1.00):
                seed = derive(17, f"{apartment.id}:{fault}:{amplitude}")
                plan, applied = corrupt(
                    apartment.plan, seed=seed, amplitude=amplitude, modes=(fault,)
                )
                if not applied:
                    continue
                before = verify_exactly(plan, apartment.context).valid
                for pavage in (False, True):
                    try:
                        out = ax.legalize(
                            plan, apartment.context, fusions=apartment.merges, pavage=pavage
                        )
                        proof = out.certificate.geometry  # type: ignore[union-attr]
                        result = ("ok", proof.valid, f"{proof.max_displacement:.6f}")
                    except ax.ArchluxError as error:
                        result = (type(error).__name__, False, "")
                    head = (
                        apartment.id,
                        fault,
                        amplitude,
                        pavage,
                        len(plan.rooms),
                        before,
                    )
                    writer.writerow((*head, *result, seed))
