# Détecter une infaisabilité

**Problème.** Deux pièces exigent chacune 8 m de largeur minimale dans une enveloppe
de 12 m. Aucun plan valide n'existe : le dire vaut mieux que de renvoyer un plan faux.

**Solution.**

```python
import archlux as ax

contour = ((0.0, 0.0), (12.0, 0.0), (12.0, 9.0), (0.0, 9.0))
plan = ax.Plan(
    pieces=(
        ax.Piece(id="a", type="sejour", x=0.0, y=0.0, w=8.0, h=8.0),
        ax.Piece(id="b", type="sejour", x=8.0, y=0.0, w=8.0, h=8.0),
    ),
    murs=(),
    ouvertures=(),
    contour=contour,
)
ctx = ax.Contexte(
    structure=ax.Structure(murs_porteurs=()),
    orientation=ax.Orientation(deg=0.0),
    contour=contour,
    referentiel=ax.Referentiel(aires_min=(), largeur_min=8.0),
)
try:
    ax.legalize(plan, ctx)
except ax.Infaisable as err:
    print(sorted(err.origines))
```

**Résultat.**

```
['contour droit b', 'separation horizontale a|b']
```

Le certificat de Farkas désigne le sous-système en conflit : les deux séparations
horizontales et les bords droits. Ce n'est pas un message d'erreur, c'est une **preuve**
d'inexistence (lemme de Farkas).

**Ce qu'il faut retenir.** `Infaisable` n'est pas un échec du solveur. C'est le
programme qui ne tient pas. Les `origines` sont des libellés métier, jamais des
indices de lignes.

Formule : [Farkas et duaux](../formules/farkas.md).

**Voir aussi :** [Corriger un plan](01-corriger-un-plan.md),
[Le polytope](../concepts/polytope.md)
