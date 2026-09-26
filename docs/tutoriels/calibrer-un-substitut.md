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

outline = ((0.0, 0.0), (12.0, 0.0), (12.0, 9.0), (0.0, 9.0))
plan = ax.Plan(
    rooms=(
        ax.Room(id="living_room", type="living_room", x=0.0, y=0.0, w=6.05, h=9.0),
        ax.Room(id="bedroom", type="bedroom", x=6.0, y=0.0, w=6.0, h=5.0),
        ax.Room(id="bathroom", type="bathroom", x=6.0, y=5.03, w=6.0, h=3.97),
    ),
    walls=(),
    openings=(),
    outline=outline,
)
ctx = ax.Context(
    structure=ax.Structure(load_bearing_walls=()),
    orientation=ax.Orientation(deg=12.0),
    outline=outline,
    regulation=ax.Regulation(min_areas=(("bathroom", 5.0),), min_width=1.0),
)


def disposition(rng: np.random.Generator) -> np.ndarray:
    """Séjour à gauche, chambre et salle de bain empilées à droite."""
    w, h = rng.uniform(4.0, 8.0), rng.uniform(3.0, 6.0)
    return np.array([0, 0, w, 9, w, 0, 12 - w, h, w, h, 12 - w, 9 - h], dtype=float)


oracle = SplitFluxOracle()
rng = np.random.default_rng(17)
xs = tuple(disposition(rng) for _ in range(80))
ys = np.array([oracle.evaluate(x, ctx.orientation) for x in xs])
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
`ModelModified`.

## 2. Ajuster un calibrateur par indicateur

```python
from archlux.uq.conforme import CalibrateurConforme

plans_calibration = [disposition(rng) for _ in range(200)]  # jamais vus à l'entraînement
predictions = np.array([modele.evaluate(x, ctx.orientation) for x in plans_calibration])
verites = np.array([oracle.evaluate(x, ctx.orientation) for x in plans_calibration])
incertitudes = np.array([modele.uncertainty(x, ctx.orientation) for x in plans_calibration])

cal = CalibrateurConforme(indicator="sDA")
cal.ajuster(predictions, verites, incertitudes, alpha=0.10)

x_nouveau = disposition(rng)  # tiré comme la calibration : échangeable avec elle
prediction = modele.evaluate(x_nouveau, ctx.orientation)
sigma = modele.uncertainty(x_nouveau, ctx.orientation)
borne = cal.borne(prediction, sigma, ">=", regime="exchangeable")
assert borne.lower <= prediction <= borne.upper
# borne.lower, borne.coverage, borne.n_calibration
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
assert q.certificate is not None and q.certificate.performance is not None
assert q.certificate.performance.regime == "selected"
print(q.certificate.report())
```

`q.certificat.performance` porte alors l'intervalle conforme du plan rendu, en
régime `"selected"` : c'est l'optimiseur qui a choisi ce plan, là où le
substitut surestime le plus (malédiction du vainqueur), donc la couverture
nominale n'est **pas** garantie. Le rapport le dit. Pour publier une couverture,
réévaluer le plan avec l'oracle.

## 4. Dérive et `NOT EVALUABLE`

Les scores de production sont ceux de plans rendus après calibration, une fois leur
vraie valeur connue : \(|y - \hat{y}| / \hat{\sigma}\), comme à l'ajustement.

```python
from archlux.certify.borne import build_bound
from archlux.uq.derive import controler_derive

plans_production = [disposition(rng) for _ in range(50)]
scores_production = np.array(
    [
        abs(oracle.evaluate(x, ctx.orientation) - modele.evaluate(x, ctx.orientation))
        / modele.uncertainty(x, ctx.orientation)
        for x in plans_production
    ]
)
derive = controler_derive(scores_production, cal.snapshot(), seed=17)
certificat_borne = build_bound(
    prediction, cal.snapshot(), derive, uncertainty=sigma, regime="exchangeable"
)
```

Ces plans sont tirés comme la calibration : le test ne détecte pas de dérive et
`certificat_borne` est un intervalle. Des erreurs trois fois plus grandes, elles, sont
détectées :

```python
derive_forte = controler_derive(3.0 * scores_production, cal.snapshot(), seed=17)
assert not derive_forte.echangeable
assert (
    build_bound(
        prediction, cal.snapshot(), derive_forte, uncertainty=sigma, regime="exchangeable"
    )
    is None
)
```

Si `derive.echangeable` est faux, `build_bound` rend `None` : le rapport
écrit `NOT EVALUABLE` plutôt qu'un intervalle. L'inverse ne vaut pas preuve :
`echangeable=True` signifie « dérive non détectée », et à faible effectif le test
n'a presque aucune puissance.

Oracle gelé : `SplitFluxOracle` (forme fermée split-flux). Pas Radiance, pas une vérité terrain.

**Voir aussi :** [Prédiction conforme](../concepts/prediction-conforme.md),
[Statistique](../formules/statistique.md),
[Les deux garanties](../concepts/deux-garanties.md).
