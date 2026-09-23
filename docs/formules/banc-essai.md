# Banc d'essai

**Code :** `bench.run`, `bench.compare`, `bench.rapport`, `bench.stats`.

## Énoncé

Toute exécution produit un **manifeste** (version, graine, empreintes, `ModeleTrace`)
**avant** les résultats. Les **bruts** sont écrits **avant** toute agrégation.
Le rapport est **stratifié par orientation** (rose à 8 secteurs) — jamais une moyenne
globale seule : deux méthodes peuvent avoir la même moyenne et se croiser au sud.

### Bootstrap apparié

Pour deux méthodes évaluées sur les **mêmes** plans, \(d_i = a_i - b_i\). On
rééchantillonne \(B\) fois les \(d_i\) avec remise et on prend les percentiles
\(\alpha/2\) et \(1-\alpha/2\) des moyennes rééchantillonnées :

\[
\mathrm{IC}_{1-\alpha}
 = \bigl[\,q_{\alpha/2}(\bar d^{*}),\; q_{1-\alpha/2}(\bar d^{*})\,\bigr],
\qquad B = 9\,999 .
\]

L'appariement est ce qui fait tomber la variance inter-plans : c'est la
différence, pas les deux moyennes, qui est rééchantillonnée.

### TOST — équivalence

**Ne pas rejeter \(H_0\) ne démontre pas l'équivalence.** Pour conclure « les deux
méthodes ne diffèrent pas de plus de \(\delta\) », il faut deux tests unilatéraux
(Schuirmann) :

\[
t_{-}=\frac{\bar d+\delta}{s/\sqrt{n}},\qquad
t_{+}=\frac{\delta-\bar d}{s/\sqrt{n}},\qquad
p=\max\bigl(P(T_{n-1}>t_{-}),\,P(T_{n-1}>t_{+})\bigr).
\]

Équivalence déclarée si \(p<\alpha\). \(\delta\) est une **marge décidée avant de
voir les données**, jamais ajustée après coup.

### Holm–Bonferroni — comparaisons multiples

Une table stratifiée compare \(m\) cellules. Sans correction, la probabilité qu'au
moins un test ressorte par hasard vaut \(1-(1-\alpha)^m\) : déjà \(0{,}56\) pour
\(m=16\), \(\alpha=0{,}05\). Holm trie les p-valeurs croissantes et rejette
\(p_{(i)}\) tant que

\[
p_{(i)} \le \frac{\alpha}{m-i+1},
\]

en s'arrêtant au premier échec. Il contrôle le **FWER sans hypothèse
d'indépendance** — contrairement à Benjamini–Hochberg, qui ne contrôle que le FDR
et ne convient donc pas à une affirmation du type « la méthode A gagne sur cette
strate ».

### Puissance

Approximation par \(t\) non centrée, paramètre \(d\) de Cohen. Sert **avant**
l'expérience à dimensionner \(n\) ; l'invoquer *après* un résultat non
significatif (« puissance observée ») n'a pas de valeur inférentielle.

## Hypothèses

- `evaluate_by` est un oracle **externe** — jamais le substitut qu'on optimise,
  sans quoi on mesure l'erreur du modèle contre lui-même.
- Graine racine obligatoire ; sous-graines via `bench.graines.deriver`.
- Le bootstrap suppose les \(d_i\) échangeables entre plans ; il ne corrige **pas**
  une dépendance entre plans issus d'un même bâtiment. Sur un corpus réel
  (plusieurs étages d'un même immeuble), rééchantillonner par **grappe**.
- Géométrie exacte hors banc ; les scores de lumière sont des **estimations**,
  jamais une preuve.

## Code

| Symbole | Fonction |
|---|---|
| manifeste | `bench.manifeste.emettre` / `ModeleTrace` |
| orchestration | `bench.run` → `Resultat` |
| comparaison | `bench.compare` |
| rapport | `bench.rapport` |
| \(\mathrm{IC}\) bootstrap | `bench.stats.bootstrap_apparie` |
| équivalence | `bench.stats.tost` |
| multiplicité | `bench.stats.holm` |
| dimensionnement | `bench.stats.puissance` |

## Cas d'utilisation

| Faire | Ne pas faire |
|---|---|
| Fixer \(\delta\) et \(\alpha\) avant l'expérience | Choisir \(\delta\) après avoir vu \(\bar d\) |
| Stratifier par orientation puis appliquer Holm | Publier 16 p-valeurs non corrigées |
| Rééchantillonner par grappe sur corpus réel | Traiter des étages d'un même immeuble comme indépendants |
| Écrire les bruts avant d'agréger | Publier une moyenne sans ses données |

## Source

Bootstrap : Efron & Tibshirani (1993), ch. 13 — [bibliographie](sources.md) n° 20.
TOST : Schuirmann (1987), n° 21. Holm : Holm (1979), n° 22.
Puissance : Cohen (1988), ch. 2, n° 23. Protocole du dépôt : `MILESTONE-6.md` §5.
