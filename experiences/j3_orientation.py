"""Même plan, huit orientations — jalon 3. API publique + substitut analytique."""
from __future__ import annotations

import csv
from pathlib import Path

import archlux as ax
from archlux.light.analytique import SubstitutAnalytique
from archlux.orient.circulaire import rayleigh

C = ((0.0, 0.0), (12.0, 0.0), (12.0, 9.0), (0.0, 9.0))
plan = ax.Plan((
    ax.Piece("sw", "sejour", 0, 0, 6, 4.5), ax.Piece("se", "chambre", 6, 0, 6, 4.5),
    ax.Piece("nw", "sejour", 0, 4.5, 6, 4.5), ax.Piece("ne", "chambre", 6, 4.5, 6, 4.5),
), (), (), C)
obj, l1, actifs = SubstitutAnalytique(), None, []
svg = ["<svg xmlns='http://www.w3.org/2000/svg' width='960' height='140'>"]
out = Path("resultats/j3_orientation.csv")
out.parent.mkdir(exist_ok=True)
with out.open("w", newline="", encoding="utf-8") as handle:
    w = csv.DictWriter(
        handle, fieldnames=("deg", "divergent_de_l1", "gain", "h_sw", "h_nw")
    )
    w.writeheader()
    for i, deg in enumerate(range(0, 360, 45)):
        ctx = ax.Contexte(ax.Structure(()), ax.Orientation(float(deg)), C, ax.Referentiel((), 1.0))
        if l1 is None:
            l1 = {p.id: (p.w, p.h) for p in ax.legalize(plan, ctx).pieces}
        rec = {p.id: p for p in ax.legalize(plan, ctx, objective=obj).pieces}
        gain = sum(abs(rec[k].w - l1[k][0]) + abs(rec[k].h - l1[k][1]) for k in l1)
        if gain > 1e-3:
            actifs.append(float(deg))
        w.writerow({"deg": deg, "divergent_de_l1": gain > 1e-3, "gain": gain,
                    "h_sw": rec["sw"].h, "h_nw": rec["nw"].h})
        ox = 10 + i * 118
        for p in rec.values():
            x, y = ox + p.x * 9, 10 + (9 - p.y - p.h) * 12
            svg.append(
                f"<rect x='{x:.1f}' y='{y:.1f}' width='{p.w*9:.1f}' "
                f"height='{p.h*12:.1f}' fill='none' stroke='#333'/>"
            )
        svg.append(f"<text x='{ox}' y='130' font-size='11'>{deg}°</text>")
svg.append("</svg>")
Path("resultats/j3_orientation.svg").write_text("\n".join(svg), encoding="utf-8")
print("n_divergent", len(actifs), "rayleigh_p", rayleigh(actifs)[1] if len(actifs) >= 2 else "n/a")
