"""Reparation de plans MSD corrompus — table principale du jalon 7.

Bruts ecrits avant toute agregation. Usage : j7_msd_reparation.py <csv> [n].
"""
from __future__ import annotations

import csv as csvmod
import sys
import time
from pathlib import Path

import archlux as ax
from archlux.bench.graines import deriver
from archlux.certify.preuve import verifier_exactement
from archlux.data.chargeurs import charger_msd
from archlux.data.corruption import MODES, corrompre

CSV = Path(sys.argv[1] if len(sys.argv) > 1 else "D:/archlux-donnees/msd/mds_V2_5.372k.csv")
CIBLE = int(sys.argv[2]) if len(sys.argv) > 2 else 300
GRAINE = 17
AMPLITUDES = (0.10, 0.25, 0.50, 1.00)
CHAMPS = ("plan_id", "mode", "amplitude_m", "pavage", "n_pieces", "valide_avant",
          "valide_apres", "deplacement_max_m", "temps_ms", "statut", "seed")

Path("resultats").mkdir(exist_ok=True)
sortie = Path("resultats/j7_reparation_brut.csv")
with sortie.open("w", newline="", encoding="utf-8") as flux:
    ecrivain = csvmod.DictWriter(flux, fieldnames=CHAMPS)
    ecrivain.writeheader()
    for appart in charger_msd(CSV, limite=CIBLE):
        for mode in MODES:
            for amplitude in AMPLITUDES:
                graine = deriver(GRAINE, f"{appart.identifiant}:{mode}:{amplitude}")
                abime, fautes = corrompre(
                    appart.plan, seed=graine, amplitude=amplitude, modes=(mode,)
                )
                if not fautes:
                    continue
                avant = verifier_exactement(abime, appart.contexte).valide
                for pavage in (False, True):
                    debut = time.perf_counter()
                    statut, valide, depl = "ok", False, ""
                    try:
                        q = ax.legalize(abime, appart.contexte,
                                        fusions=appart.fusions, pavage=pavage)
                        valide = q.certificat.geometrie.valide
                        depl = f"{q.certificat.geometrie.deplacement_max:.6f}"
                    except ax.Infaisable:
                        statut = "infaisable"
                    except ax.InvariantViole as echec:
                        statut = ("trame" if pavage and "structurel" in str(echec)
                                  else "invariant_viole")
                    ecrivain.writerow({
                        "plan_id": appart.identifiant, "mode": mode,
                        "amplitude_m": amplitude, "pavage": pavage,
                        "n_pieces": len(abime.pieces),
                        "valide_avant": avant, "valide_apres": valide,
                        "deplacement_max_m": depl,
                        "temps_ms": f"{(time.perf_counter() - debut) * 1000:.3f}",
                        "statut": statut, "seed": graine,
                    })
print("bruts ecrits :", sortie)
