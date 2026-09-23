# Jetons d'un plan

**Code :** `light.jetons.plan_vers_jetons`, `vecteur_vers_jetons`, `permuter_pieces`.

## Énoncé

Un plan n'est pas une image. Il devient un **ensemble** de jetons
\(\{\phi_1,\ldots,\phi_N\}\subset\mathbb{R}^{d}\), \(d=32\)
(`DIM_JETON`), de **deux familles**, dans cet ordre : les pièces, puis les baies.

\[
N = \underbrace{n_{\text{pièces}}}_{\text{toujours}}
  + \underbrace{n_{\text{baies rattachées}}}_{\text{0 si le plan n'a ni murs ni ouvertures}}
\]

Une baie n'est **jamais recopiée** sur chaque pièce : elle est son propre jeton.

## Disposition des 32 composantes

| Indices | Jeton de **pièce** | Jeton de **baie** |
|---:|---|---|
| `0:4` | \((x,y,w,h)\), mètres | 0 |
| `4:7` | \(\bigl(wh,\;2(w+h),\;\tfrac{4wh}{4(w+h)^2}\bigr)\) — aire, périmètre, compacité | 0 |
| `7:14` | one-hot du type sur 6 catégories + 1 case « inconnu » | 0 |
| `14:20` | \(\phi(\theta_{\text{bâtiment}})\), harmoniques 1–3 | idem |
| `20` | \(n_{\text{pièces}}\) | idem |
| `21` | \(\sum_j w_j h_j\) | idem |
| `22:24` | 0 | \(\phi(\theta_{\text{mur}})\), harmonique 1 |
| `24:27` | 0 | \((s,\ \text{largeur\_rel},\ \text{hauteur\_linteau})\) |
| `27` | 0 | **1,0 — drapeau « ceci est une baie »** |
| `28` | 0 | hauteur d'allège |
| `29:32` | 0 (réserve) | 0 (réserve) |

\(\phi(\theta)\) sont les [harmoniques circulaires](circulaire.md) — jamais le degré
brut. \(\theta_{\text{mur}}=\operatorname{atan2}(b_y-a_y,\;b_x-a_x)\) est l'azimut du
mur portant la baie, en degrés.

La compacité vaut \(1/4\) pour un carré et tend vers \(0\) pour un rectangle
dégénéré ; ce n'est pas l'indice de Polsby–Popper \(4\pi A/P^2\), mais la même
grandeur à un facteur \(\pi\) près.

## Le masque de remplissage

`plan_vers_jetons` rend le couple \((\text{jetons }[N,d],\ \text{masque }[N])\), où
`masque[i]` est **vrai si le jeton i est du remplissage** — convention PyTorch
`src_key_padding_mask`, pas l'inverse. Sur un plan seul le masque est entièrement
faux ; il ne devient utile qu'en lot de plans de tailles différentes.

## Hypothèses

- Coordonnées en mètres, contrat \((x,y,w,h)\) par pièce, **même ordre que
  `Polytope.index`** — c'est ce qui rend le gradient du substitut directement
  additionnable au vecteur de décision.
- Un déplacement de \(2\,\mathrm{cm}\) **doit** changer \(\phi\) : c'est le test
  anti-image. Sur un raster à 100 px/m, ce déplacement ne change aucun pixel, le
  gradient est nul presque partout, et l'optimiseur est aveugle
  (`ARCHITECTURE.md` §10, premier anti-pattern).
- Toute statistique d'ensemble (moyenne, somme) est **invariante par permutation**
  des pièces : `permuter_pieces` ne doit pas changer le score. C'est ce que teste
  `tests/unites/test_jetons.py`.
- Une ouverture dont le `mur_id` ne correspond à aucun mur du plan est
  **silencieusement ignorée** (`plan_vers_jetons`). C'est un choix : un corpus
  lacunaire ne doit pas faire tomber l'encodage. La contrepartie est qu'une erreur
  d'appariement mur/baie ne se signale pas ici — elle se signale à la
  dévectorisation.

## Cas d'utilisation

| Faire | Ne pas faire |
|---|---|
| Encoder depuis `Plan` quand murs et baies existent | Croire que `vecteur_vers_jetons` encode les baies : il ne voit que \((x,y,w,h)\) et force le type `"sejour"` |
| Vérifier l'invariance par permutation | Trier les jetons par position (ce serait un ordre implicite) |
| Ajouter une composante en fin de vecteur | Réindexer `0:22` — les poids `npz` gelés deviendraient faux sans que rien ne le signale |

!!! warning "Le corpus livré n'exerce pas les jetons de baie"
    `data.synthese.generer_corpus` produit des plans avec `murs=()` et
    `ouvertures=()`. Les colonnes `22:29` y sont donc **identiquement nulles**, et
    `SimulateurExact` utilise son WWR par défaut (0,30) quelle que soit la
    fenestration. Voir [vérité terrain](../donnees/verite-terrain.md).

## Source

Décision d'architecture : `ARCHITECTURE.md` §10 ; `MILESTONE-4.md` §4 (ordre des
familles). Harmoniques : Mardia & Jupp (2000), voir [circulaire](circulaire.md).
[Pourquoi pas une image](../concepts/pourquoi-pas-une-image.md).
