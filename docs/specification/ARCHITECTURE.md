# ARCHITECTURE — archlux

> Contexte pour agents de code (Cursor, Claude Code, etc.).
> **Lire ce fichier avant toute modification.** Les règles ci-dessous sont contraignantes.

---

## 1. Objet du projet

`archlux` corrige les plans d'architecture produits par des modèles génératifs :

1. **rendre le plan géométriquement valide** (aucun chevauchement, aucun jour, surfaces minimales respectées) ;
2. **choisir, parmi toutes les corrections valides, celle qui préserve le mieux la lumière naturelle**.

La sortie porte **deux garanties de natures différentes** :

| Garantie | Nature | Vérification |
|---|---|---|
| Géométrique | **exacte**, démontrable | inspection finie, `O(n²)` |
| Performance lumineuse | **probabiliste** (couverture ≥ 1−α) | prédiction conforme |

**Ne jamais les confondre, ni dans le code, ni dans les types, ni dans les messages.**

---

## 2. Principe fondateur

> Le générateur décide **l'ordre** des pièces.
> Le solveur décide **les dimensions**.
> Le réseau de neurones ne fait **que** fournir une direction (gradient).

Conséquence : l'oracle linéaire de Frank-Wolfe **est** le solveur de légalisation.
Un seul solveur, deux vecteurs objectifs.

```python
# légalisation classique
sol = lmo.resoudre(poly, c=gradient_distance(Q_propose))

# légalisation performantielle (1 itération Frank-Wolfe)
sol = lmo.resoudre(poly, c=-substitut.gradient(Q, orientation), depart=Q)
```

**Oracle d'éclairement.** Le noyau ne connaît qu'un `Substitut` déterministe :
`SubstitutAnalytique`, `SimulateurExact` (split-flux BRE, **vérité terrain
de la CI**), `SubstitutAppris`. Un moteur de lancer de rayons (Radiance) est **hors
chemin critique** : extra `sim` vide, jamais importé par le noyau, jamais exigé par
la CI ni par les jalons 5–6. Il peut se brancher plus tard derrière
`light.simulateur` sans changer le protocole. La garantie lumineuse du jalon 5
porte sur **cet oracle gelé**, pas sur un sDA LM-83.

---

## 3. Couches

```
ENTRÉES : plan proposé · structure porteuse · orientation · programme
   │
   ▼
[1] geom      modélisation → polytope (A, b)        PUR, DÉTERMINISTE
   │
   ├──────────────┬──────────────────────────┐
   ▼              ▼                          ▼
[2a] lmo       solveur LP, objectif      [2b] light   substitut
     paramétrable      PUR                    valeur / gradient / σ   APPRIS
   │              │                          │
   └──────────────┴────────► [3] solve  Frank-Wolfe   PUR
                                   │
                                   ▼
                             [4] certify   preuve + borne + duaux   PUR
                                   │
                                   ▼
              SORTIE : plan valide + certificat + diagnostic dual
```

**3 couches sur 4 sont pures et déterministes.** Une seule est apprise, isolée derrière un protocole.

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
| Tolerances | declared once in `archlux/tolerances.py`, never as inline literals |

---

## 8. Définition de « terminé » pour toute modification

- [ ] `pytest` passe (unitaires + propriétés)
- [ ] `ruff check .` et `mypy src/` propres
- [ ] Aucune nouvelle dépendance dans le noyau
- [ ] Si l'API publique change : `CHANGELOG.md` mis à jour
- [ ] Si un invariant est ajouté : un test **par propriété** l'accompagne
- [ ] Les budgets de performance du §9 sont respectés

---

## 9. Budgets de performance (contrats, testés en CI)

| Opération | Budget | Référence |
|---|---|---|
| Construction du polytope | < 5 ms | 15 pièces |
| LP à froid | < 10 ms | 15 pièces |
| LP à chaud (`depart=`) | < 3 ms | 15 pièces |
| Légalisation classique complète | < 20 ms | 15 pièces |
| Légalisation performantielle | < 500 ms | 15 pièces, 50 itérations |
| Certification | < 5 ms | — |

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

## 11. Arborescence cible

```
archlux/
├── pyproject.toml
├── src/archlux/
│   ├── __init__.py          # interface publique UNIQUEMENT
│   ├── types.py
│   ├── geom/{graphe,polytope}.py
│   ├── lmo/{solveur,coupes}.py
│   ├── solve/{frank_wolfe,trace}.py
│   ├── light/{protocole,analytique,appris,base,jetons,simulateur,validation}.py
│   ├── orient/circulaire.py
│   ├── data/{decoupage,dedup,synthese}.py
│   ├── uq/{conforme,gestion,derive}.py
│   ├── certify/{preuve,borne,dual,rapport}.py
│   ├── bench/
│   └── io/json_io.py
├── tests/{unites,proprietes,references}/
├── benchmarks/
└── experiences/            # scripts jetables, < 50 lignes, API publique seulement
```

**Règle :** un script dans `experiences/` de plus de 50 lignes signale une fonction manquante dans la bibliothèque.

---

## 12. Ordre d'implémentation

| Jalon | Contenu | Livrable |
|---|---|---|
| 1 | `types`, `io` | aller-retour JSON |
| **2** | **`geom`, `lmo`, `certify.preuve`** | **légalisation classique — voir `MILESTONE-2.md`** |
| **3** | **`light.analytique`, `orient`, `solve`** | **légalisation performantielle sans apprentissage — `MILESTONE-3.md`** |
| 4 | `light.appris`, `light.validation` | substitut entraîné + validation du gradient contre `SimulateurExact` (Radiance) — `MILESTONE-4.md` |
| 5 | `uq`, `certify.borne`, `certify.dual` | certificat complet — `MILESTONE-5.md` |
| 6 | non-Manhattan, actif, export IFC | v1.0 — `MILESTONE-6.md` |
