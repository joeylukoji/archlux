"""Couverture conforme de l'analytique contre SimulateurExact — jamais le réseau."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from archlux.light.analytique import SubstitutAnalytique
from archlux.light.simulateur import SimulateurExact
from archlux.types import Orientation
from archlux.uq.conforme import CalibrateurConforme

sim, modele, rng = SimulateurExact(), SubstitutAnalytique(), np.random.default_rng(17)
pred_c, ver_c, sig_c = [], [], []
for _ in range(120):
    c = float(rng.uniform(4.0, 8.0))
    x = np.array([0.0, 0.0, c, 4.5, c, 0.0, 12.0 - c, 4.5])
    o = Orientation(float(rng.uniform(0.0, 360.0)))
    pred_c.append(modele.evaluer(x, o))
    ver_c.append(sim.evaluer(x, o))
    sig_c.append(modele.incertitude(x, o))
cal = CalibrateurConforme()
cal.ajuster(pred_c, ver_c, sig_c, alpha=0.10)
ok = []
for _ in range(80):
    c = float(rng.uniform(4.0, 8.0))
    x = np.array([0.0, 0.0, c, 4.5, c, 0.0, 12.0 - c, 4.5])
    o = Orientation(float(rng.uniform(0.0, 360.0)))
    p, s = modele.evaluer(x, o), modele.incertitude(x, o)
    b = cal.borne(p, s, ">=")
    ok.append(b.borne_inf <= sim.evaluer(x, o) <= b.borne_sup)
couv = float(np.mean(ok))
Path("resultats/j5_conforme.md").write_text(
    f"# Jalon 5 — conforme\n\nq={cal.q:.4f}\nn={cal.n}\ncouverture_test={couv:.3f}\n",
    encoding="utf-8",
)
print("q", cal.q, "couv", couv)
