"""Repair of corrupted MSD plans, milestone 7 (PLAN.md phase 2): raw rows, root seed 17,
the derived seeds of the published run. Usage: j7_msd_repair.py MSD_CSV [N] [OUT_DIR]. MSD is
not redistributed (docs/data/msd.md). No timing column (§9). Summary: j7_msd_summary.py.

Each attempt goes through ``certify.run_repair`` (outcome repaired / rejected / infeasible /
computation_failure, independent validator verdict and evidence). ``n_rooms_after`` and
``min_side_after`` say whether the repair kept every room (spec 1.7). Statistical unit:
the dwelling (``plan_id``), not the corruption."""

import csv
import sys
from pathlib import Path

import archlux as ax
from archlux.certify import run_repair, verify_exactly
from archlux.data.corruption import MODES, corrupt
from archlux.data.loaders import load_msd
from archlux.seeds import derive

MSD, N = Path(sys.argv[1]), int(sys.argv[2]) if len(sys.argv) > 2 else 300
OUT = Path(sys.argv[3] if len(sys.argv) > 3 else "results") / "j7_repair_raw.csv"
FIELDS = ("plan_id", "fault", "amplitude_m", "pavage", "n_rooms", "valid_before", "status")
AFTER = ("valid_after", "max_displacement_m", "seed", "n_rooms_after", "min_side_after")
CHECK = ("outcome", "validator_valid", "evidence", "refused_constraints")


def attempt(plan: ax.Plan, apartment, pavage: bool) -> tuple[object, ...]:
    """One repair through ``run_repair``; the returned plan is kept for its rooms."""
    returned: list[ax.Plan] = []

    def legalize(*args, **kwargs):
        out = ax.legalize(*args, **kwargs)
        returned.append(out)
        return out

    report = run_repair(
        plan,
        apartment.context,
        legalize=legalize,
        plan_id=apartment.id,
        merges=apartment.merges,
        tiling=pavage,
    )
    final = report.final
    refused = () if final is None else (*final.violated, *final.unknown)
    check = (
        report.status,
        final.valid if final is not None else False,
        final.evidence if final is not None else "-",
        ";".join(sorted(r.spec.id for r in refused if r.spec.kind == "hard")),
    )
    if report.status != "repaired":
        return (report.error_type or report.status, False, "", "", "", *check)
    out = returned[0]
    side = min(min(r.w, r.h) for r in out.rooms)
    moved = f"{report.max_displacement_m:.6f}"
    return ("ok", True, moved, len(out.rooms), f"{side:.6f}", *check)


with OUT.open("w", newline="", encoding="utf-8") as handle:
    writer = csv.writer(handle, lineterminator="\n")
    writer.writerow((*FIELDS, *AFTER, *CHECK))
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
                    status, valid, moved, rooms, side, *check = attempt(plan, apartment, pavage)
                    head = (apartment.id, fault, amplitude, pavage, len(plan.rooms), before)
                    writer.writerow((*head, status, valid, moved, seed, rooms, side, *check))
