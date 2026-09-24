# Calibrer un substitut

L'entraînement et le point de contrôle du gradient sont au
[jalon 4](entrainer-un-substitut.md). Ici : geler, scorer, borner.

Ne pas ouvrir le jeu de calibration avant le gel des poids. Lire la
calibration à l'entraînement rend la couverture conforme **fausse**, et aucun
test de perte ne le signale.

Les blocs de cette page s'exécutent dans l'ordre, tels quels, en quelques secondes.
Les jeux de données y sont tirés au hasard et étiquetés par l'oracle gelé
`SplitFluxOracle` ; dans un vrai projet, ils sont lus dans les répertoires `train/`,
`calibration/` et `test/`.

## 0. Point de départ : un modèle entraîné

Le plan, le contexte et le modèle du [tutoriel précédent](entrainer-un-substitut.md),
en plus court :

```python
from pathlib import Path

import numpy as np

import archlux as ax
from archlux.light.base import SubstitutDense
from archlux.light.simulateur import SplitFluxOracle

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


oracle = SplitFluxOracle()
rng = np.random.default_rng(17)
xs = tuple(disposition(rng) for _ in range(80))
ys = np.array([oracle.evaluer(x, ctx.orientation) for x in xs])
modele = SubstitutDense(largeur=8)
modele.ajuster(xs, ys, (ctx.orientation,) * len(xs), seed=17, epoques=30)

for sous_dossier in ("train", "calibration", "test"):
    Path("splits/v1", sous_dossier).mkdir(parents=True, exist_ok=True)
```

## 1. Geler puis émettre le jeton

```python
from archlux.uq.gestion import GestionDonnees, geler_et_emettre

jeton = geler_et_emettre(modele, horodatage="2026-09-09T12:00:00Z")
calibration = GestionDonnees("splits/v1").pour_calibration(jeton, modele)
```

Si un poids bouge après le gel, `pour_calibration(..., modele)` lève
`ModeleModifie`.

## 2. Ajuster un calibrateur par indicateur

```python
from archlux.uq.conforme import CalibrateurConforme

plans_calibration = [disposition(rng) for _ in range(200)]  # jamais vus à l'entraînement
predictions = np.array([modele.evaluer(x, ctx.orientation) for x in plans_calibration])
verites = np.array([oracle.evaluer(x, ctx.orientation) for x in plans_calibration])
incertitudes = np.array([modele.incertitude(x, ctx.orientation) for x in plans_calibration])

cal = CalibrateurConforme(indicateur="sDA")
cal.ajuster(predictions, verites, incertitudes, alpha=0.10)

x_nouveau = disposition(rng)  # tiré comme la calibration : échangeable avec elle
prediction = modele.evaluer(x_nouveau, ctx.orientation)
sigma = modele.incertitude(x_nouveau, ctx.orientation)
borne = cal.borne(prediction, sigma, ">=", regime="exchangeable")
assert borne.borne_inf <= prediction <= borne.borne_sup
# borne.borne_inf, borne.couverture, borne.n_calibration
```

Le rang est \(\lceil(n+1)(1-\alpha)\rceil\), pas `np.quantile(s, 0.90)`. ASE
s'ajuste à part, avec `sens="<="`. `regime` est obligatoire : `"exchangeable"`
pour un plan tiré comme la calibration, `"selected"` pour un plan choisi par un
optimiseur, dont la couverture n'est alors pas garantie.

## 3. Objectif pessimiste

```python
from archlux.light.objectif import Daylight

objectif = Daylight(modele, q_chapeau=cal.q)  # pessimiste=True par défaut
q = ax.legalize(
    plan, ctx, objective=objectif, calibration=cal.snapshot(), budget=0.5, pavage=True
)
assert q.certificat is not None and q.certificat.performance is not None
assert q.certificat.performance.regime == "selected"
print(q.certificat.rapport())
```

`q.certificat.performance` porte alors l'intervalle conforme du plan rendu, en
régime `"selected"` : c'est l'optimiseur qui a choisi ce plan, là où le
substitut surestime le plus (malédiction du vainqueur), donc la couverture
nominale n'est **pas** garantie. Le rapport le dit. Pour publier une couverture,
réévaluer le plan avec l'oracle.

## 4. Dérive et `NON EVALUABLE`

Les scores de production sont ceux de plans rendus après calibration, une fois leur
vraie valeur connue : \(|y - \hat{y}| / \hat{\sigma}\), comme à l'ajustement.

```python
from archlux.certify.borne import construire_borne
from archlux.uq.derive import controler_derive

plans_production = [disposition(rng) for _ in range(50)]
scores_production = np.array(
    [
        abs(oracle.evaluer(x, ctx.orientation) - modele.evaluer(x, ctx.orientation))
        / modele.incertitude(x, ctx.orientation)
        for x in plans_production
    ]
)
derive = controler_derive(scores_production, cal.snapshot(), seed=17)
certificat_borne = construire_borne(
    prediction, cal.snapshot(), derive, incertitude=sigma, regime="exchangeable"
)
```

Ces plans sont tirés comme la calibration : le test ne détecte pas de dérive et
`certificat_borne` est un intervalle. Des erreurs trois fois plus grandes, elles, sont
détectées :

```python
derive_forte = controler_derive(3.0 * scores_production, cal.snapshot(), seed=17)
assert not derive_forte.echangeable
assert (
    construire_borne(
        prediction, cal.snapshot(), derive_forte, incertitude=sigma, regime="exchangeable"
    )
    is None
)
```

Si `derive.echangeable` est faux, `construire_borne` rend `None` : le rapport
écrit `NON EVALUABLE` plutôt qu'un intervalle. L'inverse ne vaut pas preuve :
`echangeable=True` signifie « dérive non détectée », et à faible effectif le test
n'a presque aucune puissance.

Oracle gelé : `SplitFluxOracle` (forme fermée split-flux). Pas Radiance, pas une vérité terrain.

**Voir aussi :** [Prédiction conforme](../concepts/prediction-conforme.md),
[Statistique](../formules/statistique.md),
[Les deux garanties](../concepts/deux-garanties.md).
