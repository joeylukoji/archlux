"""Validity before and after legalize, milestone 2 review (PLAN.md phase 2): 2x2 tilings,
a load-bearing wall on their cut, minimum areas at 80 % of the smallest room of each type,
one fault per plan. Raw rows, seed 17, byte-stable: no timing (§9 budgets).

Each attempt goes through ``certify.run_repair``: ``outcome`` is repaired / rejected /
infeasible / computation_failure, ``validator_valid`` and ``evidence`` come from the
independent validator re-run on the returned plan (``exact`` or ``numeric``).
Statistical unit: the source plan (``plan_id``); its 3 amplitudes x 2 strategies are
not independent."""

import csv
import sys
from pathlib import Path

import archlux as ax
from archlux.certify import run_repair, verify_exactly
from archlux.data.corruption import corrupt
from archlux.data.synthetic import MAX_SIZE, generate_corpus
from archlux.seeds import derive

SEED = 17
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "results") / "j2_validity_raw.csv"
FIELDS = ("plan_id", "amplitude_m", "pavage", "valid_before", "status", "valid_after", "seed")
CHECK = ("outcome", "validator_valid", "evidence", "refused_constraints")


def context(plan: ax.Plan) -> ax.Context:
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


with OUT.open("w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, (*FIELDS, "max_displacement_m", *CHECK), lineterminator="\n")
    writer.writeheader()
    for plan_id, plan in sorted(generate_corpus(MAX_SIZE, seed=SEED).items()):
        ctx = context(plan)
        for amplitude in (0.1, 0.25, 0.5):
            seed = derive(SEED, f"j2/{plan_id}/{amplitude}")
            faulty, _ = corrupt(plan, seed=seed, amplitude=amplitude)
            for pavage in (False, True):
                row = {"plan_id": plan_id, "amplitude_m": amplitude, "pavage": pavage, "seed": seed}
                row["valid_before"] = verify_exactly(faulty, ctx).valid
                report = run_repair(
                    faulty, ctx, legalize=ax.legalize, plan_id=plan_id, tiling=pavage
                )
                repaired = report.status == "repaired"
                row["status"] = "ok" if repaired else (report.error_type or report.status)
                row["valid_after"] = repaired
                if report.max_displacement_m is not None and repaired:
                    row["max_displacement_m"] = f"{report.max_displacement_m:.6f}"
                final = report.final
                row["outcome"] = report.status
                row["validator_valid"] = final.valid if final is not None else False
                row["evidence"] = final.evidence if final is not None else "-"
                refused = () if final is None else (*final.violated, *final.unknown)
                hard = sorted(r.spec.id for r in refused if r.spec.kind == "hard")
                row["refused_constraints"] = ";".join(hard)
                writer.writerow(row)
