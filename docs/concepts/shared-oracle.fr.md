# L'oracle partagé

L'oracle linéaire de Frank-Wolfe **est** le solveur de légalisation. Ce n'est
pas une métaphore : c'est le même appel, avec un autre vecteur de coûts.

Le bloc ci-dessous s'exécute tel quel. Il reprend le plan de la
[galerie 01](../gallery/01-repair-a-plan.md) (deux pièces qui se recouvrent d'un
mètre), construit le polytope des plans valides pour l'ordre lu sur la proposition,
puis appelle deux fois `lmo.solver.solve` : une fois pour la légalisation classique, une
fois pour le pas d'une itération Frank-Wolfe.

```python
import archlux as ax
from archlux.api import gradient_distance
from archlux.geom.graph import deduce_order
from archlux.geom.polytope import build_polytope, extend_l1_slack, vectorize
from archlux.light import AnalyticSurrogate
from archlux.lmo import solver as lmo

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
    orientation=ax.Orientation(deg=12.0),
    outline=outline,
    regulation=ax.Regulation(min_areas=(), min_width=1.0),
)
poly = build_polytope(deduce_order(plan, structure=ctx.structure), ctx)
Q_proposed = vectorize(plan, poly.index)
n = len(poly.index)

# classic legalization — milestone 2: minimize the L1 distance to the proposal
poly_l1 = extend_l1_slack(poly, Q_proposed)
sol = lmo.solve(poly_l1, c=gradient_distance(Q_proposed))
Q = sol.x[:n]  # the first n coordinates; the following ones are the L1 slacks
assert sol.status == "optimal" and poly.contains(Q)

# one Frank-Wolfe iteration — milestone 3: same call, costs = -gradient of the surrogate
surrogate = AnalyticSurrogate()
sol = lmo.solve(poly, c=-surrogate.gradient(Q, ctx.orientation), start=Q)
S = sol.x  # a vertex of the polytope
gamma = 0.5  # step of the iteration
Q_next = Q + gamma * (S - Q)
assert poly.contains(S) and poly.contains(Q_next)
```

`lmo` ignore d'où vient \(c\). Cette ignorance est le cœur de
`ARCHITECTURE.md` : un seul simplexe, deux usages. Ajouter un second solveur
« pour la lumière » casserait la garantie que tout itéré est un plan valide :
`Q_next` est une moyenne de deux points du polytope, donc un point du polytope,
qui est convexe.

Ce bloc montre le mécanisme, pas tout `legalize`. Avant la boucle, `legalize` fige
les contacts du plan légalisé et ajoute l'approximation intérieure des surfaces
minimales et le budget de déplacement ; la boucle (`archlux.solve.frank_wolfe`) prend
le pas \(2/(k+2)\), le divise par deux tant que l'objectif baisse, ajoute
des pas « away », et s'arrête quand le gap de Frank-Wolfe passe sous la tolérance.

Le démarrage à chaud (`start=x` **à chaque** itération) ne change pas la
solution, seulement le temps : seule la présence de `start` compte, elle permet de
réutiliser le modèle déjà construit pour ce polytope. L'omettre dans une boucle de
50 tours coûte un facteur 3 à 5.

La géométrie reste **exacte** (chaque itéré \(\in P\)). Le score du substitut
reste **sans garantie** jusqu'à la prédiction conforme (jalon 5). Ne pas
écrire « plan optimal pour la lumière » : écrire « plan valide qui maximise
le substitut, gap d'optimisation \(g\) ».

Voir [Frank-Wolfe](../formulas/frank-wolfe.md),
[comparer deux méthodes](../gallery/02-compare-two-methods.md).
