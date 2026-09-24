# ARCHITECTURE — archlux

> Contexte pour agents de code (Cursor, Claude Code, etc.).
> **Lire ce fichier avant toute modification.** Les règles ci-dessous sont contraignantes.

---

## 1. Objet du projet

`archlux` corrige les plans d'architecture produits par des modèles génératifs :

1. **rendre le plan géométriquement valide** (aucun chevauchement, aucun jour, surfaces
   minimales respectées, chaque pièce du bon côté des murs porteurs, déplacement borné
   par `budget`) ;
2. **améliorer la lumière naturelle sans quitter cette validité** : parmi les plans
   valides qui **gardent l'ordre relatif proposé** (une seule cellule de l'espace des
   plans : contacts figés, budget de déplacement), Frank-Wolfe cherche un meilleur
   point pour le substitut. Il rend un point stationnaire, pas l'optimum global, et
   n'explore jamais les autres ordres relatifs.

La sortie porte **deux garanties de natures différentes** :

| Garantie | Nature | Vérification |
|---|---|---|
| Géométrique | **exacte** sur le modèle (rectangles axés) | `certify.proof.verify_exactly` : arithmétique rationnelle sur contour rectangulaire axé (seule tolérance : `SNAP_M` sur les longueurs), GEOS avec tolérances déclarées sinon ; infaisabilité par certificat de Farkas vérifié exactement, **pour l'ordre relatif proposé** |
| Performance lumineuse | **probabiliste** | prédiction conforme ; couverture ≥ 1−α **seulement** en régime `"exchangeable"`. Un plan choisi par l'optimiseur est en régime `"selected"` : couverture **non** garantie (`BornePerformance.regime`) |

**Ne jamais les confondre, ni dans le code, ni dans les types, ni dans les messages.**

---

## 2. Principe fondateur

> Le générateur décide **l'ordre** des pièces.
> Le solveur décide **les dimensions**.
> Le réseau de neurones ne fait **que** fournir une direction (gradient).

Conséquence : l'oracle linéaire de Frank-Wolfe **est** le solveur de légalisation.
Un seul solveur, deux vecteurs objectifs.

```text
# pseudo-code (vrais appels : lmo.coupes.resoudre_avec_surfaces, solve.frank_wolfe)
# légalisation classique : épigraphe L1 autour du plan proposé
x = lmo.resoudre(poly_l1, c=gradient_distance(x_propose))

# légalisation performantielle (1 itération Frank-Wolfe), démarrage à chaud
s = lmo.resoudre(poly_fw, c=-substitut.gradient(x_k, orientation), depart=x_k)
```

**Oracle d'éclairement.** Le noyau ne connaît que le protocole `Substitut`.
Implémentations livrées : `SubstitutAnalytique` (formes fermées), `SplitFluxOracle`
(analytique + split-flux BRE : **oracle gelé** de la CI, une forme fermée, ni une
simulation ni une vérité terrain), `SubstitutDense` (perceptron `numpy`) et
`SubstitutAppris` (qui refuse les poids `.pt` : le transformeur n'existe pas). Un moteur
de lancer de rayons (Radiance) est **hors chemin critique** : extra `sim` vide, jamais
importé par le noyau, jamais exigé par la CI ni par les jalons 5–6. Il peut se brancher
plus tard derrière le même protocole. La garantie lumineuse du jalon 5 porte sur **cet
oracle gelé**, pas sur un sDA LM-83.

---

## 3. Couches

```
ENTRÉES : plan proposé · structure porteuse · orientation · programme
   │
   ▼
[1] geom      modélisation → polytope (A, b)        DÉTERMINISTE
   │
   ├──────────────┬──────────────────────────┐
   ▼              ▼                          ▼
[2a] lmo       solveur LP, objectif      [2b] light   substitut
     paramétrable (cache GLOP)               valeur / gradient / σ   APPRIS
   │              │                          │
   └──────────────┴────────► [3] solve  Frank-Wolfe   DÉTERMINISTE
                                   │
                                   ▼
                             [4] certify   preuve + borne + duaux   DÉTERMINISTE
                                   │
                                   ▼
              SORTIE : plan valide + certificat + diagnostic dual
```

**Toutes les couches sont déterministes** (mêmes entrées, même sortie) ; une seule est
apprise, isolée derrière un protocole. Elles ne sont pas toutes **pures** : `lmo` garde
un cache global mutable de modèles GLOP (au plus 4, `lmo.solveur._CACHE`, ADR-8 du
blueprint) pour le démarrage à chaud de Frank-Wolfe. Ce cache change le temps, jamais
le résultat ; `lmo.solveur.vider_cache` le vide, et les tests de budget le vident avant
de mesurer un LP à froid.

---

## 4. Modules

| Module | Responsabilité unique | Appris ? |
|---|---|---|
| `types` | `Plan`, `Piece`, `Ouverture`, `Mur`, `Contexte`, `Certificat` | non |
| `geom` | ordre relatif → graphe de contraintes → polytope | non |
| `lmo` | résoudre `min <c,x>` sur le polytope. **Ignore l'origine de `c`** | non |
| `solve` | Frank-Wolfe (+ away-steps, warm start, coupes) | non |
| `light` | protocole `Substitut` : `evaluer`, `gradient`, `incertitude` | **oui** |
| `orient` | encodage et statistiques circulaires | non |
| `uq` | calibration conforme, contrôle de dérive | non |
| `active` | sélection de plans à simuler (incertitude × densité) | non |
| `export` | IFC / DXF, pathologies, taux de survie (Wilson) | non |
| `feasibility` | existence d'un plan valide (Farkas), sans lumière | non |
| `certify` | vérification exacte + borne + traduction des duaux | non |
| `bench` | protocole, graines, manifestes, run/report/stats | non |
| `data` | corpus, dédup, découpage figé | non |

---

## 5. Règles de dépendance (contraignantes)

```
types   ← tout le monde
geom    ← types
lmo     ← types, geom
solve   ← types, geom, lmo, PROTOCOLE light (jamais l'implémentation)
light   ← types, orient
uq      ← types
data    ← types, uq, orient, geom   (chargeurs de corpus : redressement + decoupe)
active  ← types, light.protocole, uq
export  ← types, erreurs
feasibility ← types, erreurs, api
certify ← types, geom, uq
bench   ← tout
```

**INTERDIT :**

- [ ] `geom`, `lmo`, `solve`, `certify` **ne doivent jamais importer `torch`**
- [ ] `lmo` ne doit jamais importer `light`
- [ ] `light` ne doit jamais importer `geom`, `lmo` ou `solve`
- [ ] `active` n'importe aucune implémentation `light.*` (seulement le protocole)
- [ ] `export` n'importe ni `geom` ni `certify` (annexe certificat via `Plan.certificat`)
- [ ] `feasibility` n'importe ni `light` ni `uq` (aucune promesse de performance)
- [ ] aucun module ne doit importer `bench`
- [ ] `data` peut lire `geom` et `orient` (chargeurs de corpus **uniquement**),
      jamais `lmo`, `solve` ni `light` : il produit des entrees, il ne resout rien

Test automatisé qui garde cette règle :

```python
def test_le_noyau_n_importe_pas_torch():
    import subprocess, sys
    code = "import archlux, sys; assert 'torch' not in sys.modules"
    assert subprocess.run([sys.executable, "-c", code]).returncode == 0
```

---


## 6. Modèle de données — invariants

```python
@dataclass(frozen=True, slots=True)
class Piece:
    id: str; type: str
    x: float; y: float; w: float; h: float      # mètres

@dataclass(frozen=True, slots=True)
class Ouverture:
    id: str
    mur_id: str            # ← relatif à un mur
    s: float               # abscisse relative ∈ [0,1]
    largeur_rel: float     # ∈ ]0,1]
    hauteur_allege: float = 1.00
    hauteur_linteau: float = 2.15

@dataclass(frozen=True, slots=True)
class Plan:
    pieces: tuple[Piece, ...]
    murs: tuple[Mur, ...]
    ouvertures: tuple[Ouverture, ...]
    contour: tuple[tuple[float, float], ...]
    certificat: "Certificat | None" = None
```

**Règles absolues :**

- [ ] Tous les types sont `frozen=True` — **jamais de mutation en place**
- [ ] La position **absolue** d'une ouverture n'est **jamais stockée**, toujours dérivée
- [ ] Un plan légalisé porte **toujours** son certificat
- [ ] `PreuveGeometrique` n'a **aucun** champ de probabilité
- [ ] `BornePerformance` porte **toujours** `couverture` et `n_calibration`

---

## 7. Conventions

| Point | Règle |
|---|---|
| Unités | mètres, m², degrés (azimut) |
| Origine | coin bas-gauche du contour, axe y vers le nord géographique |
| Graines | argument `seed: int` **obligatoire, sans défaut**, sur toute fonction qui échantillonne |
| Métriques | rendent **valeur + intervalle**, jamais un scalaire nu |
| Erreurs | exceptions typées (`OrdreIncoherent`, `Infaisable`, `InvariantViole`) — jamais `Exception` |
| Journaux | `structlog`, journalisation structurée, jamais de texte libre |
| Style | `ruff check` + `ruff format` + `mypy --strict` sur `src/` |
| Language | **English** for code, API, docstrings, messages, tests and documentation. New code is English now; existing French is migrated batch by batch ([ADR 0001](../adr/0001-english-first.md), [glossary](../glossary.md)) |
| Tolerances | target rule, enforced from PLAN.md 1.5: declared once in `archlux/tolerances.py`, never as inline literals |

---

## 8. Définition de « terminé » pour toute modification

- [ ] `pytest` passe (unitaires + propriétés)
- [ ] `ruff check .` et `mypy src/` propres
- [ ] Aucune nouvelle dépendance dans le noyau
- [ ] Si l'API publique change : `CHANGELOG.md` mis à jour
- [ ] Si un invariant est ajouté : un test **par propriété** l'accompagne
- [ ] Les budgets de performance du §9 sont respectés

---

## 9. Budgets de performance (contrats, mesurés en CI)

| Opération | Budget | Référence |
|---|---|---|
| Construction du polytope | < 5 ms | 15 pièces |
| LP à froid | < 10 ms | 15 pièces |
| LP à chaud (`depart=`) | < 3 ms | 15 pièces |
| Légalisation classique complète | < 20 ms | 15 pièces |
| Légalisation performantielle | < 500 ms | 15 pièces, 50 itérations au plus |
| Certification | < 5 ms | 15 pièces |

**Ce qui est mesuré, et ce qui ne l'est pas.** `benchmarks/test_budgets.py` (job CI
`budgets`, `pytest -m budget --benchmark-only`) mesure ces budgets sur **le cas le plus
favorable** : une grille 5 × 3 de pièces déjà valide, sans mur porteur, sans pavage,
substitut analytique. S'y ajoutent, depuis le lot 1.2, le mode performantiel avec des
surfaces minimales serrées (15 pièces) et un test d'échelle à 15, 50 et 100 pièces. Aucun
budget ne couvre une entrée bruitée, `pavage=True` ni les murs porteurs : pour ces cas,
le banc `benchmarks/guarantees/` relève des temps médians (environ 5 ms en classique,
15 à 20 ms en performantiel sur 200 scénarios) sans en faire un contrat. Sous
`--benchmark-disable`, un budget non mesuré est **ignoré** (skip), pas validé.

---

## 10. Anti-patterns à refuser en revue

| Anti-pattern | Pourquoi c'est fatal |
|---|---|
| Image / raster en entrée du substitut | Gradient nul presque partout → optimiseur aveugle → **projet impossible** |
| Coordonnées absolues pour les ouvertures | Désynchronisation murs/fenêtres |
| `lmo` qui connaît la lumière | Casse la réutilisation du solveur, cœur de l'architecture |
| Jeu de calibration lu à l'entraînement | **Garantie conforme fausse, et rien ne le signale** |
| Métrique rendant un scalaire nu | Viole le principe « aucune valeur sans incertitude » |
| Mutation d'un `Plan` | Les types sont gelés ; contourner = bogue |
| `np.quantile(scores, 0.90)` en conforme | Il faut `ceil((n+1)*(1-α))/n` — correction d'échantillon fini |
| LP sans `depart=` dans la boucle FW | ×3 à ×5 de temps perdu |

---

## 11. Arborescence

État du dépôt (lot 1.8). Les noms français sont migrés lot par lot (ADR 0001) ; les
anciens noms publics restent en alias dépréciés jusqu'à la 1.0.0.

```
archlux/
├── pyproject.toml
├── src/archlux/
│   ├── __init__.py          # interface publique UNIQUEMENT
│   ├── _version.py          # source unique de la version
│   ├── api.py               # legalize
│   ├── erreurs.py           # exceptions typées
│   ├── tolerances.py        # registre des tolérances numériques
│   ├── types.py
│   ├── geom/{graphe,polytope,pavage,rectilineaire,diagnostic}.py
│   ├── lmo/{solveur,coupes}.py
│   ├── solve/{frank_wolfe,trace}.py
│   ├── light/{protocole,analytique,appris,base,jetons,objectif,simulateur,validation}.py
│   ├── orient/circulaire.py
│   ├── uq/{conforme,gestion,derive,fiabilite}.py
│   ├── certify/{proof,farkas,borne,dual,rapport}.py   # preuve.py : alias dépréciés
│   ├── feasibility/__init__.py
│   ├── active/{boucle,densite,selection}.py
│   ├── data/{chargeurs,corruption,decoupage,dedup,imputation,synthese}.py
│   ├── export/{ifc,dxf,svg,pathologie,survie,wilson}.py
│   ├── bench/{graines,manifeste,protocole,rapport,run,stats}.py
│   └── io/json_io.py
├── tests/{unites,proprietes,references,docs}/   # + checkers.py, test_dependances.py,
│                                                #   test_hygiene.py, test_language.py
├── benchmarks/{test_budgets.py,guarantees/}
├── experiences/            # scripts d'expérience (jalons 2 à 9)
├── resultats/              # résultats bruts et tables publiées
├── scripts/                # préparation des données, étiquetage par l'oracle gelé
└── splits/v1/              # découpage figé
```

**Règle :** un script dans `experiences/` de plus de 50 lignes signale une fonction
manquante dans la bibliothèque. Elle n'est pas tenue aujourd'hui (`j8_generation.py` :
443 lignes ; onze scripts sur treize dépassent 50 lignes) : dette connue.

---

## 12. Ordre d'implémentation

| Jalon | Contenu | Livrable |
|---|---|---|
| 1 | `types`, `io` | aller-retour JSON |
| **2** | **`geom`, `lmo`, `certify.proof`** | **légalisation classique — voir `MILESTONE-2.md`** |
| **3** | **`light.analytique`, `orient`, `solve`** | **légalisation performantielle sans apprentissage — `MILESTONE-3.md`** |
| 4 | `light.appris`, `light.validation` | substitut entraîné + validation du gradient contre `SplitFluxOracle` (forme fermée split-flux) — `MILESTONE-4.md` |
| 5 | `uq`, `certify.borne`, `certify.dual` | certificat complet — `MILESTONE-5.md` |
| 6 | pièces en L (fusions de rectangles), actif, export IFC ; **le non-Manhattan n'est pas livré** (un porteur oblique lève `UnsupportedInput`) | `MILESTONE-6.md` |
