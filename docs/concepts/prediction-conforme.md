# La prédiction conforme

Quatre étapes, un piège, une hypothèse. Module : `archlux.uq.conforme`.
Source : Vovk, Gammerman & Shafer (2005), [bibliographie](../formules/sources.md) n° 12.

## Les quatre étapes

1. **Geler** le substitut, émettre le jeton (`geler_et_emettre`). Le jeu de
   calibration n'a jamais été lu à l'entraînement.
2. **Scorer** chaque plan de calibration : \(s_i = \lvert y_i - \hat y_i\rvert / \hat\sigma_i\).
3. **Prendre le rang** \(k = \lceil (n+1)(1-\alpha)\rceil\) dans les scores triés.
   C'est \(q̂\). Pas le quantile empirique à \(1-\alpha\).
4. **Annoncer** l'intervalle \(\hat y \pm q̂\,\hat\sigma\) et la couverture
   visée \(1-\alpha\), avec \(n\) affiché.

Exemple chiffré. \(n = 100\), \(\alpha = 0{,}10\). Le rang conforme est
\(\lceil 101 \times 0{,}90\rceil = 91\). Le quantile empirique à 0,90 tombe plus
bas (entre les rangs 90 et 91, interpolation). L'intervalle conforme est
**strictement plus large**. Avec 1 000 points l'écart est minime ; avec 100, la
garantie tombe si on omet la correction.

Si \(k > n\) (jeu trop petit pour \(\alpha\)), `quantile_conforme` lève
`InvariantViole`. Pas de borne infinie silencieuse.

## L'hypothèse d'échangeabilité

La couverture \(\ge 1-\alpha\) vaut si le plan à borner est **échangeable** avec
les \(n\) plans de calibration. Un plan *sélectionné* par Frank-Wolfe pour
maximiser \(\hat y\) ne l'est plus tout à fait : l'optimiseur cherche les
erreurs du réseau. Le projet mesure cet écart (`uq.derive.mesurer_derive`) et,
si un test d'échangeabilité le rejette, le certificat porte `NON EVALUABLE`
plutôt qu'un intervalle.

## Sens des indicateurs

- sDA, UDI, vue : on publie la **borne inférieure** (`>=`).
- ASE : on publie la **borne supérieure** (`<=`).

Un calibrateur par indicateur : les erreurs n'ont pas la même échelle.

## Objectif pessimiste

Frank-Wolfe maximise \(J = \hat\mu - q̂\,\hat\sigma\), pas \(\hat\mu\). Là où
\(\hat\sigma\) s'ouvre, \(J\) chute, l'optimiseur revient. Classe :
`light.objectif.Daylight`. Le flottant \(q̂\) est injecté : `light` n'importe
pas `uq`.

Formule : [statistique](../formules/statistique.md).
Tutoriel : [calibrer un substitut](../tutoriels/calibrer-un-substitut.md).
