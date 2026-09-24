# Calibrer un substitut

L'entraînement et le point de contrôle du gradient sont au
[jalon 4](entrainer-un-substitut.md). Ici : geler, scorer, borner.

Ne pas ouvrir le jeu de calibration avant le gel des poids. Lire la
calibration à l'entraînement rend la couverture conforme **fausse**, et aucun
test de perte ne le signale.

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

cal = CalibrateurConforme(indicateur="sDA")
cal.ajuster(predictions, verites, incertitudes, alpha=0.10)
borne = cal.borne(prediction, sigma, ">=", regime="exchangeable")
# borne.borne_inf, borne.couverture, borne.n_calibration
```

Le rang est \(\lceil(n+1)(1-\alpha)\rceil\), pas `np.quantile(s, 0.90)`. ASE
s'ajuste à part, avec `sens="<="`. `regime` est obligatoire : `"exchangeable"`
pour un plan tiré comme la calibration, `"selected"` pour un plan choisi par un
optimiseur, dont la couverture n'est alors pas garantie.

## 3. Objectif pessimiste

```python
import archlux as ax
from archlux.light.objectif import Daylight

objectif = Daylight(substitut, q_chapeau=cal.q)  # pessimiste=True par défaut
q = ax.legalize(plan, ctx, objective=objectif, calibration=cal.snapshot())
```

`q.certificat.performance` porte alors l'intervalle conforme du plan rendu, en
régime `"selected"` : c'est l'optimiseur qui a choisi ce plan, là où le
substitut surestime le plus (malédiction du vainqueur), donc la couverture
nominale n'est **pas** garantie. Le rapport le dit. Pour publier une couverture,
réévaluer le plan avec l'oracle.

## 4. Dérive et `NON EVALUABLE`

```python
from archlux.certify.borne import construire_borne
from archlux.uq.derive import controler_derive

derive = controler_derive(scores_production, cal.snapshot(), seed=17)
certificat_borne = construire_borne(
    prediction, cal.snapshot(), derive, incertitude=sigma, regime="exchangeable"
)
```

Si `derive.echangeable` est faux, `construire_borne` rend `None` : le rapport
écrit `NON EVALUABLE` plutôt qu'un intervalle.

Oracle gelé : `OracleSplitFlux` (forme fermée split-flux). Pas Radiance, pas une vérité terrain.

**Voir aussi :** [Prédiction conforme](../concepts/prediction-conforme.md),
[Statistique](../formules/statistique.md),
[Les deux garanties](../concepts/deux-garanties.md).
