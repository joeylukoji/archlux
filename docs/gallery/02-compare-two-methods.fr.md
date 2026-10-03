# Comparer deux méthodes honnêtement

**Problème.** Le légaliseur classique ignore le nord. Deux appartements identiques,
l'un au nord, l'autre au sud, reçoivent la même correction L1. On veut une
correction qui *préfère* la lumière, sans encore entraîner de réseau.

**Solution.** Même fonction, un paramètre : `objective=AnalyticSurrogate()`.
Le substitut est un modèle fermé (profondeur utile \(2.5\times\) linteau,
harmoniques d'orientation). Frank-Wolfe réutilise l'oracle LP du jalon 2.

```python
import archlux as ax
from archlux.light.analytic import AnalyticSurrogate

outline = ((0.0, 0.0), (12.0, 0.0), (12.0, 9.0), (0.0, 9.0))
plan = ax.Plan(
    rooms=(
        ax.Room(id="living_room", type="living_room", x=0.0, y=0.0, w=12.0, h=5.0),
        ax.Room(id="bedroom", type="bedroom", x=0.0, y=4.0, w=12.0, h=5.0),
    ),
    walls=(),
    openings=(),
    outline=outline,
)
ctx_n = ax.Context(
    structure=ax.Structure(()),
    orientation=ax.Orientation(0.0),
    outline=outline,
    regulation=ax.Regulation((), 1.0),
)
ctx_s = ax.Context(
    structure=ax.Structure(()),
    orientation=ax.Orientation(180.0),
    outline=outline,
    regulation=ax.Regulation((), 1.0),
)
q_l1 = ax.legalize(plan, ctx_n)
q_n = ax.legalize(plan, ctx_n, objective=AnalyticSurrogate())
q_s = ax.legalize(plan, ctx_s, objective=AnalyticSurrogate())
print(q_l1.certificate.geometry.valid)
print(q_n.rooms == q_s.rooms)
assert q_l1.certificate.geometry.valid
assert q_n.rooms != q_s.rooms  # north and south move the shared wall differently
```

**Résultat.**

```
True
False
```

La preuve géométrique reste **exacte** dans les trois cas. Les deux plans
performantiels diffèrent : le nord n'est plus une coordonnée muette. Les deux pièces
sont empilées selon l'axe nord–sud : déplacer le mur qui les sépare échange de la
lumière entre les deux façades, et l'optimum dépend de la façade orientée au sud.
Côte à côte (un mur orienté nord–sud), chaque pièce garderait la même part de chaque
façade, et le nord et le sud donneraient le même plan. Le score du
substitut n'est **pas** un sDA mesuré ; aucune couverture conforme n'est
affirmée (jalon 5).

**Ce qu'il faut retenir.** `objective=None` reproduit le jalon 2. Un substitut
ne change pas le domaine : il change le vecteur \(c\) de l'oracle. Comparer L1
et performantiel sur le *même* ordre, jamais en mélangeant les garanties.

Formules : [substitut analytique](../formulas/analytic-surrogate.md),
[Frank-Wolfe](../formulas/frank-wolfe.md),
[oracle partagé](../concepts/shared-oracle.md).

**Voir aussi :** [Corriger un plan](01-repair-a-plan.md),
[Légalisation performantielle](../tutorials/performance-legalization.md)
