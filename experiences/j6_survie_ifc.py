"""Mesurer le taux de survie IFC sur un mélange valide / pathologique."""

from __future__ import annotations

import csv
import tempfile
from pathlib import Path

from archlux.export import diagnostiquer, survival_rate, to_ifc
from archlux.types import Mur, Piece, Plan

RACINE = Path(__file__).resolve().parents[1]
CONTOUR = ((0.0, 0.0), (12.0, 0.0), (12.0, 9.0), (0.0, 9.0))


def _sain(i: int) -> Plan:
    return Plan(
        pieces=(
            Piece(id=f"a{i}", type="sejour", x=0.0, y=0.0, w=6.0, h=9.0),
            Piece(id=f"b{i}", type="chambre", x=6.0, y=0.0, w=6.0, h=9.0),
        ),
        murs=(Mur(id=f"m{i}", a=(0.0, 0.0), b=(12.0, 0.0), porteur=True),),
        ouvertures=(),
        contour=CONTOUR,
    )


def _mauvais(i: int) -> Plan:
    return Plan(
        pieces=(
            Piece(id=f"a{i}", type="sejour", x=0.0, y=0.0, w=7.0, h=9.0),
            Piece(id=f"b{i}", type="chambre", x=6.0, y=0.0, w=6.0, h=9.0),
        ),
        murs=(Mur(id=f"nul{i}", a=(1.0, 1.0), b=(1.0, 1.0), porteur=False),),
        ouvertures=(),
        contour=CONTOUR,
    )


plans = [_sain(i) for i in range(40)] + [_mauvais(i) for i in range(10)]
taux, (lo, hi) = survival_rate(plans)

n_ok = 0
with tempfile.TemporaryDirectory() as tmp:
    for i, plan in enumerate(plans):
        rapport = to_ifc(plan, Path(tmp) / f"{i}.ifc", validate=True)
        if rapport.valide:
            n_ok += 1

csv_path = RACINE / "resultats" / "j6_survie_ifc.csv"
csv_path.parent.mkdir(parents=True, exist_ok=True)
with csv_path.open("w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(["n", "succes", "taux", "wilson_lo", "wilson_hi"])
    w.writerow([len(plans), n_ok, f"{taux:.6f}", f"{lo:.6f}", f"{hi:.6f}"])

print("taux", taux, "wilson", (lo, hi), "exportes", n_ok)
assert n_ok == sum(1 for p in plans if diagnostiquer(p).exportable)
