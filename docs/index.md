# archlux

**Corriger un plan généré vers la validité géométrique en préservant sa performance
lumineuse. La géométrie est garantie ; la performance est bornée.**

Un générateur a rendu ce plan : le séjour déborde de 5 cm sur la chambre, et 3 cm de
vide séparent la chambre de la salle de bain. `legalize` le corrige et prouve le résultat.

```python
from pathlib import Path

import archlux as ax

Path("sortie_generateur.json").write_text(
    """{
      "schema": "1",
      "contour": [[0, 0], [12, 0], [12, 9], [0, 9]],
      "pieces": [
        {"id": "sejour", "type": "sejour", "x": 0, "y": 0, "w": 6.05, "h": 9},
        {"id": "chambre", "type": "chambre", "x": 6, "y": 0, "w": 6, "h": 5},
        {"id": "sdb", "type": "salle_de_bain", "x": 6, "y": 5.03, "w": 6, "h": 3.97}
      ],
      "murs": [], "ouvertures": [], "certificat": null
    }""",
    encoding="utf-8",
)

plan = ax.Plan.from_json("sortie_generateur.json")
ctx = ax.Contexte(
    structure=ax.Structure(murs_porteurs=()),
    orientation=ax.Orientation(deg=0.0),
    contour=plan.contour,
    referentiel=ax.Referentiel(aires_min=(("salle_de_bain", 5.0),), largeur_min=1.0),
)
q = ax.legalize(plan, ctx, pavage=True)  # pavage : les pièces couvrent tout le contour
print(q.certificat.rapport())
```

Le plus rapide pour commencer : la [galerie d'exemples](galerie/01-corriger-un-plan.md).
Le plus important à comprendre : [les deux garanties](concepts/deux-garanties.md).
Pour refaire les calculs : le [formulaire](formules/index.md) (énoncé, dérivation,
source, cas d'utilisation).
