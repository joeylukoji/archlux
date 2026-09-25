# Plan de remise à niveau d'archlux : objectif 10/10

> Ce plan découle de [`AUDIT.md`](AUDIT.md) (23/09/2026). Chaque référence de type §3 n°1,
> C1, M5, Q-C2 renvoie à la section ou au constat correspondant de l'audit.
>
> **Règle d'or : on ne passe pas à la phase suivante tant que la « porte de sortie » de la
> phase en cours n'est pas franchie.** Une porte est un critère vérifiable (test, commande,
> chiffre), jamais une impression.

---

## 0. Ce que « 10/10 » veut dire ici

Une note ne s'atteint pas par l'effort fourni. Elle s'atteint quand un critère
vérifiable est rempli. Pour chaque axe de l'audit, voici le critère qui vaut 10/10.

| Axe | Note actuelle | Critère du 10/10 | Vérifié par |
|---|--:|---|---|
| Structure du code | 6 | Aucune fonction avec une complexité cyclomatique (CC) > 10 ni plus de 60 lignes hors docstring. Aucun module au-delà de 400 lignes. Règles §5 vraies **à l'exécution**. Aucune logique dupliquée (secteurs, vectorisation, chevauchement, tolérances). | `radon cc -n C`, test dynamique `sys.modules`, revue `python-design-patterns` sans point Majeur |
| Architecture | 5,5 | Chaque garantie annoncée est tenue par le code et testée. Aucune affirmation de la doc n'est contredite par une mesure. | Tests de propriétés + table « doc ↔ code » vide |
| Qualité du code | 6,5 | Couverture ≥ 95 % des lignes et ≥ 90 % des branches, ≥ 5 cas de référence figés, `ruff format` imposé, 0 `except Exception`, exceptions typées partout | CI |
| Types / modèle | 6 | Validation de toutes les entrées publiques, aucun tableau mutable dans un type gelé, `NDArray` typés, `Literal` pour les énumérations | `mypy --strict` + tests de validation |
| Ergonomie de l'API | 4 | Chaque exemple de la doc est exécuté en CI. API dans une seule langue. Chaque erreur utilisateur indique la correction. | `pytest --doctest-glob` sur README et docs |
| Utilisable en cas réel | 3 | Entrée DXF, CLI, exemples livrés, référentiel FR fourni. **Test utilisateur externe réussi en moins de 10 min par au moins 3 personnes.** | Compte rendu de test utilisateur |
| Open source | 4 | LICENSE, historique git, PyPI, DOI Zenodo, CI verte sur 3 OS, fichiers communautaires, premier contributeur externe | Checklist §Phase 8 |
| Article | 5 | Chaque affirmation de l'article est reproductible par une commande et accompagnée d'un intervalle. Au moins 2 générateurs publics, des baselines, des ablations. Relecture interne faite avec la grille d'un relecteur. | `make paper` régénère toutes les tables |
| Jalons J1–J9 (critère atteint) | 4,9 en moyenne | Chaque critère d'acceptation des MILESTONE passe **tel qu'il est écrit**, ou il est **réécrit honnêtement** et la décision est tracée dans un ADR | Tests d'acceptation + ADR |

> **Honnêteté nécessaire.** Neuf axes sur dix dépendent seulement du travail. Deux
> dépendent aussi du **résultat d'une expérience** : l'utilité réelle du mode lumière et
> le contenu de l'article. Si un substitut par pièce ne prédit toujours pas l'éclairement
> après la phase 6, on ne force pas le résultat. On publie le résultat négatif, qui est
> l'article B de l'audit, et on retire la promesse du README. **Un 10/10 scientifique,
> c'est des affirmations vraies, pas des affirmations flatteuses.**

---

## Vue d'ensemble

| Phase | Objet | Durée indicative | Axes visés |
|--:|---|---|---|
| 0 | Fondations : git, licence, filets de sécurité en CI | 2–3 jours | Open source, qualité |
| 1 | Rendre vrai ce qui est affiché (défauts critiques) | 1,5–2 semaines | Architecture, fonctionnalités |
| 2 | Revue des jalons déjà accomplis : ont-ils été correctement faits ? | 1 semaine | Jalons |
| 3 | Frontière d'entrée : validation, erreurs, API | 1 semaine | Types, ergonomie |
| 4 | Refonte par design patterns, bloc par bloc | 3–4 semaines | Structure, qualité |
| 5 | Utilisabilité réelle | 2–3 semaines | Cas concret |
| 6 | Programme scientifique | 2–4 mois | Article, lumière |
| 7 | Revue générale et correction finale des blocs | 1–2 semaines | Tous |
| 8 | Publication open source | 1 semaine, puis 6 mois d'historique | Open source |
| 9 | Rédaction de l'article | 4–6 semaines | Article |
| **E** | **Migration vers l'anglais**, transversale : petits lots greffés sur les phases 0 à 7 | Répartie (+15 à 20 % sur les phases 3, 4 et 7) | Ergonomie, open source, article |

Les phases 4 et 5 peuvent avancer en parallèle de la phase 6, qui est longue parce que
ce sont des expériences. La phase 8 (dépôt public) doit commencer **le plus tôt
possible** après la phase 1 : les revues logicielles exigent 6 mois d'historique public.

### Méthode de travail pour toute modification de code

Cette séquence s'applique à chaque étape et suit `AGENTS.md` :

1. **`request-refactor-plan`** si l'étape touche plus de 3 fichiers : découpage en
   micro-commits.
2. **`tdd`** : écrire d'abord le test qui échoue et montre le défaut (rouge).
3. **`python-expert`** : corriger (vert).
4. **`review-and-refactor`** : relire le diff selon `ARCHITECTURE.md`.
5. **`python-design-patterns`** en plus, si l'étape change une frontière de module.
6. Porte commune : `pytest`, `ruff check`, `ruff format --check`, `mypy src/` au vert,
   `CHANGELOG.md` mis à jour, un commit par intention.

---

## Chantier transversal E : migration vers l'anglais

**Décision.** Code, API, docstrings, messages d'erreur, tests, documentation principale,
README, spécifications et article sont écrits **en anglais**. Le projet vise un usage
et une relecture internationaux.

**Pourquoi.**
- Les relecteurs d'un article lisent le code : un code en français réduit fortement le
  nombre de relecteurs capables de le vérifier.
- JOSS exige un article en anglais, et les utilisateurs de PyPI cherchent en anglais.
- L'API actuelle mélange déjà les deux langues (`legalize` / `verifier_exactement`),
  ce qui est le pire des deux mondes (audit §4, Mineur).

**Ce qui peut rester en français** : une traduction facultative du README
(`README.fr.md`), non normative, et les documents de travail internes (`AUDIT.md`,
`PLAN.md`) jusqu'à la phase 7.

### Principe : jamais de « grand soir »

La migration avance **par petits lots**, greffés sur les phases existantes. Un fichier
est traduit quand on y travaille de toute façon.

Règles :
1. **Un lot = un module ou un document, au plus ~500 lignes modifiées.** Il se termine
   tests verts. On ne commence pas le lot suivant dans la même session si le précédent
   n'est pas vert.
2. **Renommer et refactorer ne se font jamais dans le même commit.** On fait d'abord
   un commit de renommage purement mécanique (comportement identique, cas de référence
   inchangés octet pour octet), puis le commit de refactor. Sinon, la revue devient
   impossible.
3. **Tout nouveau code est écrit en anglais dès la phase 0**, même dans un module qui
   est encore en français.
4. **L'API publique est protégée** : les anciens noms français restent disponibles
   comme alias qui émettent un `DeprecationWarning` jusqu'à la version 1.0.0, puis ils
   sont supprimés.
5. **Les formats de données sont versionnés** : le JSON passe au schéma `v2` (clés
   anglaises), le lecteur accepte `v1` et `v2`, et l'écrivain produit `v2`. Les anciens
   certificats restent lisibles.

### Étapes

| Lot | Moment | Contenu | Critère de fin |
|--:|---|---|---|
| E0 | Phase 0 | **Glossaire FR → EN** (`docs/glossary.md`) validé une fois pour toutes (tableau ci-dessous) ; ADR « English-first » ; règle ajoutée dans `ARCHITECTURE.md` §7 et `CONTRIBUTING.md` | Glossaire figé |
| E1 | Phase 0 | Contrôle en CI : un script signale les nouveaux identifiants, docstrings et messages non anglais dans les fichiers **déjà migrés** (liste d'autorisation qui grandit lot par lot) | CI active |
| E2 | Phase 1.8 | **README en anglais** (il est réécrit de toute façon) ; `README.fr.md` facultatif | README EN exécuté en CI |
| E3 | Phase 1.8 | `ARCHITECTURE.md`, `CONTRIBUTING.md`, `AGENTS.md`, `CLAUDE.md` traduits | — |
| E4 | Phase 3 | **API publique** renommée en une seule release (elle est petite : environ 25 symboles), avec des alias français dépréciés ; exceptions et messages d'erreur en anglais | `test_api_publique_stable` mis à jour, alias testés |
| E5 | Phase 3 | Schéma JSON v2 (clés anglaises) + lecteur v1/v2 | Aller-retour v1 → v2 testé |
| E6–E19 | Phase 4 | **Un module par lot**, dans l'ordre du refactor : `types` → `geom` → `lmo` → `solve` → `light` → `orient` → `uq` → `certify` → `feasibility` → `api` → `active` → `export` → `data` → `bench`. Pour chaque module : commit de renommage (fichiers, identifiants, docstrings, commentaires), puis commit de refactor | Cas de référence inchangés après chaque renommage |
| E20 | Phase 4 | Tests renommés et traduits (`tests/unites` → `tests/unit`, `proprietes` → `properties`, `references` → `reference`) | — |
| E21 | Phase 2 / 6 | Scripts d'`experiences/` et fichiers de `resultats/` utilisés par l'article (ils sont réécrits de toute façon) | — |
| E22 | Phase 7 | Site MkDocs : `docs/concepts`, `formules`, `galerie`, `tutoriels`, `donnees` traduits, par dossier | `mkdocs build --strict` vert |
| E23 | Phase 7 | Suppression des alias français (version 1.0.0) ; traduction ou archivage de `AUDIT.md` et `PLAN.md` | Plus aucun identifiant français dans `src/` |

### Glossaire de départ (à valider en E0)

| Français (actuel) | Anglais (cible) | | Français (actuel) | Anglais (cible) |
|---|---|---|---|---|
| `legalize` | `legalize` | | pièce / `Piece` | `Room` |
| mur / `Mur` | `Wall` | | ouverture / `Ouverture` | `Opening` |
| contexte / `Contexte` | `Context` | | référentiel / `Referentiel` | `Regulation` |
| porteur | `load_bearing` | | contour | `outline` |
| preuve / `PreuveGeometrique` | `GeometricProof` | | borne / `BornePerformance` | `PerformanceBound` |
| certificat | `Certificate` | | substitut / `Substitut` | `Surrogate` |
| chevauchement | `overlap` | | jour | `gap` |
| pavage / `pavage.py` | `tiling` / `tiling.py` | | trame | `grid` |
| coupes / `coupes.py` | `cuts` / `cuts.py` | | solveur / `solveur.py` | `solver.py` |
| graphe / `graphe.py` | `graph.py` | | rectilinéaire | `rectilinear` |
| `conforme.py` | `conformal.py` | | `derive.py` | `drift.py` |
| `fiabilite.py` | `reliability.py` | | `gestion.py` | `registry.py` |
| `boucle.py` / `densite.py` | `loop.py` / `density.py` | | `chargeurs.py` / `decoupage.py` | `loaders.py` / `splits.py` |
| `erreurs.py` / `Infaisable` | `errors.py` / `Infeasible` | | `InvariantViole` | `InvariantViolation` |
| graine | `seed` | | jalon | `milestone` |
| `SimulateurExact` | `SplitFluxOracle` | | éclairement | `daylight` / `illuminance` |

**Porte de sortie du chantier E** : `grep` des mots français courants dans `src/` et
`tests/` → 0 résultat hors alias dépréciés ; documentation principale entièrement en
anglais ; à partir de la 1.0.0, plus aucun alias.

---

## Phase 0 : fondations (avant toute correction)

But : pouvoir mesurer et revenir en arrière. On ne corrige rien sans filet.

| # | Tâche | Détail | Réf. audit |
|--:|---|---|---|
| 0.1 | `git init` + premier commit | Compléter d'abord `.gitignore` : `.hypothesis/`, `.benchmarks/`, `.coverage`, `session_memory.json`, `resultats/_tmp_ifc/`. Décider si `.claude/`, `.cursor/`, `.agents/` sont versionnés ; si oui, l'expliquer dans `CONTRIBUTING.md`. | §3 n°10, §11 |
| 0.2 | Ajouter `LICENSE` | Texte officiel Apache-2.0, plus un `NOTICE` si nécessaire. | §3 n°4 |
| 0.3 | Revenir en `0.9.0` | Dans `pyproject.toml` et `__version__`, avec **une seule source de version** (`archlux/_version.py` ou `importlib.metadata`). Corrige aussi l'en-tête « archlux 0.0.0 » du certificat. | §3 n°9, C2 |
| 0.4 | Formatage imposé | `ruff format .` en un seul commit isolé (ne rien mélanger d'autre), puis `ruff format --check` en CI et un `pre-commit`. | §2 |
| 0.5 | Seuil de couverture | `fail_under = 84` tout de suite, pour ne jamais régresser. On le remonte à chaque phase jusqu'à 95. | Q-M7 |
| 0.6 | Benchmarks robustes | `benchmarks/test_budgets.py` doit tolérer `--benchmark-disable` : sauter l'assertion si `benchmark.stats is None`. | §2 |
| 0.7 | Tests du README et de la doc | Ajouter un test qui **exécute** chaque bloc de code du README et de `docs/`. Il sera rouge ; on le marque `xfail(strict=True)` bloc par bloc, et chaque correction retire un `xfail`. | §3 n°2 |
| 0.8 | Stratégies Hypothesis réalistes | `tests/proprietes/strategies.py:205` : générer aussi des `aires_min` **non vides**, des porteurs et des budgets. Les tests qui échouent alors deviennent les tests rouges de la phase 1. | §6 « pourquoi les tests n'ont rien vu » |
| 0.9 | Registre des tolérances | Créer `archlux/tolerances.py` (sans encore remplacer les usages) pour que la phase 1 s'y appuie. | §6 Mineur |

**Porte de sortie de la phase 0** : dépôt git propre, LICENSE présente, CI verte avec
format + seuil de couverture, et une **liste des tests rouges** issus de 0.7 et 0.8, qui
sert de périmètre à la phase 1.

---

## Phase 1 : rendre vrai ce qui est affiché

But : aucune garantie annoncée ne doit être fausse. C'est la phase la plus importante :
tant qu'elle n'est pas finie, le projet ne peut être ni publié ni cité.

**Instrument de mesure** : `benchmarks/guarantees/` (200 scénarios déterministes, 5 modes,
contrôle indépendant). Chaque lot relance
`python -m benchmarks.guarantees.measure --label after-1.x --seed 17` et son effet se lit
dans `benchmarks/guarantees/README.md`. Référence (`baseline`, révision `95baabe`) :

| Mode | Correct | Certificat mensonger | Refus | Plantage |
|---|--:|--:|--:|--:|
| classique, entrée valide | 200 | 0 | 0 | 0 |
| classique + pavage, une faute de 25 cm (régime J7) | 200 | 0 | 0 | 0 |
| classique + pavage, bruit de 3 cm partout (régime J8) | 0 | 1 | 199 | 0 |
| performance, substitut analytique | 0 | **35** (murs traversés) | 165 (surfaces) | 0 |
| performance, `Daylight` | 0 | 0 | 0 | **200** |

**Constats nouveaux du banc**, ajoutés au périmètre :
- 68 refus du régime J8 disent « Infaisable : origines non renseignées » : un refus sans
  explication, contraire au principe du certificat de Farkas → lot 1.5 (et message en 3.4) ;
- en régime J8, la réparation échoue sur 199 plans sur 200 : c'est cohérent avec les ~20 %
  du jalon 8, en plus sévère parce que les surfaces minimales sont serrées ; à documenter,
  pas à « corriger » en phase 1 (sujet de la phase 6.5).

### 1.1 Structure porteuse réellement contrainte et vérifiée (§3 n°1, §5.3)

- **Modèle** : ajouter dans `Contexte` les incidences pièce ↔ mur porteur (option 1 de
  l'ADR-7), déduites du plan proposé à une tolérance de `tolerances.py`.
- **Polytope** : traduire ces incidences en lignes `A_eq` (bord de pièce = axe porteur).
- **Preuve** : `_structure` vérifie qu'aucun porteur ne coupe l'intérieur d'une pièce,
  qu'aucun poteau n'est dans une pièce, et que chaque porteur reste porté par un bord.
- **Ouvertures** : décider si les murs sont des variables. S'ils ne le sont pas, les
  fenêtres des murs non porteurs doivent suivre la pièce. Sinon, retirer « les fenêtres
  suivent » du README.
- **Tests** : propriété « aucune sortie de `legalize` ne traverse un porteur » ; test de
  non-régression sur la grille 5×3 avec un porteur à x = 6 (le cas mesuré dans l'audit).
- **Doc** : corriger `types.py:92-93` et l'ADR-7.

**État du lot 1.1 : terminé (2026-09-23).** Contraintes de côté (inégalités, pas
égalités : ADR-7 réécrit), preuve géométrique réelle, murs obliques refusés
(`UnsupportedInput`). Banc : certificats mensongers 35 → **0** en mode performance ;
mode « mur partiel + une faute » 196/200. Revue `review-and-refactor` faite ; ses
3 points majeurs et 10 mineurs sont corrigés. Suites identifiées :
- *la trame du pavage est reconstruite sans connaître les murs porteurs* : 2 refus
  honnêtes sur 200 (mur partiel + faute) → faire des murs porteurs des lignes imposées
  de `deduire_trame` (à traiter avec 1.5) ;
- poteaux non contraints, ouvertures des cloisons intérieures non suivies : décisions
  documentées (ADR-7, `limites.md`), README corrigé en 1.8.

### 1.2 Frank-Wolfe qui respecte les surfaces minimales (§3 n°6, Q-C1, §5.6)

- Appliquer `_resserrer_bornes` au domaine **avant** la première itération. Le domaine
  reste convexe, donc toute combinaison convexe reste valide.
- Si un pas viole malgré tout une surface, le raccourcir (recherche linéaire bornée) ; ne
  jamais l'accepter.
- Repli : si la preuve finale échoue, rendre le **dernier itéré prouvé valide**, au pire
  le plan L1, avec un avertissement dans le certificat. Ne plus lever `InvariantViole`
  dans ce cas.
- **Tests** : la propriété « tous les itérés sont valides » avec `aires_min` non vide ;
  le tableau de scalabilité de l'audit (15/50/100/150 pièces, `a_min = 11`) doit réussir
  partout.

**État du lot 1.2 : terminé (2026-09-23).** Approximation **intérieure** des surfaces
minimales (cordes de l'hyperbole, `lmo.coupes.inner_area_constraints`) : tout itéré de
Frank-Wolfe respecte toutes les surfaces, par construction. Banc : mode performance
33 → **200/200** (mur plein) et 41 → **200/200** (mur partiel). Le démarrage à chaud du
LP est rétabli (plus de coupes tangentes), avec un budget de 50 ms sur 500.
**Coût mesuré après revue** (grille de raison 1,1, 49 nœuds) : (a) sur les 33 scénarios qui
réussissaient avant le lot, gain médian sur la légalisation classique 4,3 % → 4,6 %,
objectif après/avant entre 0,99 et 1,02 ; (b) sur les 200 scénarios, face à une grille de
référence de 235 nœuds : médiane 0,9985 du gain de référence, ≥ 0,95 dans 96 % des cas,
+4 ms. La première version (5 nœuds filtrés par les bornes) perdait tout gain dans 7 cas
sur 120 : la revue l'a trouvé. Le repli « rendre le plan classique au lieu de lever »
prévu ci-dessous n'est plus nécessaire tant que le banc reste à 0 refus
`refused_invariant` en mode performance.

### 1.3 `Daylight` conforme au protocole (§3 n°3)

- Ajouter `*, baies=None` à `evaluer`, `gradient`, `incertitude`, puis le propager.
- Test d'intégration `legalize(objective=Daylight(...))`.
- Remplacer la vérification `isinstance(x, Substitut)` par un contrôle de signature
  (`inspect.signature`) dans un test de conformité, appliqué à **tous** les substituts.

**État du lot 1.3 : terminé (2026-09-23).** `Daylight` accepte et transmet `baies` ;
test de conformité des signatures sur les cinq substituts ; `Daylight` gelé. Banc :
200 plantages → **200/200 corrects**. Il n'y a plus ni certificat mensonger ni
plantage dans aucun mode. **Réserve de fond, non traitée ici** (audit §5.5) :
l'incertitude σ est constante dans les trois substituts livrés, donc
`Daylight = μ − qσ` a le même optimum que `μ` et le garde-fou est inopérant.
Traité en phase 6.3 (σ variable par ensemble ou régression quantile).

### 1.4 Frank-Wolfe honnête sur ce qu'il garantit (§5.1)

- `gap` initialisé à `inf` ; gap recalculé **au `x` rendu** ; `iterations` sans décalage.
- Statut d'arrêt explicite : `converge | recherche_de_pas | lp_non_optimal | max_iter`.
- Renommer en `gap_stationnarite`. N'appeler « borne sur l'optimum » que si le substitut
  déclare `concave=True`.
- Démarrage à chaud **avec coupes** : modèle GLOP en cache, coupes ajoutées de façon
  incrémentale (Q-C2). Nouveau budget §9 « performantiel avec `aires_min` ».
- Budget consommé une seule fois : boîte centrée sur la proposition, et nouveau prédicat
  de preuve `deplacement_max ≤ budget` (§5.8, `api.py:255-260`).

**État du lot 1.4 : terminé (2026-09-24).** Précédé de la migration du module `solve`
vers l'anglais (lot E9), dans un commit de renommage dont la neutralité est prouvée par
empreinte SHA-256 identique sur 200 exécutions de Frank-Wolfe. Gap initialisé à +∞,
recalculé au point rendu, documenté comme mesure de stationnarité (aucun substitut
livré n'est concave) ; statut d'arrêt explicite ; `Trace.final_gap`. Budget : dépensé
une seule fois (boîte centrée sur le plan proposé, qui contient toujours le résultat
classique) et vérifié par la preuve ; mesuré avant correction : 0,55 m pour 0,3 m.
Budget « certification » du §9 enfin mesuré (1,5 ms sur 5). Revue : 4 points majeurs
corrigés, dont une régression à budget saturé (15 sondes sur 40). Le banc a un mode
avec budget et un contrôle indépendant du budget. **Reporté au lot 1.5** : le reliquat
« X m² < X m² » (1 cas sur 200 en mode budget), et l'écart entre la tolérance du LP
(~1e-6) et celle de la preuve sur le budget (`SNAP_M`, 1e-7).

### 1.5 Preuve réellement exacte (§5.4)

- Vérification en `fractions.Fraction` pour les rectangles axés : disjonction deux à deux,
  inclusion dans le contour, et Σ aires = aire du contour. GEOS devient une vérification
  croisée, plus la référence.
- Si c'est impossible dans un cas (non-Manhattan), le certificat dit « vérification à
  tolérance ε = … ».
- **Vérifier le certificat de Farkas** en rationnels : y ≥ 0, yᵀA = 0, yᵀb < 0.
- Reformuler : « infaisable **pour cet ordre relatif** ».
- `lmo/coupes.py:449` : ne jamais conclure `Infaisable` sur un domaine resserré ; relancer
  sur le domaine d'origine (Q-M6).
- Remplacer les 25 tolérances dispersées par `tolerances.py`, en harmonisant 1e-9 et 1e-7.

**État du lot 1.5 : terminé (2026-09-24).** Trois sous-lots et une revue.
1.5a : la boucle de coupes accepte à la tolérance de la preuve (`AREA_PROOF_M2`) et vise
`a_min + 1e-6` pour les seules pièces en déficit ; le reliquat « X m² < X m² » disparaît.
1.5b : pavage prouvé en `Fraction` sur contour rectangulaire (identification des arêtes
à `SNAP_M`, puis inclusion, disjonction, somme des aires), puis bornage exact du plan
brut (chevauchements ≤ `OVERLAP_M2`, débord et borne de Bonferroni du non-couvert ≤
`GAP_M2`) ; GEOS reste pour les autres contours. 1.5c : chaque refus de `legalize` est
nommé et typé (`GridNotRecoverable`, `UnsupportedInput`), le certificat de Farkas couvre
aussi `A_eq` et il est vérifié en rationnels (`verified`) ; « infaisable pour cet ordre
relatif ». Revue : 2 majeurs corrigés (programmes serrés refusés 37 fois sur 40 ;
identification qui effaçait jusqu'à 1e-7·L m²), 6 mineurs corrigés. Banc
`after-1.5-review` : 0 faux certificat, 0 plantage sur 1 600 cas.
**Reporté** : (i) 28 plans bruités sur 200 laissent une bande non couverte après pavage
(lignes extérieures de la trame non ancrées au contour), lot dédié avant la porte de
phase 1 ; (ii) la trame ignore les murs porteurs (2 refus en `partial_one_fault`) ;
(iii) les infaisabilités dues aux surfaces ne citent pas la surface et ne sont pas
vérifiables (les coupes n'entrent pas dans le certificat ; il faudra des coupes au
minimum exact, étiquetées) → phase 3.4 ; (iv) tolérances encore littérales hors `certify`
et `lmo.coupes` → au fil des lots ; (v) `GridNotRecoverable` et `UnsupportedInput`
absents de `archlux.__all__`, et plan vide, contour non rectangulaire ou pièce dégénérée
encore en `InvariantViole` dans `pavage` → phase 3 ; (vi) double `DeprecationWarning`
sur `from archlux.certify import verifier_exactement` → phase 3.

### 1.6 Borne probabiliste qui dit son régime (§5.3)

- `BornePerformance.regime: Literal["exchangeable", "selected"]` (English labels, ADR 0001).
- Le rapport affiche un bandeau distinct si le plan a été choisi par l'optimiseur ; dans
  ce cas, pas de « couverture 90 % » sans réévaluation du plan par l'oracle.
- `legalize(objective=...)` remplit enfin `Certificat.performance` (§8 étape 3g).
- `empreinte_jeu` : hacher le jeu de données, pas les scores.
- `borner(..., incertitude=...)` : paramètre obligatoire.

**État du lot 1.6 : terminé (2026-09-24).** Chaque borne déclare son régime
(`"exchangeable"` ou `"selected"`) ; le rapport n'affiche plus de couverture pour un plan
choisi par l'optimiseur ; `legalize(..., calibration=...)` remplit enfin
`Certificat.performance`, en régime `"selected"`, centrée sur la prédiction μ̂ du
substitut ; `incertitude` et `regime` obligatoires ; `empreinte_jeu` hache le jeu de
données brut. Revue : 1 critique corrigé (borne ASE publiée négative), 1 majeur
(scripts `experiences/` cassés, hors mypy) et 6 mineurs. Banc `after-1.6` identique.
**Reporté** : une procédure valide sous sélection (phase 6.4) ; `experiences/` reste
hors mypy et hors tests (phase 2, outillage) ; renommer `couverture` en
`couverture_nominale` au prochain changement cassant du schéma.

### 1.7 Pièces en L correctes (§5.2)

- Ajouter les inégalités de recouvrement sur l'axe orthogonal, pour qu'un L ne devienne
  pas un Z.
- Contrôler la surface sur le polygone recomposé, et non par sous-rectangle.

**État du lot 1.7 : terminé (2026-09-25).** `etendre_fusions` garde, sur l'axe
orthogonal, l'ordre des extrémités des sous-rectangles et une longueur de contact
minimale (`overlap_constraints`, `largeur_min`) : un L ne devient plus ni un T, ni un Z,
ni deux pièces. La surface minimale d'une pièce fusionnée est prouvée sur l'union
(`verify_exactly(..., fusions=)`) ; le solveur donne à chaque partie une part
proportionnelle du minimum (`minimum_area_shares`, prudent : un refus à tort est
possible, un faux certificat non). Le contrôleur indépendant mesure une pièce fusionnée
d'un seul tenant ; propriété Hypothesis dédiée (`test_l_room_guarantees.py`).
Revue : 1 critique corrigé (un porteur sur la couture d'un L était certifié : la cuisine
était coupée en deux) et 1 majeur (col de 1e-7 m accepté). Revue finale de la phase 1 :
les parties d'un L gardent chacune leur côté d'un porteur, sauf si deux d'entre elles
prennent des côtés opposés (seul cas où la couture peut tomber sur le mur) ; le côté de
la boîte englobante, imposé à toutes, déplaçait un pied qui ne touchait pas le mur.

### 1.8 Documentation alignée sur le code (§5.8)

- Corriger **chaque ligne** du tableau « écarts doc ↔ code » : README l.156-205, 251,
  281, 285, 289-290, 314, 332, 368, 398-399, 603/667 ; `ARCHITECTURE.md` §1, 2, 3, 9, 11.
- Pour les fonctionnalités absentes (front de Pareto, non-Manhattan) : les retirer ou les
  déplacer dans « Feuille de route ».
- Régénérer `Project_Architecture_Blueprint.md` avec `architecture-blueprint-generator`.
- Renommer `SimulateurExact` en `SplitFluxOracle` (garder un alias déprécié) et ne plus
  écrire « vérité terrain » ni « exact » à son sujet.
- Premier paragraphe du README : dire clairement dans quel régime l'outil fonctionne
  (93,9 % sur plans corrompus, environ 20 % sur sorties de générateur).

**État du lot 1.8 : terminé (2026-09-25).** README réécrit en anglais (lot E2), premier
paragraphe sur le régime (93,9 % sur plans MSD corrompus avec repli, environ 20 % sur
sorties HouseDiffusion, chiffres d'avant le lot 1.1, à remesurer en phase 2) ; chaque
exemple du README et de `docs/` est exécuté par `tests/docs/test_examples.py`
(`KNOWN_BROKEN` vide). Chaque ligne du tableau §5.8 de l'audit est corrigée ; front de
Pareto et non-Manhattan déplacés dans la feuille de route. `ARCHITECTURE.md` §1, 2, 3,
9, 11 alignés sur le code, `Project_Architecture_Blueprint.md` régénéré.
`SimulateurExact` → `SplitFluxOracle` (alias `SimulateurExact` et `ExactSimulator`
dépréciés jusqu'à 1.0.0), jamais « exact » ni « vérité terrain ». Lot E3 :
`ARCHITECTURE.md`, `CONTRIBUTING.md`, `AGENTS.md` et `CLAUDE.md` traduits, ajoutés à la
liste des fichiers migrés de `tests/test_language.py`. Les chiffres de `api.py`
(93,0 % / 97,6 %, colonne `pavage=True`) et du README (93,9 %, colonne repli) sont
distingués dans la docstring.

**Porte de sortie de la phase 1** :
- banc `benchmarks/guarantees` : **0 certificat mensonger et 0 plantage dans tous les
  modes** ; en mode performance, au moins 95 % de sorties correctes ;
- tous les `xfail` de 0.7 et 0.8 retirés ;
- la propriété « aucune sortie de `legalize` ne viole une garantie `[EXACT]` » tient sur
  2 000 exemples Hypothesis avec porteurs, `aires_min` et budget ;
- le tableau « doc ↔ code » est vide ;
- relecture `review-and-refactor` sans point Critique.

---

## Phase 2 : revue des jalons déjà accomplis

But : vérifier si ce qui a été fait est **correctement fait**, avec le code corrigé de la
phase 1. Chaque jalon reçoit un **rapport de revue** (`docs/revues/jN.md`) qui contient :
critère d'acceptation tel qu'écrit → rejoué ? → résultat → décision.

| Jalon | Ce qu'il faut revérifier | Décision attendue |
|---|---|---|
| **J1** | Aller-retour JSON avec les nouveaux champs (incidences porteurs, `regime`) ; publier `schema.json` versionné | Critère maintenu |
| **J2** | Rejouer `test_toute_sortie_est_valide` **avec** porteurs. Remplacer `j2_brut.csv` (2 plans faits à la main) par la vraie baseline promise : 3 générateurs publics, ou au minimum HouseDiffusion plus un second (voir 6.5) | Réécrire la ligne « Ce jalon suffit à un premier article » si ce n'est pas le cas |
| **J3** | Rejouer les 3 tests d'acceptation avec `aires_min` non vide ; rejouer `j3_orientation` | Critère maintenu après 1.2 |
| **J4** | Constater que le critère a été franchi contre un oracle qui ne pouvait pas le faire échouer. **Réécrire le point de contrôle** : accord de signe mesuré contre une simulation physique (6.2), sur des plans réels | ADR : « le point de contrôle J4 est rouvert » |
| **J5** | Rejouer la couverture sur le test **et** sur des plans sélectionnés par l'optimiseur ; mesurer la largeur relative de l'intervalle par rapport à l'écart-type de la cible | Critère ajouté : « largeur < 1 écart-type de la cible » |
| **J6** | **Refaire actif contre aléatoire** avec des graines dérivées (Q-M5) avant de conclure ; faire le test utilisateur externe (phase 5) ; tester l'IFC dans un vrai logiciel BIM | La conclusion « l'actif perd » est suspendue jusqu'au nouveau calcul |
| **J7** | Rejouer après 1.1 : les porteurs contraints changent-ils les 93,9 % ? Analyser les 68 % d'appartements MSD rejetés (143 obliques, 240 contours non simples) | Chiffres mis à jour partout, y compris dans `api.py:155` |
| **J8** | Rejouer avec le nouveau Frank-Wolfe et les porteurs ; ajouter les métriques de ressemblance (6.5) | Chiffres mis à jour |
| **J9** | Rejouer avec le substitut par pièce (6.1) : les pièces dégénérées de 0,7 m² doivent disparaître | Refaire la figure |

Chaque script d'expérience rejoué doit passer sous **50 lignes** et n'utiliser que
l'API publique (règle §11). Les fonctions manquantes identifiées dans l'audit (M12)
entrent dans la bibliothèque.

**Porte de sortie de la phase 2** : 9 rapports de revue ; chaque chiffre de
`resultats/` régénéré par une seule commande (`make resultats`), avec graine et
empreinte ; les critères MILESTONE réécrits sont tracés dans un ADR.

---

## Phase 3 : frontière d'entrée, erreurs et API

| # | Tâche | Réf. audit |
|--:|---|---|
| 3.1 | Validation une fois à l'entrée de `legalize` et `is_feasible` : finitude, signes, plages, ids uniques, `budget ≥ 0`, `Orientation` normalisée modulo 360 | §3 n°8, §7 |
| 3.2 | `__post_init__` de cohérence : `PreuveGeometrique` (`valide` ⇒ aucune violation), `BornePerformance` (`inf ≤ valeur ≤ sup`), `Ouverture` (`s ∈ [0,1]`) | §7 |
| 3.3 | Hiérarchie d'exceptions : `EntreeInvalide`, `BudgetInsuffisant(Infaisable)`, sous-classes de décomposition. `InvariantViole` réservée aux bogues internes. Plus aucune `ValueError`, aucun `except Exception`, aucun tri par lecture du texte d'un message | Q-M1, Q-M2, Q-M3 |
| 3.4 | Messages qui guident : « relancer avec `pavage=True` », « le budget est insuffisant, pas le programme » | §3 n°7 |
| 3.5 | `TypePiece` en `Literal` ou avertissement si un type est inconnu du référentiel | §7 |
| 3.6 | `kw_only=True` sur `Piece`, `Mur`, `Ouverture` ; valeurs par défaut `murs=()`, `ouvertures=()` ; `Contexte.contour` repris du plan | §7 |
| 3.7 | Tableaux gelés : `setflags(write=False)`, `MappingProxyType`, `field(compare=False)` pour `trace` ; `hash(plan)` ne plante plus | §7, Q-m5 |
| 3.8 | Typage : alias `VecteurF = NDArray[np.float64]`, `NewType` pour les unités, `Indicateur` partagé, `TYPE_CHECKING` pour les paquets paresseux | §7 |
| 3.9 | **API publique en anglais** : lots E4 et E5 du chantier E (alias français dépréciés jusqu'à la 1.0.0) ; supprimer les doublons `ExactSimulator` / `Manifest` | §4 Mineur |
| 3.10 | `is_feasible(plan, ctx) -> Verdict` : ne résout que le LP de faisabilité, rend le plan témoin, ne laisse jamais échapper `InvariantViole` | M2, §8 5c |
| 3.11 | Exports publics : `Plan.to_dxf/to_ifc/to_svg`, acceptant `str` et `Path` | §8 étape 6 |
| 3.12 | Diagnostic dual filtré sur les origines métier et exprimé en unités métier (m², points d'indicateur) | §3 n°9 |
| 3.13 | Faire taire OR-Tools sur stderr ; import en moins de 0,5 s (scipy.stats et networkx chargés à la demande) | §8, §2 |

**Porte de sortie de la phase 3** : batterie de tests « entrées hostiles » (tous les cas
du tableau §7 de l'audit) qui lèvent chacun une exception typée avec un message
actionnable ; `python -X importtime -c "import archlux"` sous 0,5 s.

---

## Phase 4 : refonte par design patterns, bloc par bloc

But : structure à 10/10. Chaque bloc passe par la séquence
`request-refactor-plan` → `tdd` (épingler le comportement **avant** de toucher) →
`python-expert` → `review-and-refactor` → `python-design-patterns`.

> **Condition d'entrée** : un bloc ne se refactore que lorsque ses tests de propriétés
> et ses cas de référence figés existent (Q-M8). On épingle d'abord, on déplace ensuite.

| Bloc | Patron appliqué | Travail | Réf. |
|---|---|---|---|
| **Imports et couches** | Façade paresseuse, inversion de dépendance | `light/__init__`, `certify/__init__` paresseux ; `__version__` hors de la racine ; test **dynamique** `sys.modules` pour chaque règle §5 ; `api` ajoutée au §5 | C1, C2 |
| **`types`** | Entités pures | Sortir `trace` de `Plan` (`legalize_trace` renvoie `(Plan, Trace)`) ; déplacer `ModeleTrace` et `Manifeste` vers `bench` ; `CHAMPS_VECTEUR` et `vectoriser(plan)` | M4, M8 |
| **`geom`** | SRP | `pavage.py` → `trame.py` (inférence et réparation) + `pavage.py` (contraintes) ; `deduire_trame` découpée sous CC 10 ; `diagnostic.py` → `data/` | M10, M11 |
| **`lmo`** | Cache explicite | Cache de modèles injectable (objet `CacheLP`, pas un global indexé par `id()`), sûr entre fils d'exécution | §6 `lmo` |
| **`solve`** | Objet paramètre, Stratégie | supprimer le chemin legacy `coupes`/`pieces`/`ctx` et `_enrichir_coupes` (sans appelant depuis le lot 1.2) ; extraire `_pas_away`, `_recherche_lineaire`, `_mettre_a_jour_poids` ; pas de calcul sous forme de **Stratégie** injectable | M7, Q-M9 |
| **`light`** | Registre, protocole | **Registre d'indicateurs** (nom, sens, unité, plage), qui supprime les `if nom == "ASE"` ; `SubstitutDense` découpé en modèle / entraîneur / sérialiseur ; protocole `Empreintable` | M6, §5.7 |
| **`orient`** | Une seule source de vérité | Une fonction `secteur(deg, n, *, centre)` utilisée par `light`, `uq`, `bench` | M3 |
| **`uq`** | Protocole | Plus de réflexion sur `W1..b3` ; `nan` silencieux remplacé par une exception ou un journal | M6, Q-M4 |
| **`certify`** | Composite | `PreuveGeometrique` devient un tuple de **prédicats nommés** (`Predicat(nom, valide, detail)`) : ajouter une règle réglementaire ne casse plus le type ni le JSON | §5.7 |
| **`feasibility`** | SRP | Code métier sorti de `__init__` vers `verdict.py` ; `_resoudre_l1` partagé avec `api` | M2 |
| **`api`** | Pipeline | `legalize` = `_polytope_du_plan` → `_legaliser_l1` → `_optimiser_lumiere` → `_certifier` ; `pavage: int \| None` remplace le couple de drapeaux | M8 |
| **`active`** | Objet valeur, protocole | `Lot(x, orientations)` ; protocole `Ajustable` ; graines par `deriver` ; `run` sous CC 10 | M9, Q-M5 |
| **`export`** | SRP | `_ecrire_spf_minimal` découpé par entité IFC ; `pathologie` s'appuie sur `Plan.certificat` au lieu de recalculer les chevauchements ; SVG testé | M5 |
| **`data`** | SRP, objet paramètre | `chargeurs.py` → `msd.py`, `etiquettes_sd.py`, `decoupage.py` ; `ReglagesMSD` ; `_convertir` en 4 fonctions (redresser, caler, décomposer, rattacher) ; `imputation.py` supprimé ou branché | M1, Q-M2/M3 |
| **`bench`** | — | Synthèse Wilson générique (sortie de `j8_generation.py`), `stats` couvert au-delà de 90 % | M12 |
| **`experiences/`** | Règle §11 | Chaque script sous 50 lignes, API publique seulement, aucun import de fonction privée d'un autre script | M12 |
| **Observabilité** | — | `structlog` dans `api`, `solve`, `data`, `export` (événements structurés : itérations FW, rejets de chargement, replis) | Q-m14 |
| **Docstrings** | — | Sections `Parameters`/`Returns` NumPy complètes (54 manquantes), vérifiées par `numpydoc validate` en CI | Q-m1 |

**Porte de sortie de la phase 4** :
- `radon cc src -n C` ne renvoie rien (aucune fonction au-delà de CC 10) ;
- aucun module de plus de 400 lignes ;
- couverture ≥ 95 % des lignes et ≥ 90 % des branches ;
- cas de référence **inchangés octet pour octet** (le refactor n'a rien changé au
  comportement) ;
- nouvelle revue `python-design-patterns` et `review-and-refactor` : 0 Critique,
  0 Majeur.

---

## Phase 5 : utilisabilité réelle

| # | Tâche |
|--:|---|
| 5.1 | `Plan.from_dxf(chemin, calque_pieces=...)` et `Structure.from_dxf(chemin, calque=...)` (avec `ezdxf` en extra `cao`), plus une lecture IFC en option |
| 5.2 | CLI `archlux legalize plan.json --pavage -o corrige.json --svg corrige.svg --rapport` ; `archlux verifier`, `archlux faisable` |
| 5.3 | `examples/` : 3 plans (T2 simple, T3 avec porteurs, plan généré) et un script de 20 lignes, exécutés en CI |
| 5.4 | Préréglage `Referentiel.preset("fr/logement-collectif")` sourcé (surfaces et largeurs par type de pièce, largeur de passage) ; le document réglementaire est cité |
| 5.5 | Certificat lisible par un architecte : rapport texte + fiche SVG ou PDF avant/après, diagnostic en unités métier |
| 5.6 | Tutoriel « 10 minutes » en notebook exécuté en CI |
| 5.7 | Export IFC testé dans au moins deux logiciels (BIMcollab Zoom, Revit ou FreeCAD) ; taux de survie remesuré |
| 5.8 | **Test utilisateur externe (critère J6)** : 3 personnes qui n'ont jamais vu le code (dont au moins un architecte), chronométrées, avec compte rendu écrit des frictions ; chaque friction corrigée puis retestée |

**Porte de sortie de la phase 5** : 3 réussites sur 3 en moins de 10 minutes ;
`pip install archlux` dans un environnement vierge, suivi de l'exemple du README, sur
Linux, Windows et macOS en CI.

---

## Phase 6 : programme scientifique (conditions d'un article de qualité)

Chaque expérience suit le même protocole :
1. **pré-enregistrement** dans `docs/preregistrement/` (hypothèse, métrique, test
   statistique, taille d'échantillon calculée par `bench.puissance`) **avant** de lancer ;
2. graines dérivées, découpage par site ;
3. IC 95 % et taille d'effet ;
4. résultats bruts publiés, même négatifs.

### 6.1 Substitut par pièce (la limite la plus profonde, `j7_variance.md`)

- Changer le contrat `Substitut` : `evaluer` renvoie **un vecteur**, une valeur par pièce.
- Frank-Wolfe optimise une **scalarisation explicite** : moyenne pondérée par l'aire,
  minimum sur les pièces, ou part des pièces au-dessus d'un seuil. Le choix est un
  paramètre documenté.
- Critère : plus de pièces dégénérées dans `resultats/orientation/` (plus petit côté
  ≥ `largeur_min` réglementaire, pas 0,50 m).

### 6.2 Vraie vérité terrain d'éclairement

- Pipeline Radiance / Honeybee (extra `sim`) **hors CI**, produisant sDA et ASE annuels
  sur un échantillon de plans MSD et de plans générés (≥ 500, taille fixée en 6.0).
- Cet oracle sert à valider les substituts, à calibrer la prédiction conforme et à
  **réévaluer les plans choisis par l'optimiseur** (1.6).
- En complément, utiliser les étiquettes Swiss Dwellings **par pièce** déjà jointes.

### 6.3 Substitut qui bat les baselines triviales

- Baselines obligatoires : constante, aire au sol seule (aujourd'hui la meilleure), et
  analytique.
- Modèles : perceptron par pièce avec baies, puis modèle ensembliste ou à sorties
  quantiles, pour un **σ qui varie** (sans quoi le garde-fou μ − qσ ne fait rien, §5.5).
- Critère de succès pré-enregistré, par exemple : Spearman par pièce > celui de l'aire
  seule, IC disjoints, sur des sites disjoints.
- **Si le critère échoue** : le mode lumière reste « expérimental » dans le README, et
  l'article porte sur la légalisation (option B).

### 6.4 Garantie conforme sous sélection

- Mesurer empiriquement la couverture **sur les plans choisis par Frank-Wolfe**, réévalués
  par l'oracle de 6.2.
- Implémenter une procédure valide sous sélection : sélection conforme (Jin & Candès 2023)
  ou conforme pondéré avec sélection randomisée (Fannjiang et al. 2022).
- Critère : couverture mesurée ≥ 1 − α, avec son IC, dans les deux régimes ; largeur
  inférieure à un écart-type de la cible.

### 6.5 Légalisation : élargir la preuve

- **Second et troisième générateurs publics** (House-GAN++, baselines MSD, ou un modèle
  de langage produisant des boîtes), avec la même frontière de licence que HouseDiffusion.
- **Baselines de réparation** : L1 sans pavage (déjà faite), accrochage à une grille,
  réparation par MILP sur **toutes** les disjonctions (l'optimum global de référence, qui
  mesure le coût de l'ordre fixé, §5.2), et une méthode publiée de raffinement de plans.
- **Métriques de ressemblance** : IoU par pièce, préservation du graphe d'adjacence,
  préservation du programme, déplacement, et pas seulement le déplacement maximal.
- **Ablations** : sans pavage ; budget de réparation 0/4/8/16 ; `largeur_min` ; avec et
  sans porteurs ; ordre heuristique contre ordre MILP.
- Explorer la piste que l'audit juge la plus prometteuse : **injecter la contrainte de
  pavage dans le générateur** (guidage pendant l'échantillonnage ou projection aux
  derniers pas), puisque J8 montre que la légalisation a posteriori ne suffit pas.

### 6.6 Apprentissage actif (refait proprement)

- Graines corrigées, 30 répétitions, test apparié, taille calculée par `bench.puissance`.
- Conclure dans un sens ou dans l'autre, et le publier.

**Porte de sortie de la phase 6** : chaque hypothèse pré-enregistrée a une réponse
(confirmée ou réfutée) avec IC ; `make paper` régénère toutes les tables et figures
depuis les données brutes en une commande.

---

## Phase 7 : revue générale et correction des blocs

But : une passe complète « comme un relecteur externe », après les phases 1 à 6.

| # | Revue | Outil / skill | Critère |
|--:|---|---|---|
| 7.1 | Architecture complète, blueprint régénéré | `architecture-blueprint-generator` | Blueprint cohérent avec le code ; ADR à jour |
| 7.2 | Structure et design patterns, module par module | `python-design-patterns` | 0 Critique, 0 Majeur |
| 7.3 | Qualité, conventions §6, §7, §10 | `review-and-refactor` | 0 Critique, 0 Majeur |
| 7.4 | Typage et API | `python-expert` | Test utilisateur rejoué sans friction |
| 7.5 | Audit mathématique : chaque formule de `docs/formules/` confrontée au code | Relecture humaine et tests de propriétés | Chaque formule a un test qui la vérifie |
| 7.6 | Audit doc ↔ code | Test automatique des exemples + lecture | 0 écart |
| 7.7 | Revue de sécurité (lecture de fichiers DXF/IFC/JSON non fiables, zip) | `/security-review` | 0 Critique |
| 7.8 | **Ré-audit complet** avec la grille de `AUDIT.md` | Les 4 skills, comme pour l'audit initial | 10/10 sur chaque axe **dont le critère ne dépend que du travail** |

Chaque constat de 7.1 à 7.8 suit la séquence habituelle : `tdd` → `python-expert` →
`review-and-refactor`. On boucle jusqu'à ce que 7.8 soit vert.

---

## Phase 8 : publication open source

- [ ] Dépôt GitHub public **dès la fin de la phase 1** (pour lancer les 6 mois
      d'historique), puis travail en PR.
- [ ] Remplacer `ORG/archlux` et le DOI factice ; vrais auteurs avec ORCID dans
      `CITATION.cff` et `pyproject.toml`.
- [ ] `CODE_OF_CONDUCT.md`, `SECURITY.md`, modèles d'issue et de PR, `CODEOWNERS`.
- [ ] CI : Linux, Windows et macOS ; installation depuis le wheel ; exemples ; doc.
- [ ] PyPI par Trusted Publishing (vérifier que le nom est libre) ; Zenodo relié aux
      releases.
- [ ] Documentation publiée (GitHub Pages) ; frontière de licence HouseDiffusion (GPL)
      visible ; données non redistribuables documentées, avec le script qui les
      reconstruit.
- [ ] Version `1.0.0` **seulement** quand les phases 1 à 5 sont closes.
- [ ] Obtenir et documenter **au moins un usage tiers** (exigé par JOSS).

---

## Phase 9 : rédaction de l'article

### 9.1 Choix de l'article (décidé à la fin de la phase 6)

| Si… | Alors |
|---|---|
| 6.3 et 6.4 réussissent | Article complet « légalisation performantielle certifiée » : la thèse du README, maintenant démontrée |
| 6.3 échoue, 6.5 est solide | **Article B** : « la légalisation a posteriori ne suffit pas », avec 3 générateurs, baselines et ablations, plus le résultat de granularité en section |
| Dans tous les cas | **Article outil** JOSS après 6 mois d'historique et un usage tiers |

### 9.2 Exigences de qualité

- [ ] Chaque chiffre du texte provient d'un fichier de `resultats/` régénéré par
      `make paper` ; aucun chiffre recopié à la main.
- [ ] Chaque affirmation a son **domaine de validité** : ordre relatif fixé, tolérance ε,
      régime conforme, oracle utilisé.
- [ ] Section **Limites** reprise de `docs/limites.md` : c'est la force du projet.
- [ ] Section « menaces à la validité » : conditionnement synthétique, rectangles
      uniquement, un seul climat.
- [ ] Comparaison à l'état de l'art avec une recherche bibliographique systématique
      (légalisation en CAO de circuits, HouseDiffusion, House-GAN++, MSD, substituts
      d'éclairement, prédiction conforme sous sélection).
- [ ] Artefact de reproductibilité : image Docker ou environnement verrouillé, DOI
      Zenodo des données et du code, badge « artifact available ».
- [ ] **Relecture interne avec la grille d'un relecteur** : les 5 points de vigilance de
      l'audit §12, plus une lecture par une personne extérieure au projet.
- [ ] Soumission ciblée (option B : atelier CVPR/ICCV, CAADRIA, eCAADe, SimAUD ; option
      éclairement : Building and Environment, JBPS ; outil : JOSS, SoftwareX).

---

## Calendrier indicatif

| Semaines | Phases |
|---|---|
| S1 | Phase 0 |
| S2–S3 | Phase 1, dépôt public en fin de S3 |
| S4 | Phase 2 |
| S5 | Phase 3 |
| S6–S9 | Phase 4, avec la phase 6 lancée en parallèle (Radiance, second générateur) |
| S10–S12 | Phase 5 |
| S6–S22 | Phase 6 (expériences longues) |
| S23–S24 | Phase 7 |
| S25–S30 | Phase 9 (article) ; phase 8 continue (6 mois d'historique atteints vers S28) |

---

## Suivi

Tenir ce tableau à jour à chaque porte franchie.

| Phase | Statut | Porte franchie le | Commentaire |
|--:|---|---|---|
| 0 | **Terminée** | 2026-09-23 | 15 commits. 626 tests verts + 9 xfail stricts documentés (6 pages de doc, 2 garanties du mode performance, 1 incohérence de tolérances) : ce sont les tests d'entrée de la phase 1. Version `0.10.0.dev0` (0.9.0 déjà pris, 1.0.0 retirée). Revue `review-and-refactor` faite ; ses 18 constats corrigés, dont 1 critique (pages `docs/donnees/` jamais versionnées). |
| 1 | En cours | | Lots 1.1 à 1.6 terminés : 0 certificat mensonger, 0 plantage et 0 dépassement de budget dans tous les modes du banc ; pavage prouvé en rationnels, Farkas vérifié exactement ; chaque borne probabiliste dit son régime. Lot suivant : 1.7 (pièces en L). |
| 2 | À faire | | |
| 3 | À faire | | |
| 4 | À faire | | |
| 5 | À faire | | |
| 6 | À faire | | |
| 7 | À faire | | |
| 8 | À faire | | |
| 9 | À faire | | |
| E | En cours | | E0, E1, E9 (`solve`) et E10 (`certify.preuve` → `certify.proof`) faits. Fichiers touchés par chaque lot écrits en anglais. Lot suivant : E2, avec la réécriture du README en phase 1.8. |
