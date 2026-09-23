# Comparer deux méthodes honnêtement

**Problème.** Le légaliseur classique ignore le nord. Deux appartements identiques,
l'un au nord, l'autre au sud, reçoivent la même correction L1. On veut une
correction qui *préfère* la lumière, sans encore entraîner de réseau.

**Solution.** Même fonction, un paramètre : `objective=SubstitutAnalytique()`.
Le substitut est un modèle fermé (profondeur utile \(2{,}5\times\) linteau,
harmoniques d'orientation). Frank-Wolfe réutilise l'oracle LP du jalon 2.

```python
import archlux as ax
from archlux.light.analytique import SubstitutAnalytique

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
ctx_n = ax.Contexte(
    ax.Structure(()), ax.Orientation(0.0), contour, ax.Referentiel((), 1.0),
)
ctx_s = ax.Contexte(
    ax.Structure(()), ax.Orientation(180.0), contour, ax.Referentiel((), 1.0),
)
q_l1 = ax.legalize(plan, ctx_n)
q_n = ax.legalize(plan, ctx_n, objective=SubstitutAnalytique())
q_s = ax.legalize(plan, ctx_s, objective=SubstitutAnalytique())
print(q_l1.certificat.geometrie.valide)
print(q_n.pieces == q_s.pieces)
```

**Résultat.**

```
True
False
```

La preuve géométrique reste **exacte** dans les trois cas. Les deux plans
performantiels diffèrent : le nord n'est plus une coordonnée muette. Le score du
substitut n'est **pas** un sDA mesuré ; aucune couverture conforme n'est
affirmée (jalon 5).

**Ce qu'il faut retenir.** `objective=None` reproduit le jalon 2. Un substitut
ne change pas le domaine : il change le vecteur \(c\) de l'oracle. Comparer L1
et performantiel sur le *même* ordre, jamais en mélangeant les garanties.

Formules : [substitut analytique](../formules/substitut-analytique.md),
[Frank-Wolfe](../formules/frank-wolfe.md),
[oracle partagé](../concepts/oracle-partage.md).

**Voir aussi :** [Corriger un plan](01-corriger-un-plan.md),
[Légalisation performantielle](../tutoriels/legalisation-performantielle.md)
