# archlux

**Corriger un plan généré vers la validité géométrique en préservant sa performance
lumineuse. La géométrie est garantie ; la performance est bornée.**

```python
import archlux as ax

plan = ax.Plan.from_json("sortie_generateur.json")
q = ax.legalize(plan, ctx)
print(q.certificat.rapport())
```

Le plus rapide pour commencer : la [galerie d'exemples](galerie/01-corriger-un-plan.md).
Le plus important à comprendre : [les deux garanties](concepts/deux-garanties.md).
Pour refaire les calculs : le [formulaire](formules/index.md) (énoncé, dérivation,
source, cas d'utilisation).
