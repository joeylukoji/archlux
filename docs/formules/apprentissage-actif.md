# Apprentissage actif

**Code :** `active.selection`, `active.densite`, `active.boucle.Loop`.

## Énoncé

\[
\mathrm{priorite}(Q) \;=\; \hat\sigma(Q)\;\times\;\hat f(Q).
\]

C'est un **produit**, pas une somme : un facteur nul écarte le candidat. Sans la
densité, on simule des plans aberrants que l'optimiseur ne visitera jamais ; sans
l'incertitude, on resimule ce que le modèle maîtrise déjà. C'est la pondération
« incertitude × représentativité » de Settles (§6.3.2).

### La densité

\(\hat f\) est un estimateur à noyau gaussien isotrope sur les plans **produits par
l'optimiseur** — c'est-à-dire sur la région où le substitut va réellement être
interrogé, pas sur le corpus d'entraînement :

\[
\hat f(c) \;=\; \frac{1}{m}\sum_{j=1}^{m}
 \exp\!\left(-\frac{\lVert c-r_j\rVert_2^{2}}{2h^{2}}\right),
\qquad
h \;=\; \bar s_{r}\; m^{-1/(d+4)} ,
\]

où \(\bar s_r\) est l'écart-type moyen par coordonnée de la référence et \(d\) la
dimension du vecteur de plan. L'exposant \(-1/(d+4)\) est la **règle de Scott**.

Le facteur de normalisation \((2\pi h^2)^{-d/2}\) est **volontairement omis** : la
priorité n'est utilisée que pour *classer* des candidats, et une constante
multiplicative commune ne change aucun classement. \(\hat f\) n'est donc pas une
densité de probabilité et ne doit pas être publiée comme telle.

!!! warning "Fléau de la dimension"
    Un noyau isotrope en dimension \(d = 4n_{\text{pièces}}\) se dégrade vite :
    à \(d = 60\), \(m^{-1/64}\) est presque \(1\) quel que soit \(m\), et toutes
    les densités s'écrasent vers la même valeur. La sélection tend alors vers
    l'incertitude seule. Sur des plans à plus d'une dizaine de pièces, réduire la
    dimension (ACP, ou distance sur les descripteurs de `light.base`) **avant**
    d'estimer la densité.

### La boucle

Après chaque lot de \(k\) candidats : simuler avec l'oracle gelé → réentraîner si
`ajuster` existe → **recalibrer le conforme**. La recalibration n'est pas
facultative : le modèle a changé, donc \(\hat q\) d'avant ne borne plus rien.

!!! danger "L'échangeabilité est cassée par construction"
    Les points ajoutés sont **choisis** par le critère de priorité. Ils ne sont
    donc pas échangeables avec un tirage i.i.d., et un jeu de calibration alimenté
    par la boucle active **invalide le théorème conforme**. Le jeu de calibration
    doit rester tiré indépendamment. Ce que la boucle améliore légitimement, c'est
    la **largeur** d'intervalle (via \(\hat\sigma\)), mesurée à budget de
    simulations égal contre `Aleatoire`.

## Hypothèses

- Candidats et référence vivent dans le même espace vectoriel, même échelle.
- L'oracle est un `Substitut` déterministe (`SplitFluxOracle`), pas un lancer de
  rayons — voir [vérité terrain](../donnees/verite-terrain.md).
- Budget de simulations fini ; comparaison **à budget égal** avec `Aleatoire`,
  même graine racine.

## Code

| Symbole | Fonction |
|---|---|
| produit \(\hat\sigma\times\hat f\) | `active.selection.UncertaintyTimesDensity` |
| référence aléatoire | `active.selection.Aleatoire` |
| \(\hat f\) | `active.densite.densite_noyau` |
| \(h\) (Scott) | `densite_noyau(..., bande=None)` |
| boucle | `active.boucle.Loop.run` → `RapportActif` |

## Cas d'utilisation

| Faire | Ne pas faire |
|---|---|
| Recalibrer après chaque cycle | Réutiliser un jeton de calibration d'un modèle antérieur |
| Comparer actif vs aléatoire à budget égal | Sommer incertitude et densité |
| Mesurer la largeur d'intervalle finale | Optimiser seulement le MAE du réseau |
| Garder la calibration hors de la boucle | Verser les points acquis dans le jeu de calibration |

## Source

Pondération incertitude × densité : Settles (2009), §6.3.2 —
[bibliographie](sources.md) n° 26. Largeur de bande : Scott (1992), §6.3, n° 24 ;
noyau gaussien isotrope : Silverman (1986), §4.3, n° 25.
Protocole du dépôt : `MILESTONE-6.md` §3.
