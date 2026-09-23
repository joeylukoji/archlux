# Audit du projet archlux — points d'amélioration

> Audit réalisé le 23/09/2026 sur l'état du dossier `archlux/` (version déclarée 1.0.0).
> Méthode : exécution réelle de la suite de tests, du lint, du typage et de la couverture,
> relecture du code, des résultats (`resultats/`) et de la documentation, puis quatre
> revues spécialisées menées avec les skills du projet (`python-design-patterns`,
> `architecture-blueprint-generator`, `review-and-refactor`, `python-expert`).
> Aucune ligne de code n'a été modifiée pendant cet audit.
>
> Chaque constat cite un fichier (et une ligne quand c'est utile). Les notes sont sur 10.
> Elles sont sévères là où un utilisateur externe ou un relecteur d'article le serait.

---

## Sommaire

1. [Synthèse en une page](#1-synthèse-en-une-page)
2. [Mesures objectives](#2-mesures-objectives)
3. [Les 10 corrections prioritaires](#3-les-10-corrections-prioritaires)
4. [Structure du code](#4-structure-du-code)
5. [Architecture choisie](#5-architecture-choisie)
6. [Qualité du code](#6-qualité-du-code)
7. [Types et modèle de données](#7-types-et-modèle-de-données)
8. [Utilisabilité dans un cas concret](#8-utilisabilité-dans-un-cas-concret)
9. [Notes par fonctionnalité](#9-notes-par-fonctionnalité)
10. [Notes par tâche demandée (jalons)](#10-notes-par-tâche-demandée-jalons)
11. [Publication open source](#11-publication-open-source)
12. [Rédaction d'un article](#12-rédaction-dun-article)
13. [Plan d'action proposé](#13-plan-daction-proposé)

---

## 1. Synthèse en une page

| Axe | Note | En une phrase |
|---|--:|---|
| Idée / originalité scientifique | **8,5/10** | Réutiliser l'oracle de légalisation comme LMO de Frank-Wolfe et séparer preuve exacte et borne conforme est une idée neuve et bien argumentée. |
| Honnêteté scientifique et documentation des limites | **9/10** | Rare : les résultats négatifs sont mesurés, publiés et expliqués (`docs/limites.md`, `resultats/`). |
| Structure du code | **6/10** | Découpage en couches sain sur le papier, mais les règles de dépendance sont violées à l'exécution et plusieurs modules sont trop gros. |
| Architecture choisie | **5,5/10** | Découpage sain, mais trois garanties annoncées ne tiennent pas dans le code et le README affirme des propriétés mathématiques fausses (gap FW, coupes tangentes, itérés valides). |
| Qualité du code | **6,5/10** | ruff/mypy/tests verts, mais les tests n'exercent jamais les surfaces minimales en mode performance, ce qui masque deux défauts critiques ; 0 cas de référence. |
| Types et modèle de données | **6/10** | `mypy --strict` propre, types gelés, mais aucune validation d'entrée et des tableaux mutables dans des types « gelés ». |
| Ergonomie de l'API | **4/10** | Six appels montrés dans le README n'existent pas ou ont une autre signature. |
| Utilisable dans un cas concret aujourd'hui | **3/10** | La légalisation classique marche (avec `pavage=True`), mais les murs porteurs ne sont pas vérifiés et le mode « lumière » échoue sur un T3 réaliste. |
| Prêt pour une publication open source | **4/10** | Pas de fichier `LICENSE`, pas de dépôt git, placeholders `ORG` et DOI, README faux. |
| Prêt pour un article | **5/10** | Un article « méthode + résultats négatifs mesurés » est défendable ; un article « on améliore la lumière » ne l'est pas encore. |

**Verdict global : 6/10.** Le projet est intellectuellement solide et d'une honnêteté
rare, mais il a été livré en « 1.0.0 » alors que plusieurs promesses publiques (README,
certificat de structure, mode performance, test utilisateur externe du jalon 6) ne
tiennent pas. La priorité n'est pas d'ajouter des fonctionnalités, c'est de **rendre
vrai ce qui est affiché**.

### Ce qui est remarquablement bien fait (à garder absolument)

- **Le principe « un solveur, deux vecteurs objectifs »** : `lmo` ignore l'origine de `c`,
  ce qui rend la comparaison légalisation classique / performantielle irréprochable
  (même solveur, même tolérance, même point de départ).
- **Deux garanties de natures différentes, séparées dans les types** :
  `PreuveGeometrique` (aucun champ probabiliste) et `BornePerformance`
  (toujours `couverture` + `n_calibration`).
- **Prédiction conforme correcte** : rang `ceil((n+1)(1-α))` dans `uq/conforme.py`,
  jamais `np.quantile` ; couverture mesurée 90,2 % pour 90 % visés.
- **Rigueur expérimentale** : découpage par site (et non par appartement), intervalles de
  Wilson partout, graines explicites, résultats bruts publiés avant agrégation.
- **Résultats négatifs assumés** : le substitut analytique est battu par l'aire au sol,
  l'apprentissage actif perd contre l'aléatoire, 0 plan généré sur 740 n'est valide.
  Tout est écrit. C'est la meilleure qualité du projet.
- **`torch` hors du noyau**, vérifié par test.
- **Performance** : budgets §9 tenus avec une large marge (LP à chaud 0,5 ms pour 3 ms
  de budget, légalisation classique 12,8 ms pour 20 ms).

---

## 2. Mesures objectives

Mesures exécutées pendant l'audit (Python 3.13.5, Windows 11).

| Mesure | Résultat | Commentaire |
|---|---|---|
| Tests (`pytest`) | **529 passés, 0 échec** | 53 fichiers de test, ~5 500 lignes. |
| Tests avec `--benchmark-disable` | **5 échecs** | `benchmarks/test_budgets.py:80,91,133,144,158` lisent `benchmark.stats` qui vaut `None` quand les benchmarks sont désactivés. Fragilité, pas un vrai bogue. |
| Couverture de lignes | **84 %** | La doc (`docs/publication-1.0.md`) annonce **89 %** : chiffre à corriger. |
| Modules à 0 % de couverture | `export/svg.py`, `data/corruption.py`, `data/imputation.py` | `imputation.py` n'est importé nulle part : code mort. |
| Modules sous 70 % | `light/objectif.py` 58 %, `bench/protocole.py` 67 %, `bench/stats.py` 68 %, `geom/rectilineaire.py` 69 % | `light/objectif.py` contient `Daylight`, justement cassé (§8). |
| `ruff check .` | Propre | |
| `ruff format --check .` | **78 fichiers non formatés** | Le formatage n'est pas imposé en CI. |
| `mypy src/` (strict) | Propre, 65 fichiers | |
| `interrogate` (docstrings) | 97 % (seuil 95 %) | |
| Taille du code | 11 821 lignes dans `src/`, 1 565 dans `experiences/` + `scripts/` | |
| Temps d'`import archlux` | **~3,1 s** | scipy.stats (1,2 s) chargé via `certify/__init__` → `borne` → `uq`. |
| Budgets de performance §9 | Tous tenus | LP froid 1,6 ms / 10 ; LP chaud 0,5 / 3 ; polytope 2,0 / 5 ; classique 12,8 / 20 ; performantielle 32 / 500 ms. |
| Dépôt git | **Absent** | `git log` : « not a git repository ». |
| Fichier `LICENSE` | **Absent** | Pourtant référencé par le README, `CONTRIBUTING.md` et `pyproject.toml`. |

---

## 3. Les 10 corrections prioritaires

Classées par gravité. Les quatre premières touchent à la **véracité** de ce que le
projet affirme, ce qui est plus grave qu'un défaut de style.

| # | Gravité | Problème | Où | Correction |
|--:|---|---|---|---|
| 1 | **Critique** | Le certificat affiche « Structure préservée : oui, vérifié » alors qu'une pièce peut traverser un mur porteur. Les murs ne sont pas des variables du solveur (`A_eq` vide) et `_structure` compare seulement les murs à eux-mêmes : le test est toujours vrai. Les poteaux ne sont jamais vérifiés. | `src/archlux/certify/preuve.py:166`, `src/archlux/geom/polytope.py:351` | Vérifier qu'aucune pièce ne coupe un porteur ni ne contient un poteau. En attendant, afficher « Structure : NON VÉRIFIÉE » et le documenter dans `docs/limites.md`. Pour un projet dont la thèse est « la géométrie est prouvée », c'est le défaut n°1. |
| 2 | **Critique** | Le README montre 6 appels qui échouent : `ax.referentiel`, `Structure.from_dxf`, `Daylight(metric=, alpha=)`, `is_feasible(programme, structure, ctx)` à 2 arguments utiles, `ax.data.generator_outputs`, `Contexte.sweep_orientation`. | `README.md` l.149-217 | Soit implémenter, soit réécrire le « Démarrage rapide » avec du code réellement exécuté (idéalement testé par doctest ou par un test qui exécute le README). |
| 3 | **Critique** | `legalize(..., objective=Daylight(...))` plante : `Daylight.evaluer()` n'accepte pas l'argument `baies` du protocole `Substitut`, alors que `isinstance(dl, Substitut)` renvoie `True`. Aucun test d'intégration ne le couvre. | `src/archlux/light/objectif.py:48,75,82,86` | Ajouter `*, baies=None` et le transmettre ; ajouter un test `legalize(..., objective=Daylight(...))`. |
| 4 | **Critique** | Pas de fichier `LICENSE` alors que la licence Apache-2.0 est annoncée partout. Juridiquement, sans ce fichier, personne n'a le droit de réutiliser le code. | racine | Ajouter le texte officiel Apache-2.0 (et un `NOTICE` si besoin). |
| 5 | **Majeur** | Les règles de dépendance §5 sont respectées dans le texte des imports mais violées à l'exécution : `import archlux` charge 32 modules dont `light.analytique`, `light.simulateur`, `uq.*`. `feasibility` charge `light` et `uq` alors que c'est interdit. | `src/archlux/light/__init__.py`, `src/archlux/certify/__init__.py`, `src/archlux/api.py` | Rendre les `__init__` de `light` et `certify` paresseux ; ajouter un test dynamique sur `sys.modules`. |
| 6 | **Critique** | Le mode performantiel ne garantit pas les surfaces minimales : sur un T3 réaliste comme sur le plan du benchmark avec `aires_min` ≥ 9 m², il lève `InvariantViole`. Frank-Wolfe accepte un pas avant d'enrichir les coupes tangentes, qui sont des relaxations. Les tests ne le voient pas car ils utilisent tous `aires_min=()`. | `src/archlux/solve/frank_wolfe.py:236-307`, `src/archlux/api.py:292-315` | Resserrer les bornes au départ (domaine convexe) ou refuser un pas qui viole une surface ; à défaut, revenir au plan classique prouvé valide. Ajouter un test de propriété avec `aires_min` non vide. |
| 7 | **Majeur** | La première erreur ne guide pas : `legalize(plan, ctx)` par défaut échoue sur « jours : aire non couverte » sans suggérer `pavage=True`, alors que vos mesures donnent 93,9 % de réussite avec pavage contre 35,9 % sans. | `src/archlux/api.py:281` | Ajouter « relancer avec `pavage=True` » au message ; envisager `pavage=True` par défaut en 2.0. |
| 8 | **Majeur** | Aucune validation des entrées : `w = -1`, `w = NaN`, `Orientation(720)`, faute de frappe dans un type de pièce (`"sejuor"` → surface minimale 0 sans avertissement), ids en double. Les erreurs qui en résultent sont trompeuses (« statut LP inattendu : limite »). | `src/archlux/api.py:238`, `src/archlux/types.py` | Valider une fois à l'entrée de `legalize` (le coût est négligeable, l'objection de l'ADR-6 ne s'applique pas à un contrôle unique). |
| 9 | **Majeur** | Le certificat affiche « archlux 0.0.0 » alors que `__version__` vaut 1.0.0 : deux sources de vérité pour la version. Et la section DIAGNOSTIC affiche des lignes internes (« ecart moins sdb.x ») illisibles pour un architecte. | `src/archlux/certify/rapport.py:22-24`, `src/archlux/api.py:285` | Une seule source de version ; filtrer les duaux sur les origines métier. |
| 10 | **Majeur** | Pas de dépôt git, donc pas d'historique. Le jalon 6 exige lui-même « au moins 6 mois d'historique public », et les revues logicielles (JOSS) aussi. | racine | `git init` maintenant, premier commit propre, puis publication. Plus tôt l'historique commence, mieux c'est. |

---

## 4. Structure du code

*Revue menée avec le skill `python-design-patterns` (KISS, SRP, composition, couplage,
règle de trois).*

### Note globale : 6/10

Les idées sont saines : protocole `Substitut`, types gelés, `lmo` qui ignore d'où vient
`c`, test de dépendances. Mais la chaîne d'import charge toute la bibliothèque dès
qu'on importe un seul sous-module, trois modules dépassent 600 lignes, et plusieurs
conventions sont dupliquées puis divergent.

### Notes par module

| Module | Note | Justification |
|---|--:|---|
| `types` | 7/10 | Types gelés et invariants propres, mais `Plan.trace: object` (`types.py:195`) range un artefact du solveur dans l'entité métier ; `ModeleTrace` et `Manifeste` sont des besoins de `bench`. |
| `geom` | 5,5/10 | `pavage.py` fait 621 lignes, dont `deduire_trame` (l.365) : 140 lignes et 29 branches. `diagnostic.py` décrit un corpus et n'a rien à faire dans cette couche. |
| `lmo` | 7,5/10 | Découpage cohérent (`solveur` / `coupes`). `resoudre` (`solveur.py:242`) fait 135 lignes. |
| `solve` | 6/10 | `frank_wolfe` (`frank_wolfe.py:129`) : 12 paramètres, 228 lignes, 27 branches. |
| `light` | 6/10 | `Daylight` est une bonne composition, mais `light/__init__.py` importe toutes les implémentations. `SubstitutDense` (`base.py:126`) mélange modèle, entraînement et sérialisation. |
| `orient` | 7/10 | Cohérent, mais 5 `ValueError` au lieu d'exceptions typées (§7). |
| `uq` | 6/10 | `conforme.py` est exemplaire. Mais `gestion.py:72-90` lit par réflexion les champs internes `W1..b3` de `SubstitutDense` : couplage caché que le test d'import ne voit pas. |
| `active` | 5,5/10 | `Loop.run` (`boucle.py:205`) : 180 lignes, 26 branches, trois paires de listes parallèles validées à la main. |
| `export` | 7/10 | Couche feuille, SVG sans dépendance. Mais `ifc.py:10` importe le paquet racine (donc tout), et `_ecrire_spf_minimal` fait 208 lignes. |
| `feasibility` | 4,5/10 | 80 lignes de code métier dans un `__init__.py` ; lance un `legalize` complet pour répondre oui/non ; laisse s'échapper `InvariantViole` ; expose `dataclass`, `replace`, `legalize` dans son espace de noms. |
| `certify` | 8/10 | Petit, focalisé, une responsabilité par fichier. Seul défaut : `__init__` réexporte `borne`, donc charge `uq` et scipy.stats. |
| `bench` | 7/10 | Cohérent, arguments nommés obligatoires, graines dérivées. `run` a 10 paramètres ; alias redondant `Manifest = Manifeste`. |
| `data` | 5/10 | `chargeurs.py` (845 lignes) a trois responsabilités ; `_convertir` (l.518) : 132 lignes, 35 branches. `imputation.py` est du code mort. |
| `io` | 7,5/10 | `json_io.py` reste cohérent (une seule raison de changer : le schéma). |
| `api` / `erreurs` | 6/10 | `erreurs.py` est propre. `legalize` (`api.py:115`) : 8 paramètres, 2 pipelines dans une fonction, un couple de drapeaux dépendants (`pavage` / `budget_reparation`). |

### Points d'amélioration de la structure

**Critique**

- **C1. Règles §5 violées à l'exécution** (voir correction n°5 du §3). Trois causes :
  `archlux/__init__.py` importe `api` qui charge `solve`, `certify`, `light.protocole` ;
  `from archlux.light.protocole import …` exécute d'abord `light/__init__.py` qui importe
  toutes les implémentations ; `certify/__init__.py` importe `borne` qui charge `uq`.
- **C2. Deux trous dans `tests/test_dependances.py`** : le filtre `startswith("archlux.")`
  laisse passer `from archlux import __version__` (`export/ifc.py:10`,
  `bench/manifeste.py:13`) ; le contrôle est purement statique. Déplacer `__version__`
  dans `archlux/_version.py` et ajouter un test dynamique.

**Majeur**

- **M1.** Découper `data/chargeurs.py` en `data/msd.py` (conversion WKT),
  `data/etiquettes_sd.py` (étiquettes de simulation), et déplacer `decouper_par_site`
  dans `data/decoupage.py`. Regrouper les 5 réglages de `charger_msd` dans une dataclass.
- **M2.** Sortir le code métier de `feasibility/__init__.py` vers `feasibility/verdict.py` ;
  ne tester que la faisabilité du LP, sans l'objectif L1.
- **M3. Le découpage en secteurs d'azimut existe en 3 versions qui divergent** :
  `orient/circulaire.py:288` (secteurs centrés), `uq/fiabilite.py:114` (secteurs alignés
  sur les bords), `light/analytique.py:75` (réécrit à la main). Conséquence : une « strate
  N » du banc ne correspond pas au secteur 0 de la couverture conforme. Une seule fonction
  `secteur(deg, n, *, centre)` dans `orient`.
- **M4.** Le contrat de vectorisation (4 champs par pièce) est copié 3 fois
  (`geom/polytope.py:37`, `light/analytique.py:31`, `light/jetons.py:28`). Le placer dans
  `types` et exposer `vectoriser(plan)`.
- **M5.** La détection de chevauchement existe en 3 versions avec des tolérances
  différentes (`certify/preuve.py:98`, `geom/diagnostic.py:146`, `export/pathologie.py`).
  Risque : `export` déclare un plan exportable alors que `certify` y voit un chevauchement.
- **M6.** Remplacer la réflexion de `uq/gestion.py:72-90` par un protocole `Empreintable`.
- **M7.** Regrouper `coupes`, `pieces`, `ctx` de `frank_wolfe` (qui vont toujours ensemble)
  dans une dataclass `ContraintesSurface`.
- **M8.** Scinder `legalize` en `_polytope_du_plan`, `_legaliser_l1`, `_optimiser_lumiere` ;
  fusionner `pavage` + `budget_reparation` en `pavage: int | None = None` ; sortir `trace`
  de `Plan`.
- **M9.** `Loop.run` : une dataclass `Lot(x, orientations)` qui vérifie les longueurs, et un
  protocole `Ajustable` à la place de `getattr(..., "ajuster")`.
- **M10.** Séparer `geom/pavage.py` en `geom/trame.py` (inférence et réparation de la trame)
  et `geom/pavage.py` (contraintes linéaires).
- **M11.** Déplacer `geom/diagnostic.py` vers `data/diagnostic.py`.
- **M12. Scripts d'expérience** : la règle §11 dit « plus de 50 lignes = fonction manquante
  dans la bibliothèque ». **9 scripts sur 13 la violent**, et la plupart importent des
  modules internes, voire des fonctions privées d'un autre script
  (`from j8_generation import _construire, _echelle`).

| Script | Lignes | Fonction qui manque dans la bibliothèque |
|---|--:|---|
| `j8_generation.py` | 439 | Chargeur « plan généré (boîtes JSON) → `Plan` + `Contexte` » ; synthèse Wilson générique dans `bench.report`. |
| `j8_visuels.py` | 181 | `export.svg.dossier(paires)` pour les fiches avant/après. |
| `j9_orientation.py` | 173 | `vectoriser(plan)` / `evaluer_plan(substitut, plan, ctx)` sans construire de polytope. |
| `j7_sd_par_piece.py` | 131 | Constructeur de jeu supervisé `(x, y, orientation, baies)`. |
| `j7_sd_etiquettes.py` | 130 | Idem. |
| `j6_actif.py` | 71 | Générateur de vecteurs synthétiques dans `data.synthese`. |
| `j7_msd_reparation.py` | 62 | `bench.run` sur des corruptions. |
| `j6_survie_ifc.py` | 58 | Cas limite. |
| `j7_msd_idempotence.py` | 54 | Cas limite. |

**Mineur**

- Mélange français / anglais dans l'API publique (`legalize`, `is_feasible`, `Daylight`,
  `Loop` d'un côté ; `verifier_exactement`, `construire_borne`, `CalibrateurConforme` de
  l'autre) et deux alias doublons (`ExactSimulator = SimulateurExact`,
  `Manifest = Manifeste`). Écrire la règle dans §7 et supprimer les alias.
- Deux fonctions publiques `diagnostiquer(plan)` aux types de retour différents
  (`geom/diagnostic.py:84`, `export/pathologie.py:34`).
- `ValueError` au lieu d'exceptions typées : `orient/circulaire.py:70,101,273,275,303`,
  `geom/diagnostic.py:142`, `light/jetons.py:37`, `export/svg.py:269`.
- `structlog` (§7) n'est utilisé que dans `lmo/coupes.py` et `active/boucle.py`.
- `light/analytique.py:73-75` encode l'orientation en cos/sin puis revient à l'angle par
  `atan2` : aller-retour inutile.
- **`ARCHITECTURE.md` §4, §5 et §11 sont périmés** : l'arborescence cible ne mentionne ni
  `api.py`, ni `erreurs.py`, ni `geom/{pavage,rectilineaire,diagnostic}.py`, ni
  `feasibility/`, ni `active/`, ni la plupart de `export/` et `data/`.

---

## 5. Architecture choisie

*Revue menée avec le skill `architecture-blueprint-generator` : elle juge si
l'architecture est bonne, pas seulement si elle est documentée. Les constats marqués
**[mesuré]** viennent de sondes Python exécutées en mémoire.*

### Note globale : 5,5/10

Le découpage est sain : noyau pur, protocole étroit, types de garantie séparés, règles de
dépendance testées, docstrings honnêtes sur beaucoup de limites. Mais **trois garanties
annoncées ne tiennent pas dans le code** (structure porteuse, `Daylight`, surfaces en
mode performantiel), et la documentation vend plus que ce que le code tient.

| Question d'architecture | Note | Verdict |
|---|--:|---|
| 1. Oracle LP partagé (légalisation + Frank-Wolfe) | 6/10 | Bon principe, bien appliqué. Mais le gap FW n'est pas une borne pour ces substituts, et les coupes cassent le démarrage à chaud. |
| 2. Ordre relatif fixé par le générateur | 5/10 | Ce choix garde un LP convexe, rapide et vérifiable. Mais on optimise dans **une seule cellule** d'un problème disjonctif, choisie par une heuristique gloutonne. |
| 3. Séparation exact / probabiliste | 5/10 | 8/10 dans les types, 3/10 sur le fond : prédicat « exact » vide (structure), couverture nominale affichée sur des plans optimisés, Farkas jamais revérifié. |
| 4. Solveurs et tolérances | 5/10 | Seul GLOP (OR-Tools) résout. La « preuve exacte » est en flottants via GEOS, avec des tolérances de 1e-9 à 1e-6. |
| 5. Couche `light` | 4/10 | Acceptable comme oracle figé de CI (7/10), pas comme vérité terrain scientifique (2/10). σ constant dans les trois substituts. |
| 6. Scalabilité | 6/10 | Temps corrects jusqu'à 150 pièces. Mais les budgets §9 ne sont mesurés que sur le cas le plus favorable. |
| 7. Extensibilité | 4/10 | Ajouter un indicateur (éblouissement, thermique) touche ≥ 7 fichiers ; ajouter une règle réglementaire, 6-7 fichiers. |

### 5.1 Frank-Wolfe : ce que le gap garantit vraiment

L'inégalité utilisée par le README,

$$g_k = \langle \nabla f(x_k),\, s_k - x_k \rangle \;\ge\; f^\star - f(x_k),$$

n'est vraie que si $f$ est **concave** (on maximise). Or le substitut analytique
(`light/analytique.py:168-193`) vaut

$$f = (w\cos^2\theta + h\sin^2\theta)\cdot\min(w\sin^2\theta + h\cos^2\theta,\,P)\cdot e^{\kappa(-x\sin\theta - y\cos\theta)}.$$

À $\theta = 0$ le premier facteur donne $w\,h$, de hessienne $\begin{pmatrix}0&1\\1&0\end{pmatrix}$,
non définie ; l'exponentielle est convexe ; le `min` la rend non lisse. **$f$ n'est pas
concave.** Sur un objectif non concave, le gap mesure seulement la stationnarité au
premier ordre (Lacoste-Julien, 2016 : taux $O(1/\sqrt{k})$ vers un point stationnaire),
pas l'écart à l'optimum.

- La phrase du README (`README.md:285`) « je suis à au plus 0,4 point du meilleur plan »
  est donc fausse pour les substituts livrés.
- `solve/frank_wolfe.py:211` initialise `gap = 0.0` : si le premier LP n'est pas
  optimal, on sort avec un gap nul qui se lit « optimum atteint ». Initialiser à `inf`.
- Le gap rendu est celui de l'itéré précédent, pas du `x` rendu (`:240`, `:349-356`).
- **[mesuré]** Sur une grille 5×3 avec `a_min = 6`, FW s'arrête à 17 itérations sur 50
  avec un gap de 29,1 : l'arrêt vient de l'échec de la recherche de pas, pas de la
  convergence, et **aucun avertissement n'est émis**.
- **Les coupes désactivent le démarrage à chaud** (`lmo/solveur.py:321`) et
  `api.py:305` en passe dès qu'une surface minimale existe : en mode performantiel
  réaliste, chaque LP est reconstruit à froid — exactement l'anti-pattern §10. Le
  benchmark ne le voit pas, car il utilise `aires_min=()`.

**Correction** : renommer en `gap_stationnarite`, initialiser à `inf`, recalculer au `x`
rendu, exposer un statut d'arrêt (`converge`, `recherche_de_pas`, `lp_non_optimal`,
`max_iter`) ; mettre les coupes en cache ; ajouter des benchmarks réalistes.

### 5.2 L'ordre relatif fixé : une seule cellule combinatoire

L'ensemble réellement admissible (pièces sans chevauchement) est une **union disjonctive**
de jusqu'à $4^{n(n-1)/2}$ polytopes (gauche / droite / dessus / dessous par paire).
`deduire_ordre` (`geom/graphe.py:186-200`) choisit un axe par paire, de façon gloutonne,
sans retour arrière ; puis `figer_contacts` (`geom/polytope.py:122-198`) fige la topologie.

- `ARCHITECTURE.md` §1 (« parmi toutes les corrections valides ») est faux : c'est
  « parmi les corrections qui gardent l'ordre et les contacts ».
- **Le certificat d'infaisabilité est relatif à l'ordre.** Un Farkas sur une seule
  cellule ne prouve pas que le programme est infaisable ; il faudrait couvrir toutes les
  disjonctions (MILP, ou énumération de *sequence-pairs*). Reformuler en « infaisable
  pour cet ordre relatif ».
- Faux `Infaisable` possible : `lmo/coupes.py:449` fait `domaine = resserre`, or le
  resserrement des bornes n'est pas une approximation extérieure (risque déduit de la
  lecture, non reproduit).
- **Pièces en L** : `geom/rectilineaire.py:385-420` n'impose que `x_i + w_i = x_j` ; rien
  n'oblige les intervalles orthogonaux à se recouvrir, donc un L peut devenir un Z ou se
  déconnecter. La surface est contrôlée par sous-rectangle (`certify/preuve.py:144-155`)
  et non sur le polygone recomposé.
- **Non-Manhattan** : `decomposer` lève sur toute arête oblique. Le « Non-Manhattan ✅ »
  du README (l.603) est faux, et contredit la l.667.
- **Enveloppe** : seule la boîte englobante du contour est utilisée
  (`polytope.py:201-210`) ; un contour en L n'est traité que par `pavage=True`.

### 5.3 Séparation exact / probabiliste

**Ce qui tient** : types disjoints (`types.py:317-356`), sections `[EXACT]` /
`[PREDICTION]`, pas de score composite. C'est la meilleure idée du projet.

**Ce qui ne tient pas**

- **Structure porteuse** (voir §3 n°1). **[mesuré]** Mur porteur en x = 6 sur une grille
  5×3 : après Frank-Wolfe, les cloisons sont à {0 ; 1,898 ; 3,796 ; 11,204 ; 13,102 ; 15},
  aucune à x = 6, et pourtant `structure_preservee=True`. Même cause : les **ouvertures**,
  relatives à des murs qui ne bougent jamais, restent à leur position absolue pendant que
  les pièces bougent — l'affirmation « les fenêtres suivent » (`README.md:314`) est vide.
- **Couverture affichée sans régime** : le rapport affiche
  `[PREDICTION — couverture 90 %]` (`certify/rapport.py:58-59`) que le plan soit
  échangeable avec la calibration ou choisi par l'optimiseur.
- **Validité conforme après optimisation.** La garantie
  $P(Y \ge \hat y - \hat q\,\sigma) \ge 1-\alpha$ suppose $(X, Y)$ échangeable avec la
  calibration. Or $x^\star = \arg\max\, \hat y(x) - \hat q\,\sigma(x)$ la casse deux fois :
  décalage de distribution, et **malédiction du vainqueur** (l'argmax va précisément là
  où $\hat y - y > 0$, donc la borne basse publiée est biaisée — c'est le point 1 du
  README lui-même). Cadres corrects : *feedback covariate shift* (Fannjiang et al.,
  PNAS 2022), sélection conforme (Jin & Candès, 2023), ou réévaluation du plan choisi par
  l'oracle.
- `uq/derive.py:57-133` (test KS par permutations) suppose de connaître le vrai `y` des
  plans choisis ; `certify/borne.py:59-61` traite le non-rejet comme une autorisation de
  publier ; **rien n'appelle `construire_borne` automatiquement** : `legalize` rend
  toujours `performance=None` (`api.py:326-328`).
- `uq/conforme.py:292` : `empreinte_jeu` hache les **scores**, pas le jeu de données ; elle
  ne permet ni de vérifier le jeu ni de détecter une fuite.
- **Farkas jamais revérifié** : les duaux GLOP en flottants sont présentés comme
  « preuve d'inexistence — nature exacte », sans vérifier $y \ge 0$, $y^\top A = 0$,
  $y^\top b < 0$.

**Correction** : champ `regime: Literal["echangeable", "selectionne_non_garanti"]` dans
`BornePerformance`, bandeau distinct dans le rapport, et refus de publier une borne sur
un plan sélectionné sans réévaluation par l'oracle.

### 5.4 Solveurs et tolérances

- Solveur réellement utilisé : **GLOP uniquement** (`lmo/solveur.py:23,122`). scipy ne
  sert qu'aux matrices creuses et aux tests statistiques.
- `depart=` n'est jamais transmis numériquement à GLOP : il sert seulement de clé de
  cache (ADR-8). Honnête, mais le nom trompe.
- **La « preuve exacte » est en flottants** (`certify/preuve.py:58-62`) : chevauchement
  1e-9 m², jours 1e-6 m², surfaces 1e-9 m², murs 1e-7 m, via des overlays GEOS non
  robustes.
- **Correctif peu coûteux et fort pour l'article** : pour des rectangles axés dans un
  contour rectilinéaire, tout se vérifie en `fractions.Fraction` — disjonction deux à deux
  par intervalles, inclusion dans le contour, et $\sum \text{aires} = \text{aire(contour)}$,
  ce qui implique le pavage. Exact, et plus rapide que GEOS. D'ici là, écrire
  « vérification déterministe à tolérance ε déclarée ».

### 5.5 Couche `light`

- **`SimulateurExact`** est une formule fermée (facteur de lumière du jour BRE, ciel
  couvert) : θ = 65° constant, facteur d'azimut arbitraire (incompatible avec un ciel
  couvert CIE, reconnu dans le docstring), WWR constant, `baies` ignoré, aucune
  obstruction, σ constant. Il partage avec l'analytique la même façade et le même
  `facteur_secteur` ; le perceptron apprend le résidu à l'analytique. **Valider le
  gradient contre cet oracle mesure une cohérence interne, pas une grandeur physique.**
  Un facteur de lumière du jour ne peut d'ailleurs pas donner un sDA ou un ASE (il faut
  une simulation annuelle sur données climatiques). Renommer en `OracleSplitFlux`.
- **Le garde-fou $\mu - q\sigma$ ne fait rien** : σ est constant dans les trois
  substituts (`analytique.py:148-153`, `simulateur.py:182`, `base.py:225-236`), donc
  $\nabla\sigma = 0$ et `Daylight` a le même argmax que μ. La phrase du README (l.332)
  « la marge s'élargit en terrain inconnu, l'optimiseur revient de lui-même » est fausse
  pour tout le code livré. Estimer σ par ensemble de modèles ou régression quantile.
- `SubstitutAppris` lève toujours sur un `.pt` avec un message trompeur (« n'est servi
  que hors CI » alors qu'il ne l'est nulle part).

### 5.6 Scalabilité

**[mesuré]** Grilles valides, orientation 20°, sans pavage :

| Pièces | Lignes de A | Classique | Performantiel (`a_min = 0`) | Performantiel (`a_min = 11`) |
|--:|--:|--:|--:|---|
| 15 | 80 | 7,7 ms | 26,5 ms | **InvariantViole** |
| 50 | 353 | 34,5 ms | 52 ms | **InvariantViole** |
| 100 | 861 | 82 ms | 139 ms | **InvariantViole** |
| 150 | — | 185 ms | 216 ms | **InvariantViole** |

**Le vrai mur n'est pas le temps, c'est la réussite** : le mode performantiel échoue dès
que la surface minimale est serrée, parce que Frank-Wolfe fait passer des pièces sous
`a_min`. L'affirmation « tous les points intermédiaires sont valides » (`README.md:281`)
est fausse pour les surfaces. Le budget « certification » du §9 est déclaré
(`benchmarks/test_budgets.py:40`) mais jamais mesuré.

### 5.7 Extensibilité

- **Nouvel indicateur** : ≥ 7 fichiers (`types.py:343` `Literal` fermé ;
  `uq/conforme.py:29,149-152,316` sens de la borne codé par nom ;
  `certify/rapport.py:60` cas particulier ASE ; `io/json_io.py:171` ; `light/*`). La
  convention « renvoyer une valeur négative pour un indicateur à minimiser »
  (`objectif.py:65-68`) est fragile. **Il manque un registre d'indicateurs** (nom, sens,
  unité, plage).
- **Nouvelle règle réglementaire** (largeur par type, passage, hauteur, ratio vitrage/sol,
  cercle PMR) : 6-7 fichiers, et un nouveau champ booléen dans `PreuveGeometrique` casse
  le type gelé et le JSON. **La preuve devrait être un tuple de prédicats nommés.**
- **Aucun code de front de Pareto** n'existe, malgré `README.md:289-290,520`.

### 5.8 Écarts entre la documentation et le code

**`README.md`**

| Ligne | Affirmation | Réalité |
|---|---|---|
| 156-205 | `Structure.from_dxf`, `ax.referentiel`, `data.generator_outputs`, `sweep_orientation`, `Daylight(metric=, alpha=)` | N'existent pas. |
| 251 | « `3w + 3h ≥ 18` n'accepte que des plans dont la surface suffit » | **Faux** : une tangente est une approximation *extérieure*. $w = 5{,}9$, $h = 0{,}1$ la satisfait avec une aire de 0,59 m². (`docs/formules/coupes-surface.md` le dit correctement.) |
| 281 | « Tous les points intermédiaires sont valides » | Faux pour les surfaces minimales (mesuré). |
| 285 | « Le gap majore la distance à l'optimum » | Faux pour un substitut non concave. |
| 289-290, 520 | Tracé du front de Pareto | Aucun code. |
| 314 | « Les fenêtres suivent » | Les murs ne bougent jamais. |
| 332 | « La marge s'élargit en terrain inconnu » | σ constant. |
| 368 | Garantie géométrique « Peut être fausse ? Non » | Contredit par la structure et les tolérances. |
| 398-399 | « Structure conservée », « Déplacement ≤ 0,25 m » | Le premier ne vérifie rien, le second n'existe pas comme prédicat. Et le budget peut être consommé **deux fois** (`api.py:255-260`, `frank_wolfe.py:200`) : déplacement réel jusqu'à 2 × `budget`. |
| 603 / 667 | Non-Manhattan « ✅ » / « arrive au jalon 6 » | Non supporté ; contradiction interne. |

**`ARCHITECTURE.md`** : §1 « toutes les corrections valides » (faux, une cellule) ;
§2 et §12 `SimulateurExact` associé à Radiance (c'est une forme fermée) ; §3 « couches
pures » alors que `lmo` a un cache global mutable (ADR-8) ; §9 budgets « testés en CI »
sur le seul meilleur cas ; §11 arborescence périmée.

**`Project_Architecture_Blueprint.md`** : très en retard (« aucun corps de fonction
implémenté hors jalon 1 », « 99 tests », « 11 noms » dans `__init__` au lieu de 23,
`appris.py` présenté comme un transformeur, extras `[appris]` et `[ml]` en double,
ADR-7 « une violation lève `InvariantViole` » alors que le prédicat ne vérifie rien).
**À régénérer entièrement.**

**Autres** : `types.py:92-93` (« `Mur.porteur` : `geom` l'écrit dans `A_eq` ») est faux ;
chiffres de réparation incohérents entre `api.py:155-156` (93,0 % / 97,6 %) et
`resultats/j7_reparation.md` (93,9 % / 98,0 %).

---

## 6. Qualité du code

*Revue menée avec le skill `review-and-refactor` selon les règles du dépôt
(`ARCHITECTURE.md` §6, §7, §10 et `CONTRIBUTING.md`).*

### Note globale : 6,5/10

Le socle est rigoureux : types gelés, quantile conforme exact, règles de dépendance
exécutables, docstrings riches, aucun `print`, aucun TODO. Mais le chemin « performance »
est fragile, `InvariantViole` sert à tout, plusieurs modules sont peu ou pas testés, et
**aucun cas de référence n'existe**.

**Pourquoi les tests n'ont rien vu** : les 523 tests de `tests/` passent, mais
tous les tests du mode performance, les stratégies Hypothesis
(`tests/proprietes/strategies.py:205`) et les benchmarks (`CTX_15`) utilisent
`aires_min=()`. **Le cas réaliste (surfaces minimales déclarées) n'est jamais exercé**,
d'où les deux défauts critiques ci-dessous.

### Notes par module

| Module | Note | Justification |
|---|--:|---|
| `types` | 8/10 | Gelés, `Ouverture` relative avec position absolue dérivée. Manque la validation des plages (`s ∈ [0,1]`, `borne_inf ≤ valeur ≤ borne_sup`). |
| `geom` | 7/10 | `graphe` 100 %, `polytope` 96 %. `deduire_trame` : complexité cyclomatique (CC) 30 ; `rectilineaire` 69 %. |
| `lmo` | 6/10 | Bonne distinction infaisable / non borné. Démarrage à chaud perdu avec des coupes ; cache global indexé par `id()` et non protégé entre fils d'exécution. |
| `solve` | 5/10 | `frank_wolfe` : 157 lignes, CC 28 ; sortie pouvant violer `a_min` ; tolérances codées en dur ; `iterations` décalé de un (`frank_wolfe.py:353`). |
| `light` | 7/10 | `analytique` couvert à 100 %, validation des gradients. `objectif` à 58 %, `Daylight` et `SubstitutDense` mutables. |
| `orient` | 7/10 | API propre. 5 `ValueError` ; p-valeur de Rayleigh non corrigée alors que la docstring la dit anti-conservatrice (`circulaire.py:246`). |
| `uq` | 8/10 | `ceil((n+1)(1−α))` vérifié sans erreur d'arrondi pour α ∈ [0,01 ; 0,3], n ≤ 2000. Défaut piège `borner(..., incertitude=1.0)` (`conforme.py:206`) ; `nan` renvoyé en silence (`fiabilite.py:106`). |
| `active` | 6/10 | Calibration bien séparée de l'entraînement. Graines corrélées (`seed + cycle`) ; `run` CC 27 ; hyperparamètres codés en dur. |
| `export` | 5/10 | `svg.py` à 0 % ; `_ecrire_spf_minimal` 206 lignes ; `ifc.py:88` avale `ArchluxError` sans journaliser. |
| `feasibility` | 6/10 | Lisible, mais annonce « exacte » sur un domaine resserré et jette le plan témoin. |
| `certify` | 7,5/10 | `preuve` 94 %, `dual` 100 %. Tolérances incohérentes avec `geom`. |
| `bench` | 7/10 | `graines.deriver` excellent… mais `active` ne s'en sert pas. `stats` 68 %. |
| `data` | 5/10 | `_convertir` CC 36 ; **seul `except Exception` du dépôt** ; tri des erreurs par lecture du texte du message ; `corruption` et `imputation` à 0 %. |
| `io` | 8/10 | 97 %, `Any` confiné et justifié, JSON malformé → erreur typée. |
| `api` / `erreurs` | 6/10 | Hiérarchie claire, messages chiffrés. Mais `InvariantViole` levée 156 fois, y compris pour des erreurs de saisie ; `performance=None` codé en dur. |
| **tests** | 6,5/10 | 341 unitaires, 47 propriétés Hypothesis (9 %), 135 de dépendances, **0 cas de référence** (le marqueur `reference` est déclaré mais jamais utilisé) ; aucun seuil de couverture. |

### Défauts classés

**Critique**

- **Q-C1. Le mode performance produit des plans invalides puis lève `InvariantViole`**
  (`solve/frank_wolfe.py:236-307`, `api.py:305,315`). Reproduit sur le plan à 15 pièces
  du benchmark avec `aires_min ∈ {9, 10, 11}` : la légalisation classique réussit, le mode
  performance lève « surface p0_0 : 8,83 m² < 9,00 m² » (8 à 14 violations). Cause : les
  tangentes sont des relaxations de $\{wh \ge a_{min}\}$, et FW accepte le pas **avant**
  d'enrichir les coupes, sans le resserrement de bornes que fait `resoudre_avec_surfaces`.
  *Correction* : appliquer `_resserrer_bornes` au départ (domaine convexe, donc les
  combinaisons convexes restent valides), ou refuser un pas qui viole une surface ; test
  de propriété avec `aires_min` non vide.
- **Q-C2. Démarrage à chaud ignoré dès qu'une coupe existe** (`lmo/solveur.py:321`).
  Mesuré : avec `aires_min = 4`, 11 modèles GLOP construits pour 10 itérations (contre 2
  sans). C'est l'anti-pattern §10, masqué par un benchmark sans `aires_min`.
  *Correction* : garder le modèle en cache et ajouter les coupes au modèle existant ;
  budget §9 « performance avec `aires_min` ».

**Majeur**

- **Q-M1. `InvariantViole` a un sens contradictoire** : `erreurs.py:95-100` dit « bogue
  interne, jamais une entrée utilisateur invalide, jamais rattrapé », mais elle est levée
  pour `alpha hors ]0,1[` ou `n ≥ 2`, et rattrapée à 4 endroits (dont 3 en silence).
  Créer `EntreeInvalide(ArchluxError)`.
- **Q-M2. Tri des erreurs par lecture du message** (`data/chargeurs.py:595-600` :
  `if "diagonale" in motif`). Lever des sous-classes ou ajouter un attribut `code`.
- **Q-M3. `except Exception`** (`data/chargeurs.py:538`), contraire au §7 : lister les
  exceptions shapely attendues.
- **Q-M4. Erreurs avalées sans journal** (`export/ifc.py:88`, `uq/fiabilite.py:106`).
- **Q-M5. Graines corrélées** (`active/boucle.py:292,305,335`) : la campagne `seed=17`
  au cycle 1 rejoue la campagne `seed=18` au cycle 0. Utiliser
  `deriver(self.seed, f"selection/{cycle}")`. *(Cela peut suffire à fausser la
  comparaison actif / aléatoire du jalon 6.)*
- **Q-M6. Fausse infaisabilité possible** (`lmo/coupes.py:449`) — même constat que §5.2.
- **Q-M7. Modules non testés** : `export/svg.py`, `data/corruption.py`,
  `data/imputation.py` à 0 % ; ajouter `fail_under = 85` dans la config de couverture
  et en CI (`.github/workflows/ci.yml:39` n'a pas de seuil).
- **Q-M8. Aucun cas de référence** : figer 3 à 5 couples (plan, certificat) en JSON et
  les comparer octet à octet, comme le prévoit déjà le marqueur `reference`.
- **Q-M9. Fonctions trop longues ou trop ramifiées** — 21 fonctions sur 316 ont une
  CC > 10 :

| Rang | Emplacement | Fonction | CC | Lignes |
|--:|---|---|--:|--:|
| 1 | `data/chargeurs.py:518` | `_convertir` | 36 | 121 |
| 2 | `geom/pavage.py:365` | `deduire_trame` | 30 | 91 |
| 3 | `solve/frank_wolfe.py:129` | `frank_wolfe` | 28 | 157 |
| 4 | `active/boucle.py:205` | `run` | 27 | 142 |
| 5 | `geom/pavage.py:137` | `_consolider` | 20 | 42 |
| 6 | `light/validation.py:63` | `valider_gradient` | 18 | 59 |
| 7 | `lmo/solveur.py:242` | `resoudre` | 16 | 65 |
| 8 | `export/pathologie.py:34` | `diagnostiquer` | 16 | 39 |
| 9 | `api.py:115` | `legalize` | 14 | 93 |
| 10 | `export/ifc.py:121` | `_ecrire_spf_minimal` | 13 | 206 |

**Mineur**

- Docstrings NumPy incomplètes : 54 fonctions publiques sur 130 sans section
  `Parameters` (`CONTRIBUTING.md` les exige ; ruff ne le vérifie pas — ajouter
  `pydocstyle` convention numpy ou `numpydoc validate`).
- **Tolérances dispersées** : `_EPS` redéfini 7 fois (1e-8, 1e-9, 1e-12) et 20 littéraux
  en ligne ; contact à 1e-9 dans `geom/graphe.py:41` mais 1e-7 dans
  `figer_contacts` et `certify/preuve.py:61`. Créer un module unique
  `archlux/tolerances.py` — important pour une bibliothèque qui parle de « preuve ».
- Tableaux mutables sous types gelés (`Polytope.A/b/index`, `Calibration.scores`, qui peut
  changer **après** le calcul de `empreinte_jeu`).
- `borner(..., incertitude=1.0)` : rendre `incertitude` obligatoire.
- `is_feasible` jette le plan témoin quand la réponse est « faisable ».
- Accents incohérents : `erreurs.py` à moitié sans accents ; messages visibles de
  l'utilisateur sans accents (`data/chargeurs.py` : « aucune piece habitable ») ;
  `description` du `pyproject.toml` (« genere »).
- 3 `# type: ignore` (`lmo/solveur.py:106`, `types.py:381`, `uq/conforme.py:152`) ; celui de
  `conforme.py` s'évite avec `typing.get_args`.
- `structlog` : 3 appels dans tout le dépôt ; aucune journalisation dans `solve`, `api`,
  `data`, `export`. Observabilité quasi nulle.

### Points forts de la qualité

- §7 et §10 respectés : `seed` sans défaut sur les 8 fonctions qui échantillonnent,
  aucun `np.quantile` en conforme, aucune coordonnée absolue d'ouverture stockée, aucune
  mutation de `Plan`.
- CI complète : ruff, mypy strict, interrogate ≥ 95 %, doctests, `mkdocs --strict`,
  matrice 3.11-3.13, job de budgets ; test de démarrage à chaud par médianes entrelacées.
- Messages d'exception concrets et chiffrés, données transportées en attributs.

---

## 7. Types et modèle de données

*Revue menée avec le skill `python-expert`.*

### Note : 6/10

**Points solides** : 48 dataclasses sur 53 sont `frozen=True, slots=True` ;
`mypy --strict` passe ; `py.typed` est présent (PEP 561) ; `BornePerformance.indicateur`
est un `Literal` ; `Substitut` est `@runtime_checkable` ; la séparation preuve /
prédiction est inscrite dans les types.

**Points faibles et corrections**

| Gravité | Problème | Où | Correction |
|---|---|---|---|
| Majeur | Aucune validation à la construction ni à l'entrée de `legalize`. Sont acceptés sans erreur : `Piece(w=-1)`, `Piece(w=nan)`, `Piece(x="0")`, type `"sejuor"`, `Ouverture(s=2)`, `Orientation(720)`, `Orientation(nan)`, mur d'épaisseur −1, ids en double, `BornePerformance(borne_inf > borne_sup)`, `PreuveGeometrique(valide=True, chevauchement=True)`. | `src/archlux/types.py` | `__post_init__` léger (finitude, signes, plages) sur les types d'entrée ; cohérence interne sur `PreuveGeometrique` et `BornePerformance`. |
| Majeur | Tableaux mutables (`ndarray`, `dict`, `csr_matrix`) dans des types « gelés » : le gel est illusoire et `hash(plan)` plante avec `trace=True` (`TypeError: unhashable type: 'numpy.ndarray'`). | `solve/trace.py:29`, `lmo/solveur.py:68-72`, `geom/polytope.py:73-79`, `uq/conforme.py:44`, `orient/circulaire.py:51`, `feasibility/__init__.py:19` | `tuple[float, ...]` pour les types publics, ou `arr.setflags(write=False)` ; `field(compare=False, hash=False)` pour `Plan.trace`. |
| Majeur | `Piece.type` est un `str` libre : une faute de frappe supprime silencieusement l'exigence de surface minimale. | `types.py:60`, `Referentiel.a_min` l.264 | `TypePiece = Literal[...]` ou avertissement si un type est absent du référentiel. |
| Majeur | Les paquets paresseux `ax.light`, `ax.bench`, `ax.feasibility` sont typés `ModuleType` : ni mypy ni l'IDE ne voient `ax.light.Daylight`. | `__init__.py:94` | `if TYPE_CHECKING: from archlux import bench, feasibility, light`. |
| Mineur | `np.ndarray` nu partout (~170 occurrences), aucun `NDArray[np.float64]`. | tout `src/` | `VecteurF: TypeAlias = NDArray[np.float64]`. |
| Mineur | Aucun type d'unité ; `Orientation.deg` non normalisé. | `types.py` | `Metres = NewType(...)`, `Degres = NewType(...)` ; normaliser `deg % 360`. |
| Mineur | `Piece`, `Mur`, `Ouverture` acceptent les arguments positionnels : inverser `x, y, w, h` passe sans erreur. | `types.py` | `kw_only=True`. |
| Mineur | `Plan(murs=, ouvertures=)` obligatoires sans défaut ; contour à fournir deux fois (`Plan` et `Contexte`). | `types.py` | `murs=()`, `ouvertures=()` par défaut ; `Contexte.contour` optionnel, repris du plan. |
| Mineur | `Substitut.indicateur -> str` alors que `BornePerformance` utilise un `Literal`. | `light/protocole.py:127` | Alias `Indicateur = Literal["sDA", "ASE", "UDI", "vue"]` partagé. |
| Mineur | `Daylight` et `SubstitutDense` sont des dataclasses mutables sans raison documentée (`light/objectif.py:26`, `light/base.py:125` sans `slots`). | | Geler ou documenter l'exception à la règle « tous gelés ». |

---

## 8. Utilisabilité dans un cas concret

### Note : 3/10

*Test réalisé avec le skill `python-expert` : un utilisateur qui n'a lu que le README et
les tutoriels essaie de corriger un T3 de 10 × 7 m à 6 pièces (séjour, cuisine,
2 chambres, SdB, WC) avec des chevauchements de 3-4 cm, une SdB à 4,60 m² pour 5 m²
minimum, un jour de 3 cm et deux murs porteurs.*

Il a fallu **~20 lignes pour construire le plan et le contexte, et 5 tentatives** avant
un premier `legalize` qui passe.

| # | Étape | Résultat | Message ou friction |
|--:|---|---|---|
| 1 | Construire le plan | OK | `murs=`, `ouvertures=`, `contour=` obligatoires sans défaut. |
| 2a | `ax.referentiel("fr/logement-collectif")` (README) | **Échec** | `AttributeError: module 'archlux' has no attribute 'referentiel'` |
| 2b | `Structure.from_dxf(...)` (README) | **Échec** | `AttributeError: ... no attribute 'from_dxf'` |
| 2c | `Contexte` sans contour (comme le README) | **Échec** | `TypeError: missing 1 required positional argument: 'contour'` |
| 2d | `Referentiel` construit à la main | OK | Il faut connaître les types de pièce par cœur ; `largeur_min=1.80` s'applique aussi aux WC et SdB. |
| 3a | `legalize(plan, ctx)` par défaut | **Échec** | `InvariantViole: jours : aire non couverte 0,05 m²` — sans suggérer `pavage=True`. |
| 3c | `legalize(..., pavage=True)` | OK (8-14 ms) | SdB portée à 5,00 m², déplacement max 0,14 m. **Mais des pièces passent de y = 4,000 à 3,889 alors que le refend porteur est à y = 4, et le certificat affiche « Structure préservée : oui, vérifié ».** |
| 4 | `certificat.rapport()` | OK | En-tête « archlux 0.0.0 » ; section DIAGNOSTIC avec 10 lignes internes illisibles. |
| 3d | `Daylight(metric="sDA", alpha=0.10)` (README) | **Échec** | `TypeError: unexpected keyword argument 'metric'` |
| 3e | `legalize(objective=Daylight(...))` | **Échec (bogue)** | `TypeError: Daylight.evaluer() got an unexpected keyword argument 'baies'` |
| 3f | `objective=SubstitutAnalytique()`, divers budgets | **Échec** | Surfaces minimales violées (SdB 4,97 / 4,48 m²), `InvariantViole`. |
| 3g | Mode performance sur le plan jouet du tutoriel | OK | Mais `certificat.performance` vaut toujours `None` : **aucune API publique ne produit la section [PRÉDICTION]** du certificat. |
| 5a | `is_feasible` comme dans le README | **Échec** | Signature différente. |
| 5b | `is_feasible` sur 80 m² demandés dans 70 m² | OK | Conflit bien nommé, mais pas de déficit chiffré (contrairement au README). |
| 5c | `is_feasible` sur le T3 faisable | **Échec** | Lève `InvariantViole` au lieu de rendre un `Verdict`. |
| 6 | Export DXF / IFC / SVG | Partiel | `export` absent de l'API publique ; `to_dxf(q, "a.dxf")` refuse un `str` (`'str' object has no attribute 'write_text'`) ; avec un `Path` : OK. |
| 7 | Aller-retour JSON | OK | Égalité stricte conservée, certificat compris. |
| — | Bruit | — | OR-Tools écrit des dizaines de lignes `MPSOLVER_ABNORMAL` sur stderr dans les cas infaisables. |

### Ce qui manque pour un usage réel en bureau d'études

1. **Une entrée CAO.** Le seul format d'entrée est le JSON maison. Il faut au minimum
   `Plan.from_dxf(chemin, calque_pieces=...)` et `Structure.from_dxf(...)` ; idéalement
   une lecture IFC.
2. **Une ligne de commande.** Pas de `[project.scripts]`. Proposé :
   `archlux legalize plan.json --pavage -o corrige.json --svg corrige.svg`.
3. **Des exemples livrés.** Aucun JSON d'exemple dans le dépôt (`tests/references/` ne
   contient que `README.md` et `__init__.py`). Ajouter `examples/` avec 3 plans.
4. **Des référentiels réglementaires fournis** (au moins un préréglage français
   logement collectif), avec des minima par type de pièce.
5. **Des murs porteurs réellement respectés** (correction n°1).
6. **Un certificat lisible par un architecte** (diagnostic dual filtré et traduit en m²
   et en points d'indicateur, pas en noms de variables).
7. **Un indicateur de lumière qui prédit quelque chose.** Aujourd'hui le substitut
   analytique est battu par l'aire au sol seule (`resultats/j7_sd_par_piece.md`), donc
   le mode « préserver la lumière » optimise un signal non prédictif.

### Ce que les résultats disent de l'usage réel

| Régime | Taux de réussite | Source |
|---|---|---|
| Plans réels MSD légèrement corrompus, `pavage=True` + repli | **93,9 %** [93,2–94,5] | `resultats/j7_reparation.md` |
| Plans réels MSD déjà valides (idempotence) | 400/400, déplacement médian 0 m | `resultats/j7_msd_idempotence.md` |
| Sorties réelles de HouseDiffusion, `legalize` seul | **0 %** | `resultats/j8_generation.md` |
| Sorties réelles de HouseDiffusion, `pavage=True`, budget 16 | **18 à 23 %**, déplacement médian **38-43 % du côté du plan** | idem |

**Lecture** : l'outil est utile pour **vérifier** un plan dessiné par un humain et pour
**réparer de petites erreurs de cote** ; il n'est pas encore utile pour « corriger la
sortie d'un générateur », qui est pourtant le cas d'usage annoncé en tête du README.
Il faut le dire dans le premier paragraphe du README, pas seulement dans `limites.md`.

---

## 9. Notes par fonctionnalité

| Fonctionnalité | Note | Justification |
|---|--:|---|
| **Légalisation classique** (`legalize`) | **6/10** | Rapide (13 ms), 93,9 % sur plans corrompus avec `pavage=True`, idempotente. Mais échoue par défaut sans `pavage=True`, ne respecte pas les porteurs, et ne répare que ~20 % des sorties de générateur. |
| **Contrainte de pavage** (`pavage=True`) | **7,5/10** | Vraie contribution : la condition est combinatoire, donc un jour cesse d'être représentable. Passe de 0 % à ~20 % sur générateur, de 36 % à 94 % sur corruptions. `deduire_trame` est trop complexe (29 branches). |
| **Légalisation performantielle** (Frank-Wolfe) | **4/10** | Les itérés restent valides et l'objectif est monotone (propriétés testées). Mais `Daylight` plante, les surfaces minimales sautent sur un T3 réaliste, et l'objectif « somme sur les pièces » pousse à concentrer l'aire dans une pièce et écraser les autres (`resultats/orientation/`, pièces à 0,7 m²). |
| **Détection d'infaisabilité** (Farkas) | **6,5/10** | Le certificat de Farkas est creux et nomme le conflit minimal (2-3 lignes sur 45) : excellent. Mais `is_feasible` lance un `legalize` complet, laisse s'échapper `InvariantViole` et ne chiffre pas le déficit annoncé dans le README. |
| **Vérification seule** (`certify.preuve`) | **5/10** | Chevauchement, jours, surfaces : bien. Structure porteuse : vérification tautologique (correction n°1). Sur un projet dont la promesse est « prouvé », c'est rédhibitoire tant que ce n'est pas corrigé. |
| **Certificat** (`certify.rapport`) | **5,5/10** | Séparation typographique exact / probabiliste réussie. Mais version fausse (0.0.0), diagnostic dual illisible, section PRÉDICTION jamais remplie par l'API publique. |
| **Diagnostic dual** | **5/10** | Idée forte (« ce qui vous coûte de la lumière »). En pratique affiche des variables d'écart internes et pas d'unités métier. |
| **Substitut analytique** | **3/10** | Code propre et couvert à 100 %, mais mesuré contre 4 239 pièces réelles : rang de Spearman +0,085 une fois normalisé par l'aire ; battu par l'aire seule ; le signe s'inverse sur des sites disjoints. |
| **Simulateur « exact »** (split-flux BRE) | **4/10** | Utile comme oracle déterministe de CI. Le nom « exact » et l'expression « vérité terrain » sont trompeurs : c'est une forme fermée, pas une mesure ni une simulation par lancer de rayons. |
| **Substitut appris** | **2/10** | Le transformeur n'existe pas (`SubstitutAppris` refuse les `.pt`). Le perceptron apprend le résidu entre deux formules connues sur 90 pavages 2×2 : l'« accord de signe = 1,000 » du jalon 4 n'a donc pas de portée physique. Sur Swiss Dwellings : R² = −0,22 à −0,56. |
| **Prédiction conforme** (`uq`) | **7/10** | Mathématiquement correcte, couverture mesurée conforme (90,2 %). Mais largeur d'intervalle 1,53 pour une cible d'écart-type 0,39 : **la borne est plus large que la variabilité du phénomène**, donc vide d'information. `splits/v1` : n = 18 en calibration. |
| **Détection de dérive** (`uq.derive`) | **6,5/10** | Afficher `NON EVALUABLE` plutôt qu'un intervalle trompeur est la bonne attitude. Reste à la valider sous sélection par l'optimiseur. |
| **Statistiques circulaires** (`orient`) | **7,5/10** | Encodage harmonique, moyenne circulaire, Rayleigh : corrects. Trois conventions de secteurs divergentes dans le projet (§4 M3). |
| **Apprentissage actif** (`active`) | **3/10** | Mesuré : l'actif perd contre l'aléatoire (gagne 4 graines sur 10, gain moyen −1,42). Le code est là, la méthode ne fonctionne pas encore ; `Loop.run` fait 180 lignes. |
| **Pièces rectilinéaires / en L** (`geom.rectilineaire`) | **5/10** | Décomposition + fusions en égalités : bon principe. Couverture 69 % ; 143 pièces obliques et 240 contours non simples rejetés sur MSD (32 % seulement des appartements retenus). |
| **Export DXF / IFC / SVG** | **5,5/10** | Fonctionne, sans dépendance lourde pour le SVG. `export` n'est pas public, refuse les `str`, SVG couvert à 0 %, IFC « SPF minimal » : survie de 80 % [67–89] sur 50 plans, et non testé dans un vrai logiciel BIM. |
| **Chargeurs de corpus** (`data`) | **6/10** | Jointure MSD × Swiss Dwellings (18 263 / 18 270 appartements) : gros travail utile. Mais module de 845 lignes, `corruption.py` couvert à 0 %, `imputation.py` mort. |
| **Banc d'essai** (`bench`) | **7/10** | Bootstrap apparié, Holm, TOST, puissance, graines dérivées, manifestes : très bon niveau méthodologique. `bench.stats` couvert à 68 %. |
| **Sérialisation JSON** (`io`) | **8/10** | Aller-retour exact, certificat compris, couverture 98 %. Manque un schéma JSON publié et versionné utilisable hors Python. |
| **Performance** | **9/10** | Tous les budgets tenus avec 2 à 15 fois de marge. Seul point noir : 3,1 s d'import. |

---

## 10. Notes par tâche demandée (jalons)

Les tâches que vous avez demandées correspondent aux jalons des spécifications
(`docs/specification/MILESTONE-*.md`) et aux expériences qui ont suivi (jalons 7 à 9 dans
`experiences/` et `resultats/`). Chaque jalon reçoit deux notes : **l'exécution** (le
travail a-t-il été bien fait ?) et **le critère d'acceptation** (le livrable promis
est-il atteint ?).

| Jalon | Demande | Exécution | Critère atteint | Commentaire |
|---|---|--:|--:|---|
| **J1** | Types + aller-retour JSON | **8/10** | **8/10** | Aller-retour exact, types gelés. Manque la validation des entrées et un schéma publié. |
| **J2** | Légalisation géométrique classique + preuve | **7/10** | **5/10** | Le test Hypothesis passe, l'idempotence sur MSD est parfaite. Mais le défaut de structure porteuse invalide la « preuve » sur un point ; la baseline demandée (« 3 modèles génératifs publics ») se réduit dans `j2_brut.csv` à **2 plans construits à la main**. |
| **J3** | Légalisation performantielle sans apprentissage | **7/10** | **6/10** | Les trois tests d'acceptation (itérés valides, objectif monotone, orientation circulaire) passent. Mais le mode échoue sur un T3 réaliste et `Daylight` plante. |
| **J4** | Substitut appris + validation du gradient | **4/10** | **2/10** | Transformeur non implémenté ; perceptron entraîné sur le résidu de deux formules fermées ; l'accord de signe 1,000 est mesuré contre l'oracle synthétique, pas contre une simulation physique. Le « point de contrôle » du jalon a été franchi sur un critère qui ne pouvait pas échouer. |
| **J5** | Garanties de performance + certificat complet | **7/10** | **4/10** | La mécanique conforme est juste et la couverture est mesurée. Mais la borne est vide d'information (largeur > variabilité), porte sur un oracle gelé et non sur un éclairement, et la section PRÉDICTION n'est jamais produite par l'API publique. |
| **J6** | Consolidation v1.0 (non-Manhattan, actif, IFC, doc) | **6/10** | **3/10** | Beaucoup de choses livrées, documentation MkDocs riche. Mais le critère d'acceptation « un utilisateur externe réussit en 10 minutes » échoue dès la première ligne du README ; pas de `LICENSE`, pas de dépôt public ni d'historique ; l'actif perd contre l'aléatoire — mais la comparaison est elle-même suspecte, car les graines de sélection et d'entraînement sont corrélées (`seed + cycle`, §6 Q-M5) : à refaire avant de conclure. |
| **J7** | Corpus réel (MSD, Swiss Dwellings) | **9/10** | **8/10** | Le meilleur jalon : 4 796 corruptions, 93,9 % [93,2–94,5], décomposition de la variance sur 367 466 pièces, découpage par site, résultat négatif honnête sur le substitut. Seule réserve : 32 % des appartements MSD retenus. |
| **J8** | Légalisation de plans réellement générés | **9/10** | **4/10** | Protocole exemplaire (HouseDiffusion, 1 000 pas justifiés, 740 plans, 3 conditionnements, frontière de licence GPL respectée). Mais le résultat est que la méthode ne répare que ~20 % des plans en les déplaçant de ~40 %. L'exécution est excellente, la méthode n'est pas encore prête pour ce cas d'usage. |
| **J9** | Variantes selon l'orientation du soleil | **6/10** | **4/10** | Toutes les variantes sont certifiées valides, et la docstring dit honnêtement ce que le jalon ne montre pas. Mais l'objectif optimisé ne prédit pas la lumière, et il produit des pièces dégénérées (côtés de 0,50 m, pièces de 0,7 m²). |
| — | Explication des formules (échange précédent) | — | — | Faite en conversation ; `docs/formules/` couvre déjà 21 fiches. |

**Moyenne exécution : 7,3/10. Moyenne critères atteints : 4,9/10.** Le travail est bien
fait ; ce sont les **objectifs annoncés** qui sont en avance sur la réalité. Pour la
suite, il vaut mieux réviser les promesses que forcer les résultats.

---

## 11. Publication open source

### Note de préparation : 4/10

### Bloquant (à faire avant tout `git push` public)

- [ ] **Ajouter `LICENSE`** (texte officiel Apache-2.0). Sans lui, le code n'est pas
      réutilisable légalement.
- [ ] **`git init`** et premier commit. Vérifier `.gitignore` avant : il ignore `site/` et
      `donnees/`, mais pas `.hypothesis/`, `.benchmarks/`, `session_memory.json`,
      `resultats/_tmp_ifc/` (fichiers IFC temporaires), et `.mypy_cache` (153 Mo) n'est
      ignoré que par sa ligne dédiée — à vérifier.
- [ ] **Retirer les fichiers d'outillage personnel** de la racine ou les documenter :
      `session_memory.json` (contient des traces de sessions d'agent), `skills-lock.json`,
      `.claude/`, `.cursor/`, `.agents/`, `AGENTS.md`, `CLAUDE.md`. Les garder est possible
      (c'est un choix assumé de développement assisté), mais alors le dire dans
      `CONTRIBUTING.md` ; sinon les exclure.
- [ ] **Remplacer tous les `ORG/archlux`** (README, `CITATION.cff`, `docs/contribution.md`)
      et le DOI `XXXXXXX`.
- [ ] **Renseigner de vrais auteurs** dans `CITATION.cff` et `pyproject.toml`
      (aujourd'hui « archlux contributors » / « archlux ») avec nom, affiliation et ORCID.
      Une citation sans auteur n'est pas citable.
- [ ] **Réécrire le « Démarrage rapide » du README** avec du code qui s'exécute, et le
      tester automatiquement (un test qui extrait et exécute les blocs de code du README,
      ou `pytest --doctest-glob="README.md"`).
- [ ] **Corriger le certificat de structure porteuse** (§3 n°1) ou le marquer
      « NON VÉRIFIÉ ».

### Important (avant d'annoncer le projet)

- [ ] **Revenir à une version 0.x** (par exemple `0.9.0`). Une 1.0.0 promet une API
      stable et utilisable ; or le README est faux et le mode performance est cassé.
      Semver autorise tout en 0.x : c'est plus honnête et vous garde la liberté de
      corriger `legalize` (fusion `pavage`/`budget_reparation`, validation) sans
      version 2.0.
- [ ] **Clarifier la langue** : un projet open source international a intérêt à avoir au
      moins un README et une API en anglais. Le mélange actuel (`legalize` et
      `verifier_exactement`) est le pire des deux mondes. Options : API anglaise +
      documentation bilingue, ou API française assumée et documentée comme telle.
- [ ] **Ajouter `examples/`** avec 3 plans JSON et un script de 20 lignes.
- [ ] **Ajouter une CLI** (`[project.scripts]`).
- [ ] **Imposer `ruff format`** en CI (78 fichiers non formatés aujourd'hui) et ajouter
      un `pre-commit`.
- [ ] **Publier le schéma JSON** du format d'entrée (`docs/reference/schema-json.md`
      existe : l'exporter en fichier `.schema.json` versionné).
- [ ] **Fichiers communautaires GitHub** : `CODE_OF_CONDUCT.md`, `SECURITY.md`, modèles
      d'issue et de PR (`.github/ISSUE_TEMPLATE/`), `CODEOWNERS`.
- [ ] **CI** : ajouter un job qui installe le paquet depuis le wheel construit (pas en
      éditable) et exécute les exemples ; ajouter Windows et macOS à la matrice ;
      corriger `benchmarks/test_budgets.py` pour tolérer `--benchmark-disable`.
- [ ] **Publication PyPI** via Trusted Publishing ; vérifier que le nom `archlux` est
      libre sur PyPI.
- [ ] **Archivage Zenodo** relié à GitHub pour obtenir le DOI automatiquement à chaque
      release.
- [ ] **Déclarer la frontière de licence** avec HouseDiffusion (GPL v3, non commercial) en
      tête du README : le choix fait (échange par JSONL, aucun import) est le bon, il faut
      le rendre visible.
- [ ] **Données** : documenter précisément quelles données ne sont pas redistribuables
      (étiquettes Swiss Dwellings) et fournir le script qui les reconstruit.

### Souhaitable

- [ ] Réduire le temps d'import (3,1 s) : imports paresseux de scipy.stats et networkx.
- [ ] Faire taire OR-Tools sur stderr (`solver.SuppressOutput()`).
- [ ] Badge de couverture réelle (84 %), pas un chiffre écrit à la main.
- [ ] Un notebook « 10 minutes avec archlux » exécuté en CI.

---

## 12. Rédaction d'un article

### Note de préparation : 5/10

`docs/publication-1.0.md` fait déjà un diagnostic lucide : les jalons 1-6 démontrent
une **architecture**, pas un **résultat expérimental**. Depuis, les jalons 7-8 ont
apporté de vraies mesures sur corpus réel et générateur réel — ce qui change la nature
de l'article possible.

### Quel article écrire (recommandation)

L'article « notre méthode améliore la lumière naturelle des plans générés » **n'est pas
défendable aujourd'hui** : aucune grandeur physique n'est prédite (R² ≤ 0 sur Swiss
Dwellings), et l'objectif optimisé est battu par l'aire au sol.

Trois articles **sont** défendables avec les données existantes :

| Option | Venue possible | Contenu | Forces |
|---|---|---|---|
| **A. Article outil** | JOSS (Journal of Open Source Software), SoftwareX | Le logiciel : légalisation exacte + certificat séparant preuve et borne. | Court, rapide, valorise l'ingénierie. Exige un dépôt public avec historique et au moins un usage tiers. |
| **B. Article « la légalisation a posteriori ne suffit pas »** | Atelier de conférence (CVPR/ICCV workshop, CAADRIA, eCAADe, SimAUD) | J7 + J8 : 93,9 % sur corruptions contre ~20 % sur sorties réelles de HouseDiffusion ; la condition de pavage est nécessaire mais pas suffisante ; le taux dépend de la taille de la trame en (2n−1)². | **Le résultat le plus solide et le plus original du dépôt.** Message clair et utile à la communauté des générateurs. |
| **C. Article « granularité des substituts d'éclairement »** | Building Simulation, Journal of Building Performance Simulation, SimAUD | Décomposition de la variance sur 367 466 pièces : 92 % intra-appartement ; conséquence : un substitut par logement ne peut pas prédire un sDA. | Résultat négatif rigoureux, chiffré, avec une recommandation constructive. |

**Recommandation : B d'abord** (le résultat est prêt), puis A une fois le dépôt public
depuis quelques mois, et C comme article court ou section de B.

### Ce qui manque pour chaque article

**Commun à tous**

- [ ] **Comparaison à l'état de l'art** : aucune aujourd'hui. Au minimum : légalisation
      L1 classique sans pavage (déjà faite), un post-traitement de type « snapping » par
      grille, et une méthode publiée de réparation de plans (à identifier dans la
      littérature : légalisation de placements en CAO de circuits, méthodes de
      raffinement de HouseDiffusion/MSD).
- [ ] **Au moins deux générateurs publics** et non un seul (HouseDiffusion seul ne permet
      pas de généraliser). Candidats : House-GAN++, les baselines de MSD, un modèle de
      langage produisant des boîtes.
- [ ] **Graphes de conditionnement du jeu de test RPLAN**, ou justification explicite du
      conditionnement synthétique (déjà bien fait dans `j8_generation.md`).
- [ ] **Métriques de ressemblance** au plan généré au-delà du déplacement max : IoU par
      pièce, préservation du graphe d'adjacence, préservation du programme. Aujourd'hui
      « 43 % du côté » dit que c'est loin, pas en quoi c'est différent.
- [ ] **Figures** : les fiches avant/après de `resultats/visuels/` sont une excellente
      base ; il faut une figure-synthèse (taux vs nombre de pièces, avec IC).
- [ ] **Statistiques** : garder les IC de Wilson et le bootstrap apparié ; ajouter les
      tailles d'effet ; pré-enregistrer (même informellement) les analyses avant de
      relancer.

**Pour l'option A (outil)**

- [ ] Tous les points bloquants du §11.
- [ ] Un usage tiers documenté (un autre laboratoire, un étudiant, un bureau d'études).
- [ ] `paper.md` au format JOSS (≤ 1 000 mots), « Statement of need » clair.

**Pour l'option C (éclairement)**

- [ ] Un substitut **par pièce** (vecteur) et Frank-Wolfe sur une scalarisation explicite :
      c'est la conclusion de `j7_variance.md`, il faut la tester, au moins une fois.
- [ ] Une vraie cible d'éclairement (sDA / DF par Radiance ou Honeybee) sur un échantillon,
      même petit (quelques centaines de plans), pour valider l'oracle.
- [ ] Ne plus appeler `SimulateurExact` « vérité terrain » ni « exact » dans l'article :
      c'est une forme fermée. Le renommer (par exemple `OracleFormeFermee`) éviterait la
      remarque d'un relecteur.

### Points de vigilance pour un relecteur

1. **Frank-Wolfe et le gap de dualité** : le gap ne majore l'écart à l'optimum que pour un
   objectif concave (en maximisation). **Aucun substitut livré ne l'est**, pas même
   l'analytique (voir §5.1). La phrase du README « on sait de combien on rate
   l'optimum » doit être restreinte au cas concave ; pour un objectif non concave, le gap
   est seulement un critère de stationnarité.
   **Coupes tangentes** : le README (l.251) dit que `3w + 3h ≥ 18` « n'accepte que des
   plans dont la surface suffit ». C'est faux (approximation extérieure : w = 5,9,
   h = 0,1 passe avec 0,59 m²). Un relecteur mathématicien le verra immédiatement.
   **Optimum relatif à l'ordre** : parler de « plan valide le plus proche » et
   d'« infaisabilité prouvée » **pour l'ordre relatif fixé**, pas dans l'absolu
   (§5.2).
2. **Conformal sous sélection** : la garantie 1−α suppose l'échangeabilité ; un plan choisi
   par l'optimiseur pour maximiser la prédiction n'est pas échangeable avec le jeu de
   calibration. C'est reconnu dans `limites.md` ; un relecteur attendra soit une
   correction (conformal pondéré, *conformal under covariate shift*), soit une mesure
   empirique de la couverture **après** optimisation.
3. **« Preuve exacte »** : la vérification est faite en flottants avec tolérance. Préciser
   « exacte à la tolérance ε près » ou passer à une vérification en arithmétique
   rationnelle (`fractions.Fraction`) sur le plan final — c'est bon marché pour 15 pièces
   et rendrait le mot « preuve » inattaquable.
4. **Nombre de degrés de liberté du jalon 4** : 90 pavages 2×2 à deux degrés de liberté ne
   permettent aucune conclusion sur un réseau ; ne pas le présenter comme un résultat.
5. **Le résumé de `CITATION.cff`** est déjà honnête (« la borne vaut pour l'oracle gelé
   employé, pas pour un sDA LM-83 ») : garder ce ton dans l'article.

### Plan d'article proposé (option B)

1. Introduction — les générateurs produisent des plans invalides ; la légalisation a
   posteriori est la réponse implicite du domaine.
2. Méthode — polytope de séparation, condition de pavage combinatoire, réparation bornée
   de la trame, certificat exact et certificat de Farkas.
3. Protocole — MSD corrompu (faute connue) contre HouseDiffusion (faute réelle) ;
   découpages, graines, IC.
4. Résultats — 93,9 % contre ~20 % ; effet de la taille de trame ; effet du plancher de
   largeur (le piège des pièces annihilées à 60 %) ; infaisabilités certifiées.
5. Discussion — la contrainte doit vivre dans le générateur ; recommandations aux auteurs
   de générateurs.
6. Limites — un seul générateur, conditionnement synthétique, rectangles uniquement.

---

## 13. Plan d'action proposé

Ordre conseillé ; chaque étape est petite et vérifiable.

| Étape | Contenu | Effort indicatif | Skill / agent du projet |
|--:|---|---|---|
| 1 | `LICENSE`, `git init`, `.gitignore`, retrait des fichiers personnels, version 0.9.0 | ½ jour | — |
| 2 | Corriger ou marquer « NON VÉRIFIÉE » la structure porteuse (test d'abord) | 1-3 jours | `tdd` → `python-expert` |
| 3 | Corriger `Daylight` (argument `baies`) + test d'intégration `legalize(objective=Daylight)` | ½ jour | `tdd` |
| 4 | README « Démarrage rapide » exécutable et testé ; `examples/` | 1 jour | `python-expert` |
| 5 | Validation des entrées de `legalize` ; messages d'erreur qui guident (`pavage=True`) | 1 jour | `tdd` → `python-expert` |
| 6 | Imports paresseux (`light`, `certify`) + test dynamique des dépendances | 1 jour | `python-design-patterns` → `tdd` |
| 7 | Repli du mode performantiel sur le plan classique ; section PRÉDICTION produite | 1-2 jours | `tdd` |
| 8 | Refactors structurels M1-M12 (planifiés en micro-commits) | 1-2 semaines | `request-refactor-plan` → `review-and-refactor` |
| 9 | CLI + `Plan.from_dxf` / `Structure.from_dxf` | 3-5 jours | `python-design-patterns` → `tdd` |
| 10 | Publication GitHub + PyPI + Zenodo | ½ jour | — |
| 11 | Article B : second générateur, métriques de ressemblance, figure-synthèse | 3-6 semaines | — |
| 12 | Substitut par pièce + validation Radiance sur un échantillon (article C) | 1-3 mois | `python-design-patterns` → `tdd` |

---

*Fin de l'audit.*
