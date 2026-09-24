# Corriger un plan généré

Géométrie d'exemple : enveloppe **12 m × 9 m** du corpus de tests publié
(`CONTEXTE_DEFAUT`), pas une pièce inventée pour la documentation.

**Problème.** Un générateur a produit deux pièces qui se recouvrent d'un mètre, tout
en couvrant l'enveloppe. Le plan n'est pas constructible.

**Solution.**

```python
import archlux as ax

contour = ((0.0, 0.0), (12.0, 0.0), (12.0, 9.0), (0.0, 9.0))
plan = ax.Plan(
    pieces=(
        ax.Piece(id="sejour", type="sejour", x=0.0, y=0.0, w=7.0, h=9.0),
        ax.Piece(id="chambre", type="chambre", x=6.0, y=0.0, w=6.0, h=9.0),
    ),
    murs=(),
    ouvertures=(),
    contour=contour,
)
ctx = ax.Contexte(
    structure=ax.Structure(murs_porteurs=()),
    orientation=ax.Orientation(deg=0.0),
    contour=contour,
    referentiel=ax.Referentiel(aires_min=(), largeur_min=1.0),
)
q = ax.legalize(plan, ctx)
print(q.certificat.geometrie.valide)
print(round(q.certificat.geometrie.deplacement_max, 2))
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

Formule : [épigraphe L1](../formules/epigraphe-l1.md),
[pipeline](../formules/pipeline.md).

**Voir aussi :** [Détecter une infaisabilité](03-detecter-une-infaisabilite.md),
[Le polytope](../concepts/polytope.md)
