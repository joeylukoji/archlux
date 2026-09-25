"""Validity before and after legalize, milestone 2 review (PLAN.md phase 2).

2x2 tilings, a load-bearing wall on their cut, minimum areas at 80 % of the smallest room
of each type, one fault per plan. Raw rows, seed 17, byte-stable: no timing (§9 budgets).
"""

import csv
import sys
from pathlib import Path

import archlux as ax
from archlux.certify import verify_exactly
from archlux.data.corruption import corrompre
from archlux.data.synthese import TAILLE_MAX, generer_corpus

SEED = 17
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "resultats") / "j2_validity_raw.csv"
FIELDS = ("plan_id", "amplitude_m", "pavage", "valid_before", "status", "valid_after", "seed")


def context(plan: ax.Plan) -> ax.Contexte:
    cut = next(r.x + r.w for r in plan.pieces if r.id == "sw")
    wall = ax.Mur("lb", (cut, 0.0), (cut, 9.0), porteur=True)
    kinds = sorted({r.type for r in plan.pieces})
    minima = tuple((t, 0.8 * min(r.w * r.h for r in plan.pieces if r.type == t)) for t in kinds)
    return ax.Contexte(
        ax.Structure((wall,)), ax.Orientation(0.0), plan.contour, ax.Referentiel(minima, 1.0)
    )


with OUT.open("w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, (*FIELDS, "max_displacement_m"), lineterminator="\n")
    writer.writeheader()
    for k, (plan_id, plan) in enumerate(sorted(generer_corpus(TAILLE_MAX, seed=SEED).items())):
        ctx = context(plan)
        for amplitude in (0.1, 0.25, 0.5):
            seed = SEED * 1000 + k * 10 + int(amplitude * 20)
            faulty, _ = corrompre(plan, seed=seed, amplitude=amplitude)
            for pavage in (False, True):
                row = {"plan_id": plan_id, "amplitude_m": amplitude, "pavage": pavage, "seed": seed}
                row["valid_before"] = verify_exactly(faulty, ctx).valide
                try:
                    out = ax.legalize(faulty, ctx, pavage=pavage)
                    geometry = out.certificat.geometrie  # type: ignore[union-attr]
                    row |= {"status": "ok", "valid_after": geometry.valide}
                    row["max_displacement_m"] = f"{geometry.deplacement_max:.6f}"
                except ax.ArchluxError as error:
                    row |= {"status": type(error).__name__, "valid_after": False}
                writer.writerow(row)
