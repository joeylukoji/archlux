# Facteur de lumière du jour (split-flux)

**Code :** `light.simulateur.facteur_lumiere_jour`, `light.simulateur.SimulateurExact`.

## Énoncé

Pour une pièce rectangulaire de côtés \(w,h\) (mètres) et un azimut \(\theta\),
le facteur de lumière du jour moyen, en **fraction** (2 % \(\mapsto 0{,}02\)),
est

\[
\mathrm{DF}=\frac{1}{100}\,\frac{T\,A_w\,\vartheta}{A_{\mathrm{surf}}(1-R^2)},
\qquad
A_w=\rho\,H_v L,\quad
L=w\cos^2\theta+h\sin^2\theta,
\]

\[
A_{\mathrm{surf}}=2wh+2(w+h)H_p,\qquad
\vartheta=\vartheta_0 F_{\mathrm{secteur}}(\theta).
\]

\(\rho\) est le WWR (défaut \(0{,}30\)), \(H_v=1{,}15\,\mathrm{m}\) la hauteur
vitrée, \(H_p=2{,}70\,\mathrm{m}\) la hauteur sous plafond, \(T=0{,}70\),
\(R=0{,}50\), \(\vartheta_0=65^\circ\) (ciel dégagé).

`SimulateurExact` ajoute \(\sum_i 100\cdot\mathrm{DF}_i\cdot w_i h_i\) au
substitut analytique (CIBSE profondeur). Ce n'est **pas** un sDA LM-83.

## Hypothèses

- Ciel couvert CIE ; pas de masque urbain autre que \(F_{\mathrm{secteur}}\).
- Une baie par pièce, centrée sur la façade sud du rectangle (WWR), sans
  élargir le protocole vectoriel.
- Réflectances uniformes. Transmittance hors salissure (facteur M omis, \(=1\)).

## Dérivation

La formule de Littlefair / BRE pour le DF moyen d'un local latéral éclaire
\(A_w\) sous un angle de ciel \(\vartheta\) (degrés) et répartit le flux sur
toutes les surfaces internes. Le facteur \(1/100\) convertit le pourcent CIBSE
en fraction. \(L\) est la même façade sud que le [substitut analytique](substitut-analytique.md).
Les dérivées \(\partial\mathrm{DF}/\partial w\) et \(\partial\mathrm{DF}/\partial h\)
suivent le quotient \(u/v\).

## Code

`facteur_lumiere_jour`, `SimulateurExact.evaluer`, `.gradient`.

## Cas d'utilisation

| Faire | Ne pas faire |
|---|---|
| Oracle CI à la place d'un lancer de rayons | Publier le score comme un sDA mesuré |
| Vérifier : plus profond → DF ↓ ; sud > nord ; WWR ↑ → DF ↑ | Encoder une image ou un climat annuel |

## Source

Littlefair, P. J. (2011). *Site layout planning for daylight and sunlight*
(BRE 209, 2e éd.). IHS BRE Press. Formule du DF moyen, ciel couvert.
Angle de ciel et WWR : CIBSE, *Lighting Guide 10* (2014), voir
[bibliographie](sources.md) n° 15 et 16.
