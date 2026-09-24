# Entraîner un substitut

Le substitut appris n'entre dans `legalize` **que** s'il respecte le protocole
vectoriel et si son gradient est validé contre l'oracle gelé (`OracleSplitFlux`,
split-flux BRE ; (Radiance) hors chemin critique).

```python
from pathlib import Path
from archlux.light.base import SubstitutDense
from archlux.light.appris import SubstitutAppris
from archlux.light.simulateur import OracleSplitFlux
from archlux.light.validation import valider_gradient
from archlux.uq.gestion import emettre_jeton

sim = OracleSplitFlux()
# xs, ys, orientations : jeu d'entraînement uniquement — jamais la calibration
dense = SubstitutDense()
dense.ajuster(xs, ys, orientations, seed=17)
chemin = Path("poids/dense.npz")
empreinte = dense.sauver(chemin)
jeton = emettre_jeton(empreinte, "2026-09-09T10:00:00Z")  # après gel

reseau = SubstitutAppris(chemin, empreinte, gele=True)
rapport = valider_gradient(reseau, points, orientation, seed=17, reference=sim)
assert rapport.accord_de_signe > 0.80
q = ax.legalize(plan, ctx, objective=reseau)
```

`torch` n'est chargé que pour un fichier `.pt`. La CI entraîne le perceptron
numpy (`light.base`).

!!! warning "Le transformeur n'est pas implémenté"
    `SubstitutAppris._charger_torch` **lève systématiquement** : l'extra
    `archlux[ml]` installe `torch`, mais aucun modèle `.pt` n'est servi. La seule
    implémentation apprise du dépôt est le perceptron `numpy` ci-dessus.

!!! danger "D'où viennent `xs`, `ys`, `orientations` ?"
    Dans le dépôt, `ys` vient de `OracleSplitFlux` — une **forme fermée**. Le
    perceptron apprend alors le résidu entre deux formules analytiques : la chaîne
    est exercée, la physique n'est pas mesurée. Pour des étiquettes réelles, lire
    [vérité terrain](../donnees/verite-terrain.md) : Swiss Dwellings (CC BY 4.0,
    367 colonnes de simulation par pièce) ou une campagne Radiance.

Le jeu de calibration n'est **pas** ouvert ici. Voir
[calibrer un substitut](calibrer-un-substitut.md) (jalon 5).

Formules : [jetons](../formules/jetons.md),
[validation du gradient](../formules/validation-gradient.md).
[Pourquoi pas une image](../concepts/pourquoi-pas-une-image.md).
