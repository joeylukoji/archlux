# Blueprint d'architecture — archlux

> Document dérivé. `ARCHITECTURE.md` fait autorité ; ce blueprint le **détaille** et ne
> le contredit jamais. En cas de divergence, `ARCHITECTURE.md` gagne.
>
> Portée : structure des fichiers, contrats de chaque module, flux de données, points
> d'extension, et mécanismes qui rendent les règles exécutables plutôt que déclaratives.

---

## 1. La décision structurante

Tout le reste de ce document découle d'une seule décision :

> **La géométrie est exacte. La lumière est probabiliste. Les deux ne se mélangent
> jamais — ni dans un type, ni dans un module, ni dans un message.**

Cette séparation n'est pas une convention de nommage : elle est **matérialisée** par
quatre mécanismes indépendants, chacun capable d'attraper la faute seul.

| Mécanisme | Où | Ce qu'il attrape |
|---|---|---|
| Types disjoints | `PreuveGeometrique` / `BornePerformance` | Une probabilité glissée dans une preuve |
| Test d'invariant | `tests/proprietes/test_invariants_types.py` | L'ajout d'un champ probabiliste à la preuve |
| Section `Guarantees` | Toute docstring rendant un `Plan` ou `Certificat` | Une garantie affirmée sans sa nature |
| Rendu séparé | `certify/rapport.py` | Un score composite agrégeant les deux |

Un seul mécanisme suffirait à documenter la règle. Quatre sont nécessaires pour qu'elle
survive à dix-huit mois de développement.

---

## 2. Arborescence réelle

Conforme à `ARCHITECTURE.md` §11, avec les ajouts signalés en gras et justifiés au §7.

```
archlux/
├── pyproject.toml               # noyau sans torch ; torch dans l'extra [appris]
├── mkdocs.yml                   # nav figée : la doc a une structure, pas un tas
├── README.md · CHANGELOG.md
├── AGENTS.md · CLAUDE.md        # routage des agents — restent à la racine (découverte)
├── .github/workflows/ci.yml     # 3 jobs : qualité · tests · budgets
│
├── docs/specification/          # les documents contraignants, publiés avec le site
│   ├── ARCHITECTURE.md          #   fait autorité
│   ├── Project_Architecture_Blueprint.md
│   ├── DOCUMENTATION.md
│   ├── MILESTONE-2.md
│   ├── MILESTONE-3.md … MILESTONE-6.md
│
├── src/archlux/
│   ├── __init__.py              # interface publique UNIQUEMENT (11 noms)
│   ├── py.typed
│   ├── types.py                 # modèle de données gelé — dépend de rien
│   ├── erreurs.py               # ★ exceptions typées — dépend de rien
│   ├── api.py                   # legalize() + gradient_distance()
│   │
│   ├── geom/                    # [1] PUR
│   │   ├── graphe.py            #     ordre relatif → DAG, réduction transitive
│   │   └── polytope.py          #     DAG → (A, b, A_eq, b_eq, bornes, index, origines)
│   │
│   ├── lmo/                     # [2a] PUR — ignore l'origine de c
│   │   ├── solveur.py           #      min <c,x> ; warm start, duaux, Farkas
│   │   └── coupes.py            #      tangentes de surface (wh ≥ a)
│   │
│   ├── light/                   # [2b] SEULE COUCHE APPRISE
│   │   ├── protocole.py         #      Protocol Substitut — 3 méthodes
│   │   ├── analytique.py        #      formes fermées, sans apprentissage
│   │   ├── appris.py            #      transformeur — seul fichier autorisé à voir torch
│   │   └── validation.py        #      valider_gradient() — obligatoire avant usage
│   │
│   ├── solve/                   # [3] PUR
│   │   ├── frank_wolfe.py       #     away-steps, warm start, gap certifié
│   │   └── trace.py             #     trace gelée = donnée de sortie, pas du log
│   │
│   ├── orient/circulaire.py     # encodage (cos θ, sin θ) + statistiques circulaires
│   │
│   ├── uq/                      # quantification d'incertitude
│   │   ├── conforme.py          #     quantile ceil((n+1)(1−α))/n
│   │   ├── gestion.py           #     ★ jeton d'accès au jeu de calibration
│   │   └── derive.py            #     contrôle d'échangeabilité
│   │
│   ├── certify/                 # [4] PUR
│   │   ├── preuve.py            #     vérification EXACTE, indépendante du solveur
│   │   ├── borne.py             #     assemblage de la garantie probabiliste
│   │   ├── dual.py              #     prix duaux → langage d'architecte
│   │   └── rapport.py           #     rendu, deux sections séparées
│   │
│   ├── bench/                   # feuille de l'arbre : personne ne l'importe
│   │   ├── protocole.py         #     ★ découpage 60/20/20 figé
│   │   ├── manifeste.py         #     ★ manifeste de reproductibilité
│   │   └── graines.py           #     ★ dérivation déterministe de graines
│   │
│   └── io/json_io.py            # schéma JSON versionné, sérialisation déterministe
│
├── tests/
│   ├── conftest.py              # graine unique, jamais implicite
│   ├── test_dependances.py      # ★★ les règles de dépendance sont exécutables
│   ├── unites/
│   ├── proprietes/
│   │   ├── strategies.py        #     stratégies Hypothesis partagées par tous les jalons
│   │   ├── test_invariants_types.py
│   │   └── test_acceptation_jalon2.py
│   └── references/              # certificats gelés, comparés octet à octet
│
├── benchmarks/test_budgets.py   # les budgets §9 sont des contrats, pas des mesures
├── experiences/                 # scripts jetables, < 50 lignes, API publique seulement
├── resultats/                   # bruts, avant toute agrégation
└── docs/                        # galerie → tutoriels → concepts → référence
```

★ = ajout au §11 d'`ARCHITECTURE.md`, justifié au §7 de ce document.

---

## 3. Flux de données

### 3.1 Légalisation classique — `objective=None`

```
Plan proposé ─┬─► deduire_ordre ──► OrdreRelatif
              │                          │
Contexte ─────┼──────────────────────────┼─► construire_polytope ──► Polytope
              │                          │        (A, b, index, origines)
              │                          ▼
              │                   gradient_distance(x̂) ──► c
              │                          │
              │                          ▼
              │                   lmo.resoudre(poly, c, duaux=True)
              │                          │
              │            infaisable ───┴──► raise Infaisable(farkas, origines)
              │                          │
              │                       optimal
              │                          ▼
              │                   devectoriser ──► Plan candidat
              ▼                                        │
        certify.verify_exactly  ◄─────────────────┘
                    │
        invalide ───┴──► raise InvariantViole    (bogue interne, jamais silencieux)
                    │
                 valide
                    ▼
        Plan + Certificat(geometrie=preuve, performance=None, duaux=traduits)
```

**Le point non négociable** est la boucle de retour vers `verify_exactly` : la
sortie du solveur n'est jamais rendue à l'utilisateur sans avoir été revérifiée par une
implémentation **séparée et naïve**. Si GLOP a un bug, c'est cette vérification qui
l'attrape — et elle lève, elle ne corrige pas.

### 3.2 Légalisation performantielle — `objective=Substitut`

Le flux est **le même**, avec une boucle autour de l'oracle :

```
Plan légalisé classiquement ──► x₀
        │
        ▼
   ┌──► substitut.gradient(x_k, orientation) ──► c = −∇
   │         │
   │         ▼
   │    lmo.resoudre(poly, c, depart=x_k)   ← MÊME solveur, MÊME polytope
   │         │
   │         ▼
   │    pas + away-step ──► x_{k+1}, gap
   └─────────┤
             │ gap < tol ou k = max_iter
             ▼
        certify.verify_exactly  (identique)  +  uq.borner  (nouveau)
             │
             ▼
   Plan + Certificat(geometrie=preuve EXACTE, performance=borne PROBABILISTE)
```

Ce que ce diagramme démontre : **`lmo` n'a pas changé d'une ligne** entre les deux modes.
C'est la propriété que le test `test_lmo_n_importe_jamais_light` protège.

---

## 4. Contrats par module

Un module a un contrat en trois parties : ce qu'il **rend**, ce qu'il **garantit**, ce
qu'il lui est **interdit** de savoir.

| Module | Rend | Garantit | Ne doit pas savoir |
|---|---|---|---|
| `types` | Structures gelées | Immuabilité, position d'ouverture dérivée | Tout le reste |
| `erreurs` | Exceptions typées | Aucune `Exception` nue dans le projet | Tout le reste |
| `geom.graphe` | `GrapheContraintes` | Acyclique ; toute paire séparée | Dimensions, coûts |
| `geom.polytope` | `Polytope` | Tout point ⇒ plan sans chevauchement ni jour | Objectifs |
| `lmo.solveur` | `SolutionLP` | Optimalité LP, ou Farkas si infaisable | **L'origine de `c`** |
| `lmo.coupes` | `Coupe` | Aucun point admissible exclu (convexité) | La lumière |
| `light.protocole` | *(interface)* | Trois méthodes, entrée vectorielle | `geom`, `lmo`, `solve` |
| `light.appris` | valeur, ∇, σ | Rien en soi — la garantie vient de `uq` | La géométrie |
| `solve` | `FrankWolfeResult` | Validité à chaque itéré ; gap certifié | L'implémentation du substitut |
| `orient` | Encodages, statistiques | Continuité en 0°/360° | Le reste du plan |
| `uq.conforme` | `BornePerformance` | Couverture ≥ 1−α **sous échangeabilité** | La géométrie |
| `certify.proof` | `PreuveGeometrique` | Exactitude par inspection finie | Toute probabilité |
| `certify.dual` | `(libellé, coût)` | Traduction fidèle via `origines` | — |
| `bench` | Découpages, manifestes | Reproductibilité | — |

### Les trois « ignorances délibérées »

Ces trois lignes du tableau ne sont pas des omissions ; ce sont les **choix de conception
qui portent le projet**, et chacune est gardée par un test dédié.

1. **`lmo` ignore l'origine de `c`.** Un seul solveur sert aux deux modes. Lui apprendre
   la lumière détruit cette réutilisation et fait du mode performantiel un second système
   à maintenir en parallèle.
2. **`solve` ignore quelle implémentation de `Substitut` il manipule.** C'est ce qui
   permet de faire tourner la chaîne complète au jalon 3, avec des formules fermées,
   **avant d'avoir dépensé un euro de simulation**. Si l'architecture est fausse, elle est
   fausse à ce moment-là.
3. **`light` ignore la géométrie.** Il ne voit qu'un vecteur et un azimut. C'est ce qui
   confine `torch` à un seul fichier et rend `import archlux` léger.

---

## 5. Comment les règles sont rendues exécutables

Une règle d'architecture écrite dans un fichier Markdown a une demi-vie de six mois.
Chacune des règles contraignantes est donc doublée d'un mécanisme automatique.

| Règle (`ARCHITECTURE.md`) | Mécanisme | Fichier |
|---|---|---|
| §5 — couches et dépendances | Analyse AST des imports, un test par module | `tests/test_dependances.py` |
| §5 — noyau sans `torch` | Sous-processus + inspection de `sys.modules` | idem |
| §5 — `lmo` ⇏ `light` | Test dédié | idem |
| §5 — `solve` ⇒ `light.protocole` seul | Test dédié (l'implémentation est refusée) | idem |
| §5 — personne n'importe `bench` | Test dédié | idem |
| §6 — types gelés | `is_dataclass` + `__dataclass_params__.frozen` | `tests/proprietes/test_invariants_types.py` |
| §6 — preuve sans probabilité | Liste noire de noms de champs | idem |
| §6 — borne avec couverture | Liste blanche de champs obligatoires | idem |
| §6 — ouverture sans position absolue | Liste noire de noms de champs | idem |
| §7 — style, types | `ruff` + `mypy --strict` | `ci.yml`, job *qualité* |
| §9 — budgets de performance | `pytest -m budget --benchmark-only`, job séparé | `benchmarks/test_budgets.py` |
| `DOCUMENTATION.md` §6 — doctests | `pytest --doctest-modules src/archlux` | `ci.yml` |
| `DOCUMENTATION.md` §6 — couverture doc | `interrogate -f 95` | `ci.yml` |

**Le job « tests » exécute `test_dependances.py` dans une étape distincte et antérieure.**
Une violation de couche doit être lisible dans le nom de l'étape qui échoue, pas noyée
parmi trois cents tests.

Deux précisions qui ont chacune coûté un défaut réel :

- **les `__init__.py` sont scannés.** Les exclure laisse le trou le plus probable : un
  paquet qui viole une couche depuis son propre `__init__` ;
- **les dérogations sont nominatives et plafonnées.** `EXEMPTIONS` liste deux imports
  précis (ADR-5), et `test_les_exemptions_restent_rares_et_nommees` échoue au troisième.
  Une liste de dérogations sans plafond est la façon dont une règle de couches se vide,
  une entrée à la fois.

État actuel : **99 tests passent, 2 sont volontairement ignorés** (jalons à venir).
`ruff check .` et `mypy --strict` sont propres sur les 35 fichiers source.

---

## 6. Points d'extension

Où étendre le système sans rien casser, et où **ne pas** l'étendre.

| Besoin | Point d'extension | Pourquoi c'est le bon |
|---|---|---|
| Nouvel indicateur (UDI, vue) | Nouvelle implémentation de `Substitut` | `solve` et `lmo` inchangés |
| Simulateur exact comme oracle | Idem — troisième implémentation du protocole | Permet de mesurer l'erreur du substitut sur la même interface |
| Nouvelle réglementation | Nouveau `Referentiel` (une **donnée**) | Aucun code de `geom` ni `lmo` à toucher |
| Nouveau type de contrainte géométrique | Lignes supplémentaires dans `construire_polytope` + entrées dans `origines` | Le diagnostic dual reste lisible |
| Nouveau corpus | Chargeur dans `bench`, `Decoupage` figé | La règle des trois jeux reste tenue |
| Pièces non rectangulaires | `geom` uniquement — jalon 6 | Le reste de la chaîne ne voit qu'un polytope |

**À ne pas faire :** ajouter un argument à `resoudre` pour « passer un peu de contexte
lumière ». C'est la manière dont l'ignorance de `lmo` se perd — non pas d'un coup, mais
par un paramètre à la fois.

---

## 7. Décisions d'architecture — les ajouts au §11

Trois fichiers ne figurent pas dans l'arborescence cible d'`ARCHITECTURE.md`. Voici
pourquoi ils existent.

### ADR-1 — `erreurs.py` séparé de `types.py`

`ARCHITECTURE.md` §7 exige des exceptions typées sans leur assigner de fichier. Les
placer dans `types.py` poserait un problème : `Infaisable` transporte un certificat de
Farkas et les libellés d'un `Polytope`, objets des couches `lmo` et `geom`. Un module
`erreurs` sans aucune dépendance, en amont comme `types`, évite le cycle. Les champs y
sont typés `object`, et la traduction lisible est faite par l'appelant.

**Alternative écartée :** exceptions dans chaque module. Rejetée — l'utilisateur devrait
importer depuis quatre endroits pour écrire un `except`.

### ADR-2 — `uq/gestion.py` : jeton d'accès à la calibration

`ARCHITECTURE.md` §10 nomme « jeu de calibration lu à l'entraînement » comme la seule
erreur **silencieuse** capable d'invalider une publication. Une règle d'équipe ne suffit
pas contre une erreur silencieuse : le fichier matérialise l'exigence du README (« l'accès
au jeu de calibration exige un jeton émis après le gel du modèle ») en code, et
`CalibrationVerrouillee` la rend bruyante.

### ADR-3 — `bench/{manifeste,graines}.py`

Le README exige un manifeste **à chaque exécution, sans exception**, et §7 une graine
obligatoire sans défaut sur toute fonction qui échantillonne. `bench/graines.deriver`
donne un flux nommé par composante depuis une graine racine : deux composantes ne
partagent jamais un flux, et une exécution se rejoue exactement. Sans ce point unique,
chaque module invente sa convention.

### ADR-4 — `tests/test_dependances.py` écrit avant toute implémentation

Le test coûte une heure aujourd'hui et un refactor complet au jalon 4. Il est à la racine
de `tests/`, pas dans un sous-répertoire, parce qu'il ne teste aucun comportement : il
teste la **forme** du projet.

---

### ADR-8 — Un cache de modèles GLOP porte le démarrage à chaud

`SetStartingLpBasis` **n'est pas exposé** dans le binding Python d'OR-Tools : le seul
mécanisme réel de démarrage à chaud est la réutilisation de l'instance `MPSolver`, qui
laisse GLOP repartir de sa base courante quand seul l'objectif change.

Or `resoudre(poly, c, *, depart=…)` est sans état, et `MILESTONE-2.md` §4 interdit d'en
changer la signature. Le compromis retenu : un cache borné de quatre modèles, indexé par
l'`id` du polytope, dont la valeur **retient le polytope par référence forte** — tant
qu'il est là, son `id` ne peut pas être réattribué, donc la clé reste correcte.

`depart` n'est pas consommé comme un point de départ numérique : sa **présence** est le
signal « je suis dans une boucle sur le même polytope, réutilise le modèle ». C'est une
lecture littérale de l'intention du §10 (« LP sans `depart=` dans la boucle FW : ×3 à ×5
de temps perdu »), et la mesure la confirme : **×3,6**.

Un état global dans un module que `ARCHITECTURE.md` §3 déclare *pur* mérite une
justification : le cache ne change **aucun résultat**, seulement le temps. La pureté visée
ici — déterminisme, rien d'appris — est intacte, et un test de propriété vérifie à chaque
exécution que froid et chaud rendent la même solution. `vider_cache()` rend le départ à
froid explicite pour les mesures.

### ADR-7 — Load-bearing walls: side inequalities read from the proposed plan

- **Status:** decided (2026-09-23, PLAN.md batch 1.1). Supersedes the open question of
  milestone 2.

**Context.** `MILESTONE-2.md` §3 asked for `A_eq` rows tying rooms to load-bearing walls.
They were never written; the proof then compared each wall with itself — walls are not
decision variables — so `structure_preservee` was always true, and rooms crossed
load-bearing walls under a valid certificate (AUDIT.md §3 n°1; 35 of 200 benchmark cases
in performance mode).

**Decision.**

1. A load-bearing wall is a **fixed obstacle**, not an equality. Each room keeps one
   side of each wall — `x + w <= c`, `x >= c`, `y + h <= c` or `y >= c` — read from the
   proposed plan by `deduire_ordre(plan, structure=...)` (`OrdreRelatif.wall_sides`),
   the half-plane the room penetrates least among those with room before the outline.
   `construire_polytope(ordre, ctx)` keeps its signature: the incidence travels in the
   order, like the relative order between rooms.
2. Equalities were rejected: they would pin rooms to walls and forbid a room from
   being bounded by a wall on one side only, or from not touching it at all.
3. The proof checks the guarantee directly: no room interior contains a stretch of a
   load-bearing wall (geometric test, oblique walls included).
4. Oblique load-bearing walls raise `UnsupportedInput`: no single linear side row
   describes them, and ignoring them silently is what this ADR removes.
5. **Columns** (`Structure.poteaux`) are fixed data and are not constrained: a column
   inside a room is normal in housing. Nothing about them is certified.
6. **Openings** are relative to walls (`Ouverture.mur_id`), and walls are not decision
   variables: an opening on a facade stays put (the outline is fixed), but an opening on
   an interior partition does **not** follow a moved room. The README claim "windows
   follow" is withdrawn (PLAN.md 1.8).

**Consequences.** Classic, tiling and performance modes inherit the rows since they
share the polytope. The benchmark reports 0 false certificates after this batch. The
choice of a single half-plane is a deliberate over-constraint, as for the order between
rooms (see `docs/formules/polytope-separe.md`).

### ADR-6 — Les plages du §6 sont vérifiées à la frontière, pas dans les constructeurs

`ARCHITECTURE.md` §6 documente `s ∈ [0,1]` et `largeur_rel ∈ ]0,1]`, et une pièce a des
dimensions positives. Rien ne le faisait respecter : `Ouverture(s=42.0)` se construisait
sans broncher.

| Option | Verdict |
|---|---|
| Valider dans `__post_init__` | Rejetée — interdirait au solveur tout état intermédiaire hors plage, et ferait payer une vérification à chaque construction dans une boucle Frank-Wolfe qui en fait des milliers |
| **Valider dans `depuis_dict`** | **Retenue** |
| Ne rien valider | Rejetée — l'invariant restait purement documentaire |

La frontière JSON est l'endroit où les données viennent de l'extérieur : c'est là qu'il
faut les refuser. L'objet en mémoire reste libre, ce qui laisse `solve` travailler sans
contrainte, et un fichier lu est garanti sain.

`_verifier_plages` rapporte **toutes** les violations d'un coup, pas la première :
corriger un fichier une erreur à la fois est un supplice, et rien n'oblige à s'y prêter.

Corollaire tiré de la même passe : `json.loads` accepte les littéraux `NaN` et
`Infinity`. `ecrire` refusant déjà de les écrire, la lecture devait refuser de les lire —
sans quoi un fichier produit par un autre outil injecte des valeurs non finies dans le
solveur, où elles se propagent en silence jusqu'à un certificat absurde.

### ADR-5 — `Plan.from_json` et `Certificat.rapport()` : deux dérogations nominatives

`DOCUMENTATION.md` §3 et §5 fixent une API publique où le chargement et le rendu sont des
**méthodes du modèle** : `Plan.from_json(...)`, `q.certificat.rapport()`. Les honorer
demande à `types` de joindre `io` et `certify`, alors que `types` ne doit dépendre de
rien.

Trois options ont été pesées :

| Option | Verdict |
|---|---|
| Fonctions libres `ax.charger` / `ax.rapport` | Rejetée — contredit l'API que les specs publient déjà dans leurs exemples |
| Import de `io` et `certify` en tête de `types` | Rejetée — cycle à l'import, et la règle « `types` dépend de rien » disparaît |
| **Import local dans les deux méthodes** | **Retenue** |

L'import local s'exécute à l'appel, jamais à l'import : aucun cycle, et `import archlux`
reste aussi léger qu'avant. Les deux méthodes ne font que **déléguer** — la lecture reste
dans `io`, la mise en forme dans `certify`. Le coût est réel et assumé : deux entrées dans
`EXEMPTIONS`, plafonnées par un test.

## 8. Ordre d'implémentation et état

| Jalon | Modules | Livrable | État du squelette |
|:--:|---|---|---|
| 1 | `types`, `erreurs`, `io`, `bench.{graines,manifeste}` | Aller-retour JSON | **Terminé** — propriété d'aller-retour verte sur 200 cas |
| **2** | `geom`, `lmo`, `certify.proof`, `api` | **Légalisation classique + preuve** | Étapes 1 à 3 faites (`geom.graphe`, `geom.polytope`, `lmo.solveur`) ; étapes 4 à 7 à venir |
| 3 | `light.analytique`, `orient`, `solve` | Performantiel **sans apprentissage** | Contrats écrits |
| 4 | `light.appris`, `light.validation`, `uq.gestion` | Substitut entraîné + gradient validé | Contrats écrits |
| 5 | `uq.conforme`, `uq.derive`, `certify.{borne,dual,rapport}` | Certificat complet | Contrats écrits |
| 6 | non-Manhattan, actif, IFC | v1.0 | — |

Hors jalon 1, **aucun corps de fonction n'est implémenté**. Chaque `NotImplementedError`
porte son numéro de jalon : la dette est datée, pas diffuse.

Le jalon 1 livre au passage ce qui ne se voit pas dans le tableau : `plans_quelconques`,
la stratégie Hypothesis dont dépendront le critère d'acceptation du jalon 2, les tests de
coupes et ceux de dérive. Écrite une fois ici, elle évite trois générateurs divergents.

---

## 9. Conventions transverses

| Point | Règle | Où c'est vérifié |
|---|---|---|
| Unités | mètres, m², degrés d'azimut | Docstrings ; revue |
| Origine | coin bas-gauche, `y` vers le nord | `geom.polytope` |
| Déterminisme | tri explicite des identifiants, jamais l'ordre d'un `set` | `Plan.ids_pieces`, `OrdreRelatif.pieces` |
| Graines | `seed: int` obligatoire, **sans défaut** | Signatures de `uq.derive`, `light.validation` |
| Métriques | valeur **+** intervalle, jamais un scalaire nu | `BornePerformance` |
| Journaux | `structlog`, structuré, jamais de texte libre | Revue |
| Dictionnaires gelés | tuples de paires dans les types gelés | `Referentiel`, `Manifeste`, `Certificat` |

Le dernier point mérite un mot : un `dict` dans un `dataclass(frozen=True)` reste mutable
et n'est pas hachable. Les types du modèle utilisent donc des `tuple[tuple[str, T], ...]`
triés — ce qui rend en prime la sérialisation reproductible, condition du manifeste.

---

## 10. Ce que ce blueprint n'autorise pas

Les huit anti-patterns d'`ARCHITECTURE.md` §10 valent comme motif de refus en revue, sans
discussion sur le cas particulier. Les trois plus coûteux à découvrir tard :

1. **Raster en entrée d'un substitut.** Gradient nul presque partout, optimiseur aveugle.
   Détectable seulement par `valider_gradient` — d'où son caractère obligatoire.
2. **Jeu de calibration vu à l'entraînement.** Aucun test ne le signale ; seul le jeton
   d'ADR-2 l'empêche.
3. **`origines` omis du `Polytope`.** Le diagnostic dual du jalon 5 devient impossible et
   le module doit être reconstruit.
