"""IFC export of repaired plans, opened by ifcopenshell (milestone 6 review, PLAN.md phase 2).

The old survival rate (40 healthy + 10 broken plans = 80 %) was set by its input mix, and
no IFC reader opened the files. Here: 90 synthetic plans with a load-bearing wall, one
fault each, repaired with pavage, exported, then validated by ifcopenshell (schema and
rules). Needs the `bim` or `dev` extra. Seed 17, byte-stable.
"""

import csv
import sys
import tempfile
from pathlib import Path

import ifcopenshell
import ifcopenshell.validate

import archlux as ax
from archlux.data.corruption import corrompre
from archlux.data.synthese import TAILLE_MAX, generer_corpus
from archlux.export import to_ifc
from archlux.export.wilson import intervalle_wilson
from archlux.seeds import derive

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "resultats") / "j6_ifc.csv"
N = int(sys.argv[2]) if len(sys.argv) > 2 else TAILLE_MAX  # 2.8 s of validation per file
with tempfile.TemporaryDirectory() as tmp, OUT.open("w", newline="", encoding="utf-8") as handle:
    writer = csv.writer(handle, lineterminator="\n")
    writer.writerow(("plan_id", "exported", "validator_errors"))
    accepted = 0
    for plan_id, plan in sorted(generer_corpus(N, seed=17).items()):
        cut = next(r.x + r.w for r in plan.pieces if r.id == "sw")
        wall = ax.Mur("lb", (cut, 0.0), (cut, 9.0), porteur=True)
        ctx = ax.Contexte(
            ax.Structure((wall,)), ax.Orientation(0.0), plan.contour, ax.Referentiel((), 1.0)
        )
        repaired = ax.legalize(
            corrompre(plan, seed=derive(17, f"ifc/{plan_id}"))[0], ctx, pavage=True
        )
        path = Path(tmp) / f"{plan_id}.ifc"
        exported = to_ifc(
            ax.Plan(repaired.pieces, (wall,), (), plan.contour), path, validate=True
        ).valide
        logger = ifcopenshell.validate.json_logger()
        if exported:
            ifcopenshell.validate.validate(ifcopenshell.open(str(path)), logger, express_rules=True)
        accepted += exported and not logger.statements
        writer.writerow((plan_id, exported, len(logger.statements) if exported else ""))
low, high = intervalle_wilson(accepted, N)
print(f"accepted by ifcopenshell: {accepted}/{N}, Wilson 95 % [{low:.3f}, {high:.3f}]")
