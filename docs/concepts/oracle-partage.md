# L'oracle partagé

L'oracle linéaire de Frank-Wolfe **est** le solveur de légalisation. Ce n'est
pas une métaphore : c'est le même appel, avec un autre vecteur de coûts.

Le bloc ci-dessous s'exécute tel quel. Il reprend le plan de la
[galerie 01](../galerie/01-corriger-un-plan.md) (deux pièces qui se recouvrent d'un
mètre), construit le polytope des plans valides pour l'ordre lu sur la proposition,
puis appelle deux fois `lmo.resoudre` : une fois pour la légalisation classique, une
fois pour le pas d'une itération Frank-Wolfe.

```python
import archlux as ax
from archlux.api import gradient_distance
from archlux.geom.graphe import deduire_ordre
from archlux.geom.polytope import construire_polytope, etendre_ecarts_l1, vectoriser
from archlux.light import SubstitutAnalytique
from archlux.lmo import solveur as lmo

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
    orientation=ax.Orientation(deg=12.0),
    contour=contour,
    referentiel=ax.Referentiel(aires_min=(), largeur_min=1.0),
)
poly = construire_polytope(deduire_ordre(plan, structure=ctx.structure), ctx)
Q_propose = vectoriser(plan, poly.index)
n = len(poly.index)

# légalisation classique — jalon 2 : minimiser la distance L1 à la proposition
poly_l1 = etendre_ecarts_l1(poly, Q_propose)
sol = lmo.resoudre(poly_l1, c=gradient_distance(Q_propose))
Q = sol.x[:n]  # les n premières coordonnées ; les suivantes sont les écarts L1
assert sol.statut == "optimal" and poly.contient(Q)

# une itération Frank-Wolfe — jalon 3 : même appel, coûts = -gradient du substitut
substitut = SubstitutAnalytique()
sol = lmo.resoudre(poly, c=-substitut.gradient(Q, ctx.orientation), depart=Q)
S = sol.x  # un sommet du polytope
gamma = 0.5  # pas de l'itération
Q_suivant = Q + gamma * (S - Q)
assert poly.contient(S) and poly.contient(Q_suivant)
```

`lmo` ignore d'où vient \(c\). Cette ignorance est le cœur de
`ARCHITECTURE.md` : un seul simplexe, deux usages. Ajouter un second solveur
« pour la lumière » casserait la garantie que tout itéré est un plan valide :
`Q_suivant` est une moyenne de deux points du polytope, donc un point du polytope,
qui est convexe.

Ce bloc montre le mécanisme, pas tout `legalize`. Avant la boucle, `legalize` fige
les contacts du plan légalisé et ajoute l'approximation intérieure des surfaces
minimales et le budget de déplacement ; la boucle (`archlux.solve.frank_wolfe`) prend
le pas \(2/(k+2)\), le divise par deux tant que l'objectif baisse, ajoute
des pas « away », et s'arrête quand le gap de Frank-Wolfe passe sous la tolérance.

Le démarrage à chaud (`depart=x` **à chaque** itération) ne change pas la
solution, seulement le temps : seule la présence de `depart` compte, elle permet de
réutiliser le modèle déjà construit pour ce polytope. L'omettre dans une boucle de
50 tours coûte un facteur 3 à 5.

La géométrie reste **exacte** (chaque itéré \(\in P\)). Le score du substitut
reste **sans garantie** jusqu'à la prédiction conforme (jalon 5). Ne pas
écrire « plan optimal pour la lumière » : écrire « plan valide qui maximise
le substitut, gap d'optimisation \(g\) ».

Voir [Frank-Wolfe](../formules/frank-wolfe.md),
[comparer deux méthodes](../galerie/02-comparer-deux-methodes.md).
