# Validation du gradient

**Code :** `light.validation.validate_gradient`.

## Énoncé

Pour un point \(x\) et une direction \(e_i\), la pente réelle du simulateur est

\[
\widehat{\partial_i f}(x)
=\frac{f(x+\delta e_i)-f(x-\delta e_i)}{2\delta}.
\]

L'**accord de signe** est la fraction des coordonnées telles que
\(\mathrm{sign}(\nabla \hat f_i)=\mathrm{sign}(\widehat{\partial_i f})\).

| Accord | Décision |
|---|---|
| \(> 0.90\) | continuer |
| \(0.80\)–\(0.90\) | continuer en surveillant |
| \(< 0.80\) | **arrêt** — ne pas ouvrir le jalon 5 |

## Hypothèses

- Le simulateur est déterministe (sinon la pente n'est pas définie).
- \(\delta=0.10\,\mathrm{m}\) pour le point de contrôle (pas un \(\varepsilon\)
  numérique).
- On évalue par le simulateur, jamais par le réseau.

## Source

`MILESTONE-4.md` §7. Différences finies centrées : Nocedal & Wright,
*Numerical Optimization*, Springer, §8.1.

## Au-delà du point de contrôle : fiabilité et refus à l'exécution

**Code :** `light.trust` (`gradient_agreement`, `gradient_reliability`,
`step_gain_audit`, `gradient_trust`, `GuardedSurrogate`,
`FiniteDifferenceSurrogate`) ; expérience `experiments/j4_reliability.py`.

La comparaison est répétée par secteur d'azimut, type de pièce, configuration
de fenêtres, amplitude \(\delta \in \{0{,}02 ; 0{,}10 ; 0{,}50\}\,\mathrm{m}\),
sur les plans retournés par Frank-Wolfe et pas à pas (gain prédit contre gain
réalisé). Mesures avec le réseau de j4 contre l'oracle split-flux figé
(`results/j4_reliability.csv`) :

| Plans | Accord de signe (tous) | Secteurs de 45° au-dessus de 0,80 |
|---|--:|--:|
| 80 plans tenus à l'écart | 0,827 | 4 / 8 |
| 16 sorties de Frank-Wolfe | 0,935 | 6 / 7 présents |
| 125 pas de Frank-Wolfe, signe du gain prédit contre réalisé | **0,552** | — |

`GuardedSurrogate` refuse un gradient dont l'accord est sous le seuil : il
renvoie un gradient nul (Frank-Wolfe s'arrête) ou lève `UntrustedGradient`.
`FiniteDifferenceSurrogate` fournit la référence sans gradient appris. La
référence est une **forme close** : fidélité à l'oracle, pas à la physique.
