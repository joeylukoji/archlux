"""Idempotence de legalize sur corpus reel MSD — jalon 7.

Un plan deja valide doit ressortir inchange : l'optimum L1 est alors e = 0.
Corpus non redistribue : passer le chemin du CSV en argument.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

import archlux as ax
from archlux.certify.proof import verify_exactly
from archlux.data.chargeurs import StatistiquesChargement, charger_msd

CSV = Path(sys.argv[1] if len(sys.argv) > 1 else "D:/archlux-donnees/msd/mds_V2_5.372k.csv")
CIBLE = int(sys.argv[2]) if len(sys.argv) > 2 else 400

stats = StatistiquesChargement()
avant = apres = echecs = 0
depl: list[float] = []
temps: list[float] = []
tailles: list[int] = []
for appart in charger_msd(CSV, statistiques=stats, limite=CIBLE):
    avant += verify_exactly(appart.plan, appart.contexte).valide
    tailles.append(len(appart.plan.pieces))
    debut = time.perf_counter()
    try:
        corrige = ax.legalize(appart.plan, appart.contexte, fusions=appart.fusions)
    except ax.ArchluxError:
        echecs += 1
        continue
    temps.append((time.perf_counter() - debut) * 1000.0)
    apres += corrige.certificat.geometrie.valide
    depl.append(corrige.certificat.geometrie.deplacement_max)

n = stats.retenus
Path("resultats").mkdir(exist_ok=True)
Path("resultats/j7_msd_idempotence.md").write_text(
    "# Jalon 7 — idempotence sur MSD\n\n"
    f"{stats.resume()}\n\n"
    f"appartements evalues : {n}\n"
    f"sous-rectangles : median {int(np.median(tailles))}, max {max(tailles)}\n"
    f"valides avant legalize : {avant}/{n}\n"
    f"valides apres legalize : {apres}/{n}\n"
    f"echecs : {echecs}\n"
    f"deplacement max : median {np.median(depl):.6f} m, max {max(depl):.6f} m\n"
    f"temps : median {np.median(temps):.1f} ms, p90 {np.percentile(temps, 90):.1f} ms\n",
    encoding="utf-8",
)
print(
    f"n={n} avant={avant} apres={apres} echecs={echecs} "
    f"depl_max={max(depl):.6f} temps_median={np.median(temps):.1f} ms"
)
