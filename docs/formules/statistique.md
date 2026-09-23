# Statistique — prédiction conforme

**Code :** `uq.conforme.quantile_conforme`, `uq.conforme.CalibrateurConforme`.

Cette page est le formulaire du jalon 5. Les duaux, Farkas, \(\delta_\infty\)
restent des **nombres exacts** : ils n'appartiennent pas ici.

## Énoncé

Scores de non-conformité normalisés, un par plan de calibration :

\[
s_i = \frac{\lvert y_i - \hat y_i\rvert}{\hat\sigma_i},\qquad i=1,\ldots,n.
\]

Quantile conforme à échantillon fini, niveau \(\alpha\in\,(0,1)\) :

\[
k = \bigl\lceil (n+1)(1-\alpha)\bigr\rceil,
\qquad
\hat q = s_{(k)}\ \text{si}\ k\le n,\ \text{sinon indéfini}.
\]

Intervalle annoncé au point \((\hat y, \hat\sigma)\) :

\[
\bigl[\hat y - \hat q\,\hat\sigma,\ \hat y + \hat q\,\hat\sigma\bigr].
\]

Sous échangeabilité du point avec le jeu de calibration,

\[
\mathbb{P}\bigl(y \in [\hat y - \hat q\,\hat\sigma,\ \hat y + \hat q\,\hat\sigma]\bigr)
 \ge 1-\alpha.
\]

## Hypothèses

- Les \(n+1\) scores (calibration + point à borner) sont échangeables.
- \(\hat\sigma_i > 0\).
- Le modèle est **gelé** avant toute lecture du jeu de calibration.
- \(k\le n\) : sinon le noyau lève plutôt que de publier une borne infinie.

Les plans produits par un maximiseur de \(\hat y\) violent l'échangeabilité.
La couverture *sous sélection* se mesure (`uq.derive`) ; elle n'est pas
garantie par le théorème.

## Dérivation

La prédiction conforme par rang (Vovk, Gammerman & Shafer, 2005) prend le
\((1-\alpha)\)-quantile *sur \(n+1\) points*, dont le point de test de rang
inconnu. Remplacer \(n+1\) par \(n\) (quantile empirique ordinaire) donne des
intervalles trop étroits : la couverture réelle tombe sous \(1-\alpha\), et
rien ne le signale. D'où \(k=\lceil(n+1)(1-\alpha)\rceil\) et l'interdiction
de `np.quantile(s, 0.90)` seul.

## Code

| Symbole | Fonction |
|---|---|
| \(s_{(k)}\) | `quantile_conforme` |
| \(\hat q\) | `CalibrateurConforme.ajuster` / `.q` |
| intervalle | `CalibrateurConforme.borne` → `BornePerformance` |
| CRPS | `uq.fiabilite.crps` |
| \(J=\hat\mu-\hat q\,\hat\sigma\) | `light.objectif.Daylight` |

## Cas d'utilisation

| Faire | Ne pas faire |
|---|---|
| Calibrer **après** le gel, sur un jeu jamais vu à l'entraînement | Lire `calibration/` pendant `ajuster` des poids |
| Afficher `n_calibration` à côté de la borne | Publier \(\hat\sigma\) du réseau comme si c'était \(1-\alpha\) |
| Un calibrateur par indicateur, ASE en `<=` | Réutiliser le \(q̂\) du sDA pour l'ASE |
| `NON EVALUABLE` si le test d'échangeabilité rejette | Élargir silencieusement l'intervalle |

## Source

Vovk, Gammerman & Shafer (2005), *Algorithmic Learning in a Random World*.
[Bibliographie](sources.md) n° 12.

Oracle de vérité du jalon : [split-flux](split-flux.md), pas un sDA LM-83.
