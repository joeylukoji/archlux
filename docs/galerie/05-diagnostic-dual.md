# Diagnostic dual

**Problème.** Le plan est valide et la borne de sDA est connue, mais on ne sait
pas **quelle contrainte** empêche d'ouvrir davantage la pièce au sud. Reculer
un porteur de 20 cm, ou élargir le dégagement ?

**Solution.**

```python
import numpy as np
from scipy import sparse

from archlux.certify.dual import translate_duals
from archlux.geom.polytope import Polytope

poly = Polytope(
    A=sparse.csr_matrix(np.eye(3)),
    b=np.ones(3),
    A_eq=sparse.csr_matrix((0, 3)),
    b_eq=np.zeros(0),
    bornes=((0.0, 1.0),) * 3,
    index={"a.x": 0, "a.y": 1, "a.w": 2},
    origines=(
        "mur porteur axe 3",
        "surface minimale cuisine",
        "largeur de passage",
    ),
)
for phrase, prix in translate_duals(np.array([-4.1, -1.7, 0.0]), poly):
    print(f"{prix:+.1f}  {phrase}")
```

Les prix duaux viennent du même LP que la légalisation (`lmo.resoudre(...,
duaux=True)`). `Polytope.origines` les rend lisibles ; un indice de ligne nu
ne l'est pas. Les prix nuls (contraintes inactives) sont filtrés.

**Résultat.**

```
-4.1  mur porteur axe 3: relaxing it by 10 cm would change the total displacement by -0.41 m (valid for small changes only, a few tens of cm)
-1.7  surface minimale cuisine: relaxing it by 10 cm would change the total displacement by -0.17 m (valid for small changes only, a few tens of cm)
```

Le prix brut (`-4.1`) est la variation de l'objectif par mètre de relâchement ; la phrase le
convertit pour un cran de 10 cm (`step_m`) et dans l'unité de l'objectif : des mètres de
déplacement total en mode classique, des points de l'indicateur **prédits** en mode
performance. Les libellés inconnus (comme ceux de cet exemple) sont repris tels quels ;
ceux du polytope réel sont reformulés (« load-bearing wall p1 at x = 6 m : … »), et les
lignes de l'épigraphe L1, qui sont des artefacts du solveur, ne sont jamais rapportées.

**Ce qu'il faut retenir.** Un prix dual est une dérivée *locale*. Reculer le
porteur de 20 cm est dans l'intervalle annoncé ; le reculer de 2 m ne l'est
pas. Ni un correcteur géométrique ni un simulateur seuls ne produisent ces
lignes : elles naissent de la fusion polytope × objectif lumineux.

**Voir aussi :** [Farkas et duaux](../formules/farkas.md),
[Lire un certificat](04-lire-un-certificat.md),
[Le polytope](../concepts/polytope.md).
