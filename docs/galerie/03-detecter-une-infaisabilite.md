# Détecter une infaisabilité

**Problème.** Deux pièces exigent chacune 8 m de largeur minimale dans une enveloppe
de 12 m. Aucun plan valide n'existe : le dire vaut mieux que de renvoyer un plan faux.

**Solution.**

```python
import archlux as ax

outline = ((0.0, 0.0), (12.0, 0.0), (12.0, 9.0), (0.0, 9.0))
plan = ax.Plan(
    rooms=(
        ax.Room(id="a", type="living_room", x=0.0, y=0.0, w=8.0, h=8.0),
        ax.Room(id="b", type="living_room", x=8.0, y=0.0, w=8.0, h=8.0),
    ),
    walls=(),
    openings=(),
    outline=outline,
)
ctx = ax.Context(
    structure=ax.Structure(load_bearing_walls=()),
    orientation=ax.Orientation(deg=0.0),
    outline=outline,
    regulation=ax.Regulation(min_areas=(), min_width=8.0),
)
try:
    ax.legalize(plan, ctx)
except ax.Infeasible as err:
    print(sorted(err.origins))
```

**Résultat.**

```
['contour droit b', 'separation horizontale a|b']
```

Le certificat de Farkas désigne le sous-système en conflit : les deux séparations
horizontales et les bords droits. Ce n'est pas un message d'erreur, c'est une **preuve**
d'inexistence (lemme de Farkas).

**Ce qu'il faut retenir.** `Infeasible` n'est pas un échec du solveur. C'est le
programme qui ne tient pas. Les `origins` sont des libellés métier, jamais des
indices de lignes.

Formule : [Farkas et duaux](../formules/farkas.md).

**Voir aussi :** [Corriger un plan](01-corriger-un-plan.md),
[Le polytope](../concepts/polytope.md)
