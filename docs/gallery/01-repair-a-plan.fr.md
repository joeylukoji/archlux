# Corriger un plan généré

Géométrie d'exemple : enveloppe **12 m × 9 m** du corpus de tests publié
(`CONTEXTE_DEFAUT`), pas une pièce inventée pour la documentation.

**Problème.** Un générateur a produit deux pièces qui se recouvrent d'un mètre, tout
en couvrant l'enveloppe. Le plan n'est pas constructible.

**Solution.**

```python
import archlux as ax

outline = ((0.0, 0.0), (12.0, 0.0), (12.0, 9.0), (0.0, 9.0))
plan = ax.Plan(
    rooms=(
        ax.Room(id="living_room", type="living_room", x=0.0, y=0.0, w=7.0, h=9.0),
        ax.Room(id="bedroom", type="bedroom", x=6.0, y=0.0, w=6.0, h=9.0),
    ),
    walls=(),
    openings=(),
    outline=outline,
)
ctx = ax.Context(
    structure=ax.Structure(load_bearing_walls=()),
    orientation=ax.Orientation(deg=0.0),
    outline=outline,
    regulation=ax.Regulation(min_areas=(), min_width=1.0),
)
q = ax.legalize(plan, ctx)
print(q.certificate.geometry.valid)
print(round(q.certificate.geometry.max_displacement, 2))
```

**Résultat.**

```
True
1.0
```

Le séjour passe de 7 m à 6 m de large ; la chambre ne bouge pas. Aucun chevauchement,
aucun jour. La preuve est **exacte** : `certify.proof` recompte les aires, indépendamment
du solveur.

**Ce qu'il faut retenir.** `legalize` minimise le déplacement L1 sous le polytope des
plans valides de même ordre relatif. La disposition (qui est à gauche de qui) est
conservée ; seules les cotes bougent.

Formule : [épigraphe L1](../formulas/l1-epigraph.md),
[pipeline](../formulas/pipeline.md).

**Voir aussi :** [Détecter une infaisabilité](03-detect-infeasibility.md),
[Le polytope](../concepts/polytope.md)
