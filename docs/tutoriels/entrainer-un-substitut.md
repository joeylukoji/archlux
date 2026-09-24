# Entraîner un substitut

Le substitut appris n'entre dans `legalize` **que** s'il respecte le protocole
vectoriel et si son gradient est validé contre l'oracle gelé (`SplitFluxOracle`,
split-flux BRE ; (Radiance) hors chemin critique).

Les blocs de cette page s'exécutent dans l'ordre, tels quels. Les tailles sont
réduites pour tourner en quelques secondes (80 plans, 8 neurones, 30 époques) : la
chaîne est complète, le modèle obtenu n'est qu'un jouet.

## 1. Un plan, et des dispositions pour apprendre

Le plan à corriger est celui des [premiers pas](premiers-pas.md) : trois pièces dans
une enveloppe de 12 m × 9 m, un débord de 5 cm et un vide de 3 cm. Le substitut ne
voit qu'un vecteur `[x, y, w, h]` par pièce ; `disposition` tire des variantes valides
des mêmes trois pièces.

```python
from pathlib import Path

import numpy as np

import archlux as ax

contour = ((0.0, 0.0), (12.0, 0.0), (12.0, 9.0), (0.0, 9.0))
plan = ax.Plan(
    pieces=(
        ax.Piece(id="sejour", type="sejour", x=0.0, y=0.0, w=6.05, h=9.0),
        ax.Piece(id="chambre", type="chambre", x=6.0, y=0.0, w=6.0, h=5.0),
        ax.Piece(id="sdb", type="salle_de_bain", x=6.0, y=5.03, w=6.0, h=3.97),
    ),
    murs=(),
    ouvertures=(),
    contour=contour,
)
ctx = ax.Contexte(
    structure=ax.Structure(murs_porteurs=()),
    orientation=ax.Orientation(deg=12.0),
    contour=contour,
    referentiel=ax.Referentiel(aires_min=(("salle_de_bain", 5.0),), largeur_min=1.0),
)


def disposition(rng: np.random.Generator) -> np.ndarray:
    """Séjour à gauche, chambre et salle de bain empilées à droite."""
    w, h = rng.uniform(4.0, 8.0), rng.uniform(3.0, 6.0)
    return np.array([0, 0, w, 9, w, 0, 12 - w, h, w, h, 12 - w, 9 - h], dtype=float)
```

## 2. Entraîner, sauver, geler

```python
from archlux.light.base import SubstitutDense
from archlux.light.simulateur import SplitFluxOracle
from archlux.uq.gestion import emettre_jeton

sim = SplitFluxOracle()
rng = np.random.default_rng(17)
# xs, ys, orientations : jeu d'entraînement uniquement — jamais la calibration
xs = tuple(disposition(rng) for _ in range(80))
orientations = tuple(ax.Orientation(deg=float(d)) for d in rng.uniform(0.0, 360.0, len(xs)))
ys = np.array([sim.evaluer(x, o) for x, o in zip(xs, orientations, strict=True)])

dense = SubstitutDense(largeur=8)
dense.ajuster(xs, ys, orientations, seed=17, epoques=30)
Path("poids").mkdir(exist_ok=True)
chemin = Path("poids/dense.npz")
empreinte = dense.sauver(chemin)
jeton = emettre_jeton(empreinte, "2026-09-09T10:00:00Z")  # après gel
```

`sauver` rend l'empreinte SHA-256 du fichier écrit ; le jeton la lie à l'instant du
gel. C'est lui qui ouvrira le jeu de calibration au
[tutoriel suivant](calibrer-un-substitut.md).

## 3. Valider le gradient, puis légaliser

```python
from archlux.light.appris import SubstitutAppris
from archlux.light.validation import valider_gradient

reseau = SubstitutAppris(chemin, empreinte, gele=True)
points = np.stack([disposition(rng) for _ in range(8)])
rapport = valider_gradient(reseau, points, ctx.orientation, seed=17, reference=sim)
assert rapport.accord_de_signe > 0.80

q = ax.legalize(plan, ctx, objective=reseau, budget=0.5, pavage=True)
assert q.certificat is not None and q.certificat.geometrie.valide
```

`valider_gradient` lève `SubstitutInvalide` sous le seuil d'accord de signe (0,80) :
l'`assert` ne fait que rendre le point de contrôle visible. `budget=0.5` borne le
déplacement de chaque mur à 50 cm autour de la proposition ; sans lui, Frank-Wolfe
suit le substitut aussi loin que le polytope le permet : dans cet exemple, il réduit
le séjour à 1 m, la largeur minimale.

`torch` n'est chargé que pour un fichier `.pt`. La CI entraîne le perceptron
numpy (`light.base`).

!!! warning "Le transformeur n'est pas implémenté"
    `SubstitutAppris._charger_torch` **lève systématiquement** : l'extra
    `archlux[ml]` installe `torch`, mais aucun modèle `.pt` n'est servi. La seule
    implémentation apprise du dépôt est le perceptron `numpy` ci-dessus.

!!! danger "D'où viennent `xs`, `ys`, `orientations` ?"
    Ici, comme dans le dépôt, `ys` vient de `SplitFluxOracle` — une **forme fermée**.
    Le perceptron apprend alors le résidu entre deux formules analytiques : la chaîne
    est exercée, la physique n'est pas mesurée. Pour des étiquettes réelles, lire
    [vérité terrain](../donnees/verite-terrain.md) : Swiss Dwellings (CC BY 4.0,
    367 colonnes de simulation par pièce) ou une campagne Radiance.

Le jeu de calibration n'est **pas** ouvert ici. Voir
[calibrer un substitut](calibrer-un-substitut.md) (jalon 5).

Formules : [jetons](../formules/jetons.md),
[validation du gradient](../formules/validation-gradient.md).
[Pourquoi pas une image](../concepts/pourquoi-pas-une-image.md).
