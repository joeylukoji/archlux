# archlux

> **Corriger un plan généré vers la validité géométrique en préservant sa performance lumineuse.
> La géométrie est garantie ; la performance est bornée.**

[![CI](https://github.com/ORG/archlux/actions/workflows/ci.yml/badge.svg)](https://github.com/ORG/archlux/actions)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](pyproject.toml)
[![DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.XXXXXXX-blue)](https://doi.org/10.5281/zenodo.XXXXXXX)

---

## Sommaire

- [Le problème](#le-problème)
- [Ce que fait archlux](#ce-que-fait-archlux)
- [Installation](#installation)
- [Démarrage rapide](#démarrage-rapide)
- [Comment ça marche](#comment-ça-marche)
- [Les deux garanties](#les-deux-garanties)
- [Le certificat](#le-certificat)
- [Architecture](#architecture)
- [Données](#données)
- [Indicateurs d'éclairement](#indicateurs-déclairement)
- [Performance](#performance)
- [Contexte scientifique](#contexte-scientifique)
- [Feuille de route](#feuille-de-route)
- [Reproductibilité](#reproductibilité)
- [Limites](#limites)
- [Documentation](#documentation)
- [Citer ce travail](#citer-ce-travail)

---

## Le problème

### Un plan généré est presque juste

Les modèles génératifs — diffusion, transformeurs, modèles de langage — produisent
aujourd'hui des plans d'appartements plausibles. Mais **presque** justes : deux cloisons
se chevauchent de trois centimètres, un jour de deux centimètres subsiste entre deux
pièces, une salle de bains passe à 4,6 m² au lieu des 5 m² réglementaires.

Ce n'est pas un défaut de réglage. C'est **structurel** : ces modèles traitent la validité
géométrique comme une pénalité à minimiser dans une fonction de perte. Or une pénalité
finie ne peut jamais annuler la probabilité de produire une sortie invalide. Aucun
hyperparamètre ne corrigera cela.

### On corrige aujourd'hui sans savoir vers quoi

La correction porte un nom, hérité de la conception de circuits intégrés où elle est
étudiée depuis les années 1980 : la **légalisation**. Sa formulation canonique est
« parmi tous les plans valides, prendre le plus proche de la proposition ».

Cette formulation contient une décision que quarante ans de littérature n'ont jamais
interrogée. **Pourquoi le plus proche ?**

En conception de circuits, la réponse est bonne : le placement approximatif minimisait
la longueur des interconnexions, et s'en écarter la dégrade. La proximité y est un
substitut légitime de l'objectif réel.

En architecture, cette justification n'existe pas. Le plan approximatif vient d'un modèle
qui a appris à imiter un corpus ; **la proximité à cette proposition n'est le substitut
de rien**.

Et le problème n'est pas théorique. Dans le voisinage d'une proposition invalide, il
n'existe pas *un* plan valide : il en existe un continuum de dimension élevée. Une cloison
mal placée peut être rectifiée de neuf centimètres vers l'est ou de onze vers l'ouest.
La légalisation classique choisit l'est parce que neuf est plus petit que onze. Or si la
façade regarde le sud-est, ces deux corrections n'ont pas le même effet sur la lumière
reçue par la pièce, et l'écart se compte en points d'autonomie lumineuse.

> **La légalisation tranche sur deux centimètres une question qui se joue en dizaines
> de pourcents d'éclairement, et elle la tranche par un critère qui ne veut rien dire.**

### Le problème symétrique

De l'autre côté, la physique du bâtiment a la difficulté inverse.

Évaluer l'éclairement naturel annuel d'un logement demande une simulation par lancer de
rayons : minutes à heures par plan. Explorer un espace de conception en exigerait des
millions. Le domaine s'est donc doté de **modèles de substitution** — un réseau apprend
à prédire les indicateurs à partir de la géométrie, avec un gain de plusieurs ordres de
grandeur.

Ces substituts servent à évaluer, à classer, parfois à guider un apprentissage par
renforcement. Ils ne servent **jamais** à optimiser sous contrainte, pour deux raisons :

1. **Un optimiseur exact trouve les erreurs de son estimateur.** Plus l'optimiseur est
   efficace, plus il l'est à exploiter l'approximation plutôt que la réalité.
2. **Un objectif environnemental sans contrainte géométrique produit des absurdités** :
   pièces filiformes plaquées contre les façades, cloisons qui ne se rejoignent pas,
   surfaces sous les minima.

### Chacun est la réponse manquante de l'autre

> **La légalisation cherche un objectif : le substitut le lui fournit.
> Le substitut cherche un domaine de validité : la légalisation le lui fournit.**

Et le terme de proximité géométrique — celui dont nous venons de dire qu'il est
arbitraire — ne disparaît pas : **il change de statut**. Un substitut appris est fiable
au voisinage de la distribution où il a été calibré et se dégrade en s'en éloignant.
Borner le déplacement des murs, c'est borner l'extrapolation. Ce qui était une convention
de sobriété devient une **condition de validité statistique**.

---

## Ce que fait archlux

`archlux` prend un plan quelconque et rend un plan **valide**, corrigé de sorte à
préserver au mieux la lumière naturelle, accompagné d'un **certificat** qui distingue
ce qui est prouvé de ce qui est prédit.

| Fonction | Entrée | Sortie |
|---|---|---|
| **Légalisation classique** | Plan invalide | Plan valide le plus proche + preuve |
| **Légalisation performantielle** | Plan invalide + orientation | Plan valide le mieux éclairé + preuve + borne |
| **Détection d'infaisabilité** | Programme + enveloppe | Verdict + certificat nommant les contraintes en conflit |
| **Diagnostic dual** | — | Quelle contrainte coûte le plus de lumière, et combien |
| **Vérification seule** | Plan dessiné à la main | Preuve géométrique, sans aucune IA |

**Ce que `archlux` ne fait pas :** générer des plans. Les plans viennent de modèles
publics existants, ou d'un architecte. `archlux` corrige, vérifie et certifie.

---

## Installation

```bash
pip install archlux                 # noyau : géométrie, solveur, certification
pip install "archlux[ml]"           # + substitut appris (PyTorch)
pip install "archlux[sim]"          # extra vide (Radiance)
pip install "archlux[bim]"          # + export IFC
pip install "archlux[stats]"        # + outils statistiques du banc d'essai
```

**Le noyau n'installe pas PyTorch.** Un bureau d'études qui veut seulement corriger et
vérifier des plans n'a aucune raison d'installer deux gigaoctets de bibliothèques
d'apprentissage. Cette séparation n'est pas cosmétique : elle reflète le principe
d'architecture selon lequel le noyau ne dépend d'aucun modèle appris, et elle est
vérifiée par un test automatique.

Dépendances du noyau : `numpy`, `scipy`, `shapely`, `networkx`, `ortools`.

---

## Démarrage rapide

### Corriger un plan

```python
import archlux as ax

plan = ax.Plan.from_json("sortie_generateur.json")
ctx  = ax.Contexte(
    structure   = ax.Structure.from_dxf("porteurs_niveau3.dxf"),
    orientation = ax.Orientation(deg=12),          # nord à 12° est
    referentiel = ax.referentiel("fr/logement-collectif"),
)

q = ax.legalize(plan, ctx)
print(q.certificat.rapport())
```

### Corriger en préservant la lumière

Un seul argument change :

```python
q = ax.legalize(
    plan, ctx,
    objective = ax.light.Daylight(metric="sDA", alpha=0.10),
    budget    = 0.25,        # déplacement maximal autorisé, en mètres
)
```

> C'est l'expression, dans l'interface, du fait que les deux méthodes partagent tout
> sauf leur vecteur objectif. Un utilisateur qui connaît la première obtient la seconde
> en ajoutant un paramètre.

### Détecter l'infaisable

```python
verdict = ax.feasibility.is_feasible(programme, structure, ctx)
if not verdict:
    print(verdict.certificat.expliquer())
```

```
Infaisable : surface utile 58,0 m2 < surface programme 65,0 m2.
Contraintes en cause : [sejour >= 20, services >= 40, total <= 58].
Deficit : 7,0 m2.
```

**Tous les modèles génératifs publiés produisent une sortie quoi qu'il arrive**, y compris
quand la demande est mathématiquement impossible — auquel cas le plan produit est
nécessairement faux quelque part, sans que rien ne le signale. `archlux` refuse, et dit
pourquoi.

### Comparer deux méthodes honnêtement

```python
res = ax.bench.compare(
    plans        = ax.data.generator_outputs("housediffusion", n=500),
    context      = ctx.sweep_orientation(n=8),        # 8 orientations
    methods      = ["proximity", "performance"],
    evaluate_by  = ax.light.ExactSimulator(),         # obligatoire, sans défaut
    seeds        = range(5),
)
res.report(stratify_by="orientation", test="paired_bootstrap")
```

`evaluate_by` n'a **pas de valeur par défaut** : on ne peut pas comparer sans dire
explicitement avec quoi on évalue. Cela rend difficile d'évaluer par erreur avec le
prédicteur qui a servi à optimiser — l'erreur circulaire la plus tentante du domaine.

---

## Comment ça marche

### Le principe : une division du travail

> Le générateur décide **l'ordre** des pièces.
> Le solveur décide **les dimensions**.
> Le réseau de neurones fournit **une direction**.

Aucun des trois n'empiète sur le domaine des autres. Le réseau fait ce en quoi il est
bon — deviner une disposition plausible ; le solveur fait ce en quoi il est bon — rendre
les chiffres exacts et conformes.

### Étape 1 — Le polytope

Dire que la pièce A est à gauche de la pièce B, c'est dire qu'elle se termine avant que
B ne commence :

```
x_A + w_A ≤ x_B
```

Une phrase de français est devenue une inégalité. En écrivant cette inégalité pour chaque
paire de pièces, on obtient un système linéaire.

**Le point crucial :** pour deux pièces quelconques, l'une doit être à gauche, à droite,
au-dessus ou en dessous de l'autre. Si aucune des quatre n'est vraie, elles se chevauchent
forcément. **Une fois une séparation posée par paire, le chevauchement est mathématiquement
impossible.** Ce n'est pas une pénalité qui le décourage : c'est une interdiction.

Les contraintes de surface (`w × h ≥ 9`) ne sont pas linéaires, mais l'ensemble qu'elles
définissent est **convexe**. On les remplace par des tangentes ajoutées à la demande —
autour de `w₀ = h₀ = 3`, la contrainte devient `3w + 3h ≥ 18`, qui est linéaire et
n'accepte que des plans dont la surface suffit réellement.

### Étape 2 — L'oracle partagé

Le problème à résoudre maximise une fonction régulière sur un ensemble convexe compact.
C'est exactement le cadre de l'algorithme de **Frank-Wolfe**, qui procède ainsi :

1. Regarder dans quelle direction la lumière augmente le plus vite — le **gradient**,
   fourni par le réseau.
2. Demander : *« quel plan valide va le plus loin dans cette direction ? »*
3. Avancer un peu vers ce plan, et recommencer.

**La question de l'étape 2 est exactement celle que résout le correcteur géométrique.**
Même système de contraintes, même solveur, même code. Seul le vecteur objectif change :

```python
# légalisation classique
sol = lmo.resoudre(poly, c=gradient_distance(Q_propose))

# une itération de Frank-Wolfe
sol = lmo.resoudre(poly, c=-substitut.gradient(Q, orientation), depart=Q)
```

**Les deux moitiés du système ne sont pas couplées : elles sont confondues.** C'est ce
qui rend le projet réalisable — le composant le plus coûteux à écrire est partagé — et
c'est ce qui rend les comparaisons expérimentales irréprochables, puisque la référence
et la méthode partagent le solveur, la tolérance et le point de départ.

### Trois propriétés gratuites

**Tous les points intermédiaires sont valides.** On part d'un plan valide, et chaque
étape mélange deux plans valides. **On peut interrompre l'algorithme à tout moment et
récupérer un plan correct** — déterminant en usage interactif.

**On sait de combien on rate l'optimum.** L'écart de dualité de Frank-Wolfe majore la
distance à la meilleure solution possible. On peut donc s'arrêter en disant « je suis à
au plus 0,4 point du meilleur plan ».

**Le compromis complet se trace pour presque rien.** En faisant varier le poids entre
autonomie lumineuse et éblouissement, avec redémarrage à chaud, on obtient la courbe
entière des solutions non dominées.

### Étape 3 — Le substitut

Le substitut reçoit la description du plan et rend un indicateur, son gradient et son
incertitude, derrière le protocole `Substitut` (trois méthodes, pas une de plus).

> **État réel du dépôt.** Trois implémentations existent : `SubstitutAnalytique`
> (formes fermées), `SimulateurExact` (split-flux BRE, oracle gelé de la CI) et
> `SubstitutDense` (perceptron trois couches, poids `numpy`, entraîné sur le **résidu**
> à l'analytique). **Le transformeur sur jetons n'est pas implémenté** :
> `SubstitutAppris` refuse les poids `.pt`. L'entrée par jetons décrite ci-dessous est
> le contrat que respectent les trois — c'est une décision d'architecture déjà tenue,
> pas une promesse. Voir
> [`docs/donnees/verite-terrain.md`](docs/donnees/verite-terrain.md).

**Point de conception décisif, et contre-intuitif : l'entrée est un ensemble de jetons,
pas une image.** Sur une image, déplacer un mur de deux centimètres ne change souvent
aucun pixel : le gradient est nul presque partout et l'optimiseur est aveugle. Sur une
liste de nombres, le changement est continu et le gradient existe.

Autre point : **les fenêtres sont repérées relativement à leur mur** — « à 30 % de la
longueur du mur nord », jamais par des coordonnées absolues. Quand le solveur déplace un
mur, ses fenêtres suivent sans aucune synchronisation, et l'état incohérent n'est pas
représentable.

### Étape 4 — La marge d'erreur

Une prédiction sans marge n'est pas utilisable dans un certificat. `archlux` emploie la
**prédiction conforme** :

1. Réserver un millier de plans, **jamais vus à l'entraînement**, dont on connaît la vraie
   valeur par simulation. *(Dimensionnement cible. Le découpage livré, `splits/v1`, en
   compte 18 : il exerce la mécanique, il ne fonde pas un chiffre publiable.)*
2. Mesurer les erreurs du réseau sur ces plans.
3. Prendre le 90ᵉ centile de ces erreurs.
4. Annoncer `prédiction − marge` au lieu de `prédiction`.

La promesse est alors tenue au moins neuf fois sur dix, **sans aucune hypothèse sur la
loi des données ni sur la justesse du modèle**, et pour un échantillon fini.

En version normalisée, la marge **s'élargit là où le modèle est en terrain inconnu**.
Comme l'optimiseur, en cherchant des plans très lumineux, s'éloigne de ce qu'il connaît,
la marge s'ouvre, l'objectif chute, et l'optimiseur revient de lui-même. **Le garde-fou
n'est pas ajouté : il découle de la façon dont l'incertitude est estimée.**

### Étape 5 — Le diagnostic dual

Quand un programme linéaire est résolu, il rend aussi, pour chaque contrainte, un **prix
implicite** : de combien l'objectif s'améliorerait si l'on relâchait cette contrainte
d'une unité.

```
CE QUI VOUS COUTE DE LA LUMIERE

  1. Mur porteur, axe 3             -4,1 pts de sDA   (reculer de 20 cm : +0,8)
  2. Surface minimale cuisine 9 m2  -1,7 pt
  3. Largeur de passage degagement  -0,6 pt
  4. Contour, facade nord            0,0 pt  (non contraignant)
```

**Ni un correcteur géométrique ni un simulateur ne peut produire ces lignes.** Le premier
ne connaît pas la lumière, le second ne connaît pas les contraintes. Elles tombent de leur
fusion, et le solveur les calcule de toute façon.

---

## Les deux garanties

C'est le point central du projet, et il ne doit jamais être confondu.

| | Géométrique | Performance |
|---|---|---|
| **Nature** | Exacte, démontrable | Probabiliste |
| **Ce qu'on affirme** | « ce plan ne comporte aucun chevauchement » | « ce plan atteindra au moins 51,4 % » |
| **Statut logique** | Une preuve | Une prédiction avec sa marge |
| **Vérification** | Inspection finie, `O(n²)` | Couverture ≥ 1−α sur un jeu de calibration |
| **Hypothèses** | Aucune | Échangeabilité avec le jeu de calibration |
| **Peut être fausse ?** | Non | Oui, dans au plus α des cas |

Présenter la seconde avec l'assurance de la première serait une faute. `archlux` la rend
difficile à commettre : les deux sont **des types distincts** (`PreuveGeometrique` n'a
aucun champ de probabilité, `BornePerformance` en a trois), et le certificat les sépare
typographiquement.

Voir [`docs/concepts/deux-garanties.md`](docs/concepts/deux-garanties.md).

---

## Le certificat

Toute sortie de `archlux` porte son certificat. **Il n'existe aucune interface qui rende
une géométrie sans lui.**

> **Le bloc ci-dessous est une maquette de format**, pas un résultat mesuré. Les
> chiffres (`56,2`, `1 284 simulations`) illustrent la mise en page du rapport. Les
> résultats réellement produits par ce dépôt sont dans [`resultats/`](resultats/), et
> l'état des étiquettes d'éclairement est décrit dans
> [`docs/donnees/verite-terrain.md`](docs/donnees/verite-terrain.md).

```
CERTIFICAT — plan T3-065-a          archlux 0.10.0    graine 17

GEOMETRIE                                       [EXACT]
  Chevauchement            aucun         verifie
  Jour / recouvrement      aucun         verifie
  Surfaces minimales       6/6           verifie
  Structure conservee      oui           verifie
  Deplacement maximal      0,18 m        <= 0,25 m

PERFORMANCE                        [PREDICTION — couverture 90 %]
  sDA(300/50%)   >= 51,4 %   (predit 56,2, marge 4,8)
  ASE(1000,250h) <= 8,9 %    (predit 6,1, marge 2,8)
  Qualite de vue >= 0,62     (predit 0,71, marge 0,09)
  Orientation    N 12 deg E  calibration : 1 284 simulations exactes

NON EVALUABLE
  Confort d'ete, systemes techniques, materiaux — hors perimetre
```

| Champ | Rôle |
|---|---|
| `[EXACT]` / `[PREDICTION]` | La distinction de nature, rendue visible |
| `calibration : N simulations` | Une borne conforme calculée sur 50 points ne vaut pas une borne calculée sur 1 284 — le nombre voyage avec la borne |
| `NON EVALUABLE` | Les articles dont la vérification exige une information absente du plan. **Un oracle qui ne déclare jamais « non évaluable » ment sur sa couverture** |
| `archlux <version>` + graine | Traçabilité : un certificat doit rester reproductible |

---

## Architecture

```
ENTRÉES : plan proposé · structure porteuse · orientation · programme
   │
   ▼
[1] geom      modélisation → polytope (A, b)        PUR, DÉTERMINISTE
   │
   ├────────────────────┬──────────────────────────┐
   ▼                    ▼                          ▼
[2a] lmo   solveur LP, objectif        [2b] light   substitut
     paramétrable            PUR             valeur / gradient / σ    APPRIS
   │                    │                          │
   └────────────────────┴────────► [3] solve  Frank-Wolfe        PUR
                                        │
                                        ▼
                                  [4] certify   preuve + borne + duaux   PUR
                                        │
                                        ▼
                   SORTIE : plan valide + certificat + diagnostic
```

**Trois couches sur quatre sont pures et déterministes.** Une seule est apprise, isolée
derrière un protocole à trois méthodes. `lmo` reçoit un vecteur de coefficients et ne
sait pas s'il vient d'une distance géométrique ou d'un gradient d'éclairement — cette
ignorance délibérée est ce qui permet à un seul solveur de servir aux deux modes.

| Module | Responsabilité | Appris |
|---|---|:--:|
| `types` | `Plan`, `Piece`, `Ouverture`, `Contexte`, `Certificat` | non |
| `geom` | ordre relatif → graphe de contraintes → polytope | non |
| `lmo` | résoudre `min <c,x>`. **Ignore l'origine de `c`** | non |
| `solve` | Frank-Wolfe, pas d'écartement, démarrage à chaud | non |
| `light` | protocole `Substitut` : valeur, gradient, incertitude | **oui** |
| `orient` | encodage et statistiques circulaires | non |
| `uq` | calibration conforme, contrôle de dérive | non |
| `certify` | vérification exacte, borne, traduction des duaux | non |
| `bench` | protocole, graines, manifestes | non |

Le protocole `Substitut` admet **trois implémentations interchangeables** : analytique
(formules fermées, sans apprentissage), apprise (perceptron / transformeur), et
simulateur exact (`SimulateurExact` ; (Radiance) hors chemin critique). Le noyau ne
fait pas la différence — ce qui permet de tester toute la chaîne avant d'avoir
entraîné quoi que ce soit.

Détail complet : [`ARCHITECTURE.md`](docs/specification/ARCHITECTURE.md).

---

## Données

`archlux` ne redistribue aucun corpus. Le dépôt embarque un générateur synthétique
déterministe (90 pavages 2×2) qui fait tourner la CI, et documente l'ingestion des jeux
publics.

| Corpus | Ce qu'il apporte | Licence | Accès |
|---|---|---|---|
| **[Swiss Dwellings](docs/donnees/swiss-dwellings.md)** | **le couple géométrie ↔ lumière** : 45 000 appartements, **367 colonnes de simulation par pièce** (soleil, vue, bruit) | **CC BY 4.0** | [doi:10.5281/zenodo.7788422](https://doi.org/10.5281/zenodo.7788422) |
| **[MSD](docs/donnees/msd.md)** *(Modified Swiss Dwellings)* | murs porteurs et poteaux annotés, graphes de zonage, **orientation cardinale conservée**, géométrie non-Manhattan | **CC BY-SA 4.0** | [arXiv:2407.10121](https://arxiv.org/abs/2407.10121), Kaggle |
| **[CubiCasa5K](docs/donnees/cubicasa.md)** | **portes et fenêtres annotées** en SVG vectoriel, > 80 catégories | recherche / non commercial | [github.com/CubiCasa/CubiCasa5k](https://github.com/CubiCasa/CubiCasa5k) |
| **RPLAN** | 80 000 plans, comparabilité avec la littérature vision | sur demande | [page projet](http://staff.ustc.edu.cn/~fuxm/projects/DeepLayout/index.html) |

**Le projet démarre sans partenariat, sans collecte et sans autorisation.** C'est rare
dans ce domaine et cela pèse dans l'évaluation de faisabilité.

> **Avant d'annoncer un chiffre de couverture**, lire
> [`docs/donnees/verite-terrain.md`](docs/donnees/verite-terrain.md) : les étiquettes
> livrées viennent d'une forme fermée, pas d'une simulation. Le chargeur WKT →
> `Plan` des corpus réels reste à écrire.

### Le découpage en trois — et pourquoi trois

L'habitude est de découper en deux : entraînement et test. **Ici il en faut trois.**

| Jeu | Part | Rôle |
|---|---|---|
| Entraînement | 60 % | Ajuster les poids |
| **Calibration** | 20 % | Calculer le quantile conforme — **jamais vu à l'entraînement** |
| Test | 20 % | Mesure finale, ouvert une seule fois |

**Si le jeu de calibration a servi de près ou de loin à l'entraînement, la garantie de
couverture est fausse** — trop optimiste — et **rien ne le signale** : ni les tests, ni la
validation, ni la relecture. C'est la seule erreur silencieuse du système capable
d'invalider une affirmation publiée. `archlux` la rend difficile par construction : trois
répertoires distincts, et l'accès au jeu de calibration exige un jeton émis après le gel
du modèle.

---

## Indicateurs d'éclairement

| Indicateur | Définition | Sens |
|---|---|---|
| **sDA₍₃₀₀/₅₀%₎** | Part du sol dépassant 300 lux pendant au moins 50 % des heures d'occupation | Autonomie lumineuse. **Plus haut, mieux c'est** |
| **ASE₍₁₀₀₀,₂₅₀ₕ₎** | Part du sol recevant plus de 1 000 lux de soleil direct pendant plus de 250 h/an | Éblouissement et surchauffe. **Plus bas, mieux c'est** |
| **UDI** | Part du temps où l'éclairement reste dans une plage utile | Ni trop sombre, ni trop lumineux |
| **Qualité de vue** | Indicateur d'ouverture visuelle depuis les zones occupées | Bien-être |

**sDA et ASE vont en sens contraire, et c'est essentiel.** Agrandir une baie augmente
l'autonomie *et* l'éblouissement. Il n'existe pas de plan qui maximise les deux ; il
existe une courbe de compromis, que `archlux` sait tracer entièrement.

L'orientation est traitée comme une **variable circulaire** : encodage en
(cos θ, sin θ) et harmoniques, statistiques circulaires pour l'analyse. Traiter 359° et
1° comme éloignés produit des conclusions fausses, et la règle de profondeur limite des
pièces dépend elle-même fortement de l'exposition.

---

## Performance

Budgets contractuels, vérifiés en intégration continue. Un dépassement casse la
construction.

| Opération | Budget | Référence |
|---|---|---|
| Construction du polytope | < 5 ms | 15 pièces |
| Un appel LP à froid | < 10 ms | 15 pièces |
| Un appel LP à chaud | < 3 ms | 15 pièces |
| **Légalisation classique complète** | **< 20 ms** | 15 pièces |
| **Légalisation performantielle** | **< 500 ms** | 15 pièces, 50 itérations |
| Certification | < 5 ms | — |
| *Pour mémoire :* une simulation exacte | **minutes à heures** | — |

**La lecture de ce tableau est l'argument de faisabilité du projet.** La légalisation
performantielle coûte cent fois plus cher que la correction classique, et **dix mille à
un million de fois moins cher qu'une seule simulation exacte**. C'est ce rapport qui
permet cinquante évaluations de lumière là où on ne pourrait pas en faire une.

---

## Contexte scientifique

### Trois littératures qui ne se lisent pas

| Littérature | Où elle se publie | Ce qu'elle sait |
|---|---|---|
| Légalisation / placement | Automatisation de la conception électronique | Corriger un placement exactement, en millisecondes |
| Substituts environnementaux | Physique du bâtiment | Prédire l'éclairement sans simuler |
| Génération de plans | Vision par ordinateur | Produire des plans plausibles |

Aucune conférence, aucun relecteur, aucun vocabulaire communs. Le seul domaine qui aurait
besoin des trois — la génération de plans — s'est constitué en vision par ordinateur et
ne lit ni les deux autres.

### Ce qui est nouveau

- **Légalisation à objectif physique.** Personne n'a remplacé la proximité géométrique
  par un objectif ayant un sens architectural.
- **Substitut d'éclairement calibré.** Les substituts publiés ne publient pas de borne
  d'erreur, ce qui laisse ouverte la question de savoir si le générateur optimise la
  performance réelle ou l'erreur de l'estimateur.
- **Deux garanties de natures distinctes produites ensemble**, et refus explicite de les
  confondre.
- **Diagnostic dual architectural** : les variables duales du solveur, traduites en
  phrases lisibles par un maître d'œuvre.
- **Certificat d'infaisabilité** : un système génératif qui refuse et explique, plutôt
  que de produire un plan faux.

### Références fondatrices

- Moffitt M. D., Ng A. N., Markov I. L., Pollack M. E. (2008). *Constraint-Driven
  Floorplan Repair*. ACM TODAES.
- Murata H., Fujiyoshi K., Nakatake S., Kajitani Y. (1996). *VLSI Module Placement Based
  on Rectangle-Packing by the Sequence-Pair*. IEEE TCAD.
- Lacoste-Julien S., Jaggi M. (2015). *On the Global Linear Convergence of Frank-Wolfe
  Optimization Variants*. NeurIPS.
- Vovk V., Gammerman A., Shafer G. (2005). *Algorithmic Learning in a Random World*.
- Shabani M. A., Hosseini S., Furukawa Y. (2023). *HouseDiffusion*. CVPR.
- van Engelenburg C. et al. (2024). *MSD: A Benchmark Dataset for Floor Plan Generation
  of Building Complexes*. ECCV.

---

## Feuille de route

| Jalon | Contenu | Ce qui fonctionne | État |
|:--:|---|---|:--:|
| 1 | `types`, entrées/sorties JSON | Aller-retour de plans | ✅ |
| **2** | `geom`, `lmo`, `certify.preuve` | **Légalisation classique + preuve** | ✅ |
| **3** | `light.analytique`, `orient`, `solve` | Légalisation performantielle **sans apprentissage** | ✅ |
| **4** | `light.jetons`, `light.base`, `light.validation` | Perceptron `numpy` + **point de contrôle** du gradient contre `SimulateurExact` | ✅ |
| 5 | `uq`, `certify.borne`, `certify.dual` | Certificat complet, diagnostic, couverture sur oracle gelé | ✅ |
| 6 | Non-Manhattan, apprentissage actif, IFC | L ✅ · actif ✅ · IFC ✅ | ✅ |
| **7** | **Corpus réel** : chargeur WKT, transformeur, couverture mesurée | chargeur, `light/radiance.py`, `SubstitutAppris` `.pt` | ⬜ |

**Le jalon 3 mérite d'être signalé :** la chaîne complète y tourne avec un modèle de
lumière en formules fermées, **avant toute dépense de simulation ou d'entraînement**.
C'est ce qui valide l'architecture au troisième mois plutôt qu'au dix-huitième.

**Le jalon 7 est la condition d'une publication scientifique.** Les jalons 1 à 6
établissent que la mécanique tient de bout en bout sur un oracle analytique gelé ; ils
n'établissent rien sur une grandeur physique mesurée. Voir
[`docs/donnees/verite-terrain.md`](docs/donnees/verite-terrain.md).

Détail : [`MILESTONE-2.md`](docs/specification/MILESTONE-2.md),
[`MILESTONE-3.md`](docs/specification/MILESTONE-3.md),
[`MILESTONE-4.md`](docs/specification/MILESTONE-4.md),
[`MILESTONE-5.md`](docs/specification/MILESTONE-5.md) (terminés).
Jalon 6 : [`docs/specification/`](docs/specification/).

---

## Reproductibilité

Toute exécution produit un **manifeste**, sans exception. Exemple de **format**
(valeurs illustratives) :

```json
{
  "archlux": "0.10.0.dev0",
  "horodatage": "2026-08-27T14:32:11Z",
  "graine": 17,
  "empreinte_donnees": "sha256:9c2f...",
  "decoupage": "splits/v2",
  "environnement": {"python": "3.12.4", "ortools": "9.8.3296", "torch": "2.2.1"},
  "modele": {"poids": "sha256:4a1b...", "calibration_n": 1284, "calibration_alpha": 0.10},
  "parametres": {"budget": 0.25, "max_iter": 50, "tol": 1e-4}
}
```

- Toute fonction qui échantillonne exige une **graine, sans valeur par défaut**.
- Les découpages sont **figés et publiés** sous forme de listes d'identifiants.
- Les résultats bruts sont publiés **avant** toute agrégation.
- **Le jeu de calibration est publié avec le modèle.** Sans lui, une borne conforme
  annoncée est invérifiable — et publier une garantie invérifiable, ce n'est pas publier
  une garantie.
- Tout changement de comportement de l'oracle ou du certificat est une **version majeure**.

---

## Limites

**À lire avant tout usage professionnel.** Version complète :
[`docs/limites.md`](docs/limites.md).

- Les indicateurs produits sont des **estimations de phase amont**. Ils ne se substituent
  pas à une étude thermique ou d'éclairement réglementaire.
- La garantie de performance suppose l'**échangeabilité** avec le jeu de calibration.
  Les plans produits par un optimiseur sont *sélectionnés* pour maximiser la prédiction :
  la couverture réelle sous cette sélection est une question de recherche ouverte, mesurée
  et publiée par le projet.
- Le champ **`NON EVALUABLE`** du certificat couvre les articles dont la vérification
  exige une information absente du plan — matériaux, systèmes techniques — ou une
  interprétation.
- La vérification réglementaire calcule des prédicats sur une géométrie. **Elle ne
  constitue pas un avis juridique** et ne remplace pas un professionnel habilité.
- Le jalon courant traite les géométries rectangulaires ; les pièces en L arrivent au
  jalon 6.

> **Un plan produit par ce système est une proposition, jamais un document de projet.
> La responsabilité de conception et de signature demeure celle d'un professionnel
> habilité.**

---

## Documentation

| | |
|---|---|
| [**Galerie d'exemples**](docs/galerie/) | Le plus rapide pour commencer |
| [Tutoriels](docs/tutoriels/) | Parcours guidés |
| [Concepts](docs/concepts/) | Le pourquoi, plutôt que le comment |
| [Référence d'API](docs/reference/) | Signatures et détails |
| [**Limites**](docs/limites.md) | Ce que le système ne fait pas |
| [`ARCHITECTURE.md`](docs/specification/ARCHITECTURE.md) | Pour contribuer au code |
| [`DOCUMENTATION.md`](docs/specification/DOCUMENTATION.md) | Conventions de documentation |

---

## Contribuer

Voir [`CONTRIBUTING.md`](CONTRIBUTING.md).

**Avant toute contribution, lire [`ARCHITECTURE.md`](docs/specification/ARCHITECTURE.md).** Les règles de
dépendance sont contraignantes et vérifiées automatiquement — en particulier :
`geom`, `lmo`, `solve` et `certify` **ne doivent jamais importer `torch`**.

Une fonction publique sans docstring est une fonction non terminée.

---

## Citer ce travail

```bibtex
@software{archlux,
  title  = {archlux: geometric legalization of generated floor plans
            with conformally bounded daylight surrogates},
  year   = {2026},
  url    = {https://github.com/ORG/archlux},
  doi    = {10.5281/zenodo.XXXXXXX},
  version = {0.10.0.dev0}
}
```

**Citer une version étiquetée, jamais « le dépôt ».** Un certificat doit rester traçable
à une version exacte de la bibliothèque et de sa calibration. Voir aussi
[`CITATION.cff`](CITATION.cff) (version de développement **0.10.0.dev0** ; aucune version n'est encore publiée).

---

## Licence

Apache 2.0 — voir [`LICENSE`](LICENSE). Licence permissive avec clause de brevet,
choisie pour permettre l'usage industriel, condition d'adoption par les bureaux d'études.
