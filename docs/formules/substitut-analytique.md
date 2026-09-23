# Substitut analytique

**Code :** `light.analytique.SubstitutAnalytique`.

## Énoncé

Pour chaque pièce, le vecteur \((x,y,w,h)\) et l'azimut \(\theta\) (via
[`encoder`](circulaire.md), jamais le degré brut) donnent un score

\[
f_i=L\cdot\min(P,D)\cdot\exp(\kappa\,s),\qquad
L=w\cos^2\theta+h\sin^2\theta,\quad
P=w\sin^2\theta+h\cos^2\theta,
\]

où \(D=2{,}5\times 2{,}15\times F_{\mathrm{secteur}}\) est la profondeur utile
modulée par huit secteurs, et \(s\) la coordonnée vers le sud géographique :

\[
s=-x\sin\theta-y\cos\theta.
\]

Le substitut rend \(\sum_i f_i\) (sDA, UDI, vue) ou son opposé (ASE).

## Hypothèses

- Le vecteur suit le contrat \((x,y,w,h)\) par pièce, même ordre que le polytope.
- La règle \(2{,}5\times\) linteau est **empirique** (CIBSE LG10) ; incertitude
  typique \(\sim 30\,\%\). Ce n'est **pas** une garantie de performance.
- \(\kappa=0{,}15\,\mathrm{m}^{-1}\) casse l'invariance par translation : sans
  lui, un facteur d'orientation *global* ne changerait pas l'argmax.

## Dérivation

La façade au sud d'un rectangle aligné vaut \(w\) si \(+y\) est le nord
(\(\theta=0\)) et \(h\) si le bâtiment a tourné de \(90^\circ\). D'où
\(L=w\cos^2\theta+h\sin^2\theta\). La profondeur associée est l'autre
dimension. \(\min(P,D)\) est la règle de profondeur utile : au-delà de \(D\),
approfondir n'ajoute plus de lumière. Le sous-gradient en \(P=D\) vaut \(\{0,1\}\).

Le gradient se calcule par règle du produit ; un test le compare aux
différences finies centrées.

## Code

`SubstitutAnalytique.evaluer`, `.gradient`, `.incertitude`.
Constantes : `FACTEUR_PROFONDEUR`, `HAUTEUR_LINTEAU`, `KAPPA_SUD`,
`FACTEURS_SECTEUR` — `ClassVar`, jamais de magie dans le corps.

## Cas d'utilisation

| Faire | Ne pas faire |
|---|---|
| Valider le flux Frank-Wolfe avant tout apprentissage | Publier le score comme un sDA mesuré |
| Vérifier que nord et sud *déplacent* le plan | Encoder \(\theta\) en réel dans \([0,360]\) |

## Source

Règle de profondeur utile : CIBSE, *Lighting Guide 10 : Daylighting — a guide
for designers*, Londres. Harmoniques : [circulaire](circulaire.md).
Le protocole vectoriel : `ARCHITECTURE.md` §10.
