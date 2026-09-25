"""Idempotence of legalize on real MSD plans, milestone 7 (PLAN.md phase 2).

A valid plan must come out unchanged (the L1 optimum is then e = 0). Usage:
python experiences/j7_msd_idempotence.py MSD_CSV [N_APARTMENTS] [OUT_DIR]. MSD is not
redistributed (docs/donnees/msd.md). Byte-stable: no timing (§9 budgets).
"""

import sys
from pathlib import Path

import numpy as np

import archlux as ax
from archlux.certify import verify_exactly
from archlux.data.chargeurs import StatistiquesChargement, charger_msd

MSD, N = Path(sys.argv[1]), int(sys.argv[2]) if len(sys.argv) > 2 else 400
OUT = Path(sys.argv[3] if len(sys.argv) > 3 else "resultats") / "j7_msd_idempotence.md"
stats = StatistiquesChargement()
valid_before = valid_after = refused = 0
moved: list[float] = []
sizes: list[int] = []
for apartment in charger_msd(MSD, statistiques=stats, limite=N):
    valid_before += verify_exactly(apartment.plan, apartment.contexte).valide
    sizes.append(len(apartment.plan.pieces))
    try:
        out = ax.legalize(apartment.plan, apartment.contexte, fusions=apartment.fusions)
    except ax.ArchluxError:
        refused += 1
        continue
    valid_after += out.certificat.geometrie.valide  # type: ignore[union-attr]
    moved.append(out.certificat.geometrie.deplacement_max)  # type: ignore[union-attr]
n = stats.retenus
OUT.write_text(
    "# Milestone 7: idempotence on MSD\n\n"
    f"```\n{stats.resume()}\n```\n\n"
    f"apartments evaluated: {n}\n"
    f"sub-rectangles: median {int(np.median(sizes))}, max {max(sizes)}\n"
    f"valid before legalize: {valid_before}/{n}\n"
    f"valid after legalize: {valid_after}/{n}\n"
    f"refused: {refused}\n"
    f"max displacement: median {np.median(moved):.6f} m, max {max(moved):.6f} m\n",
    encoding="utf-8",
)
