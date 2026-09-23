# JALON 2 — Légalisation géométrique classique

> **Prérequis : lire `ARCHITECTURE.md` d'abord.**
> Durée visée : 6 semaines. Livrable : un plan invalide entre, un plan valide + preuve sort.
> **Ce jalon suffit à un premier article publiable.** Aucune composante lumière ici.

---

## 0. Objectif et critère d'acceptation

**Objectif.** Implémenter `archlux.legalize(plan, ctx) -> Plan` qui rend le plan **valide le plus proche** de l'entrée.

**Critère d'acceptation unique — le jalon est terminé quand ce test passe :**

```python
@given(plan=plans_quelconques(), ctx=contextes())
@settings(max_examples=500, deadline=None)
def test_toute_sortie_est_valide(plan, ctx):
    assert archlux.legalize(plan, ctx).certificat.geometrie.valide
```

**Mesure à produire pour l'article :** taux de plans valides avant / après correction, sur les sorties de 3 modèles publics.

**Hors périmètre de ce jalon** (ne pas commencer) :
- géométries non rectangulaires (pièces en L) → jalon 6
- lumière, substitut, Frank-Wolfe → jalon 3
- prédiction conforme → jalon 5

---

## 1. Prérequis

- [ ] Jalon 1 terminé : `types.py` et `io/json_io.py` fonctionnent, aller-retour JSON testé
- [ ] `pip install -e ".[dev]"` fonctionne
- [ ] `pytest` passe (même à vide)
- [ ] CI verte

---

## 2. Étape 1 — Graphe de contraintes

**Fichier :** `src/archlux/geom/graphe.py`

### Ce que ça fait

Traduire « la pièce A est à gauche de la pièce B » en inégalité `x_A + w_A ≤ x_B`.

**Règle fondatrice :** pour chaque paire de pièces, **au moins une** séparation (gauche / droite / dessus / dessous) doit exister. Sans elle, le chevauchement est possible.

### Signature

```python
@dataclass(frozen=True)
class OrdreRelatif:
    horizontal: tuple[tuple[str, str], ...]   # (a, b) : a est à gauche de b
    vertical:   tuple[tuple[str, str], ...]   # (a, b) : a est en dessous de b

def construire_graphe(ordre: OrdreRelatif, pieces: list[str]) -> GrapheContraintes: ...
def reduction_transitive(g: GrapheContraintes) -> GrapheContraintes: ...
def deduire_ordre(plan: Plan) -> OrdreRelatif: ...   # depuis un plan proposé
```

### Tâches

- [ ] `deduire_ordre(plan)` — extraire l'ordre relatif d'un plan proposé (comparer les centres)
- [ ] `construire_graphe` — deux graphes orientés (`networkx.DiGraph`), un horizontal, un vertical
- [ ] Détecter les **cycles** → lever `OrdreIncoherent(cycle=[...])`
- [ ] Détecter les **paires non séparées** → lever `SeparationManquante(paire=(a, b))`
- [ ] `reduction_transitive` via `networkx.transitive_reduction`

### Pourquoi la réduction transitive n'est pas optionnelle

15 pièces → ~210 contraintes brutes → ~30 après réduction.
Le solveur est appelé 50 fois au jalon 3 : le gain se multiplie par 50.

### Tests

```python
def test_separation_simple():
    o = OrdreRelatif(horizontal=(("A","B"),), vertical=())
    g = construire_graphe(o, ["A","B"])
    assert ("A","B") in g.horizontal.edges

def test_cycle_detecte():
    o = OrdreRelatif(horizontal=(("A","B"),("B","A")), vertical=())
    with pytest.raises(OrdreIncoherent):
        construire_graphe(o, ["A","B"])

@given(ordre=ordres_valides())
def test_toute_paire_est_separee(ordre):
    g = construire_graphe(ordre, ordre.pieces)
    for a, b in itertools.combinations(ordre.pieces, 2):
        assert g.a_separation(a, b)

@given(ordre=ordres_valides())
def test_reduction_preserve_la_fermeture(ordre):
    complet = construire_graphe(ordre, ordre.pieces)
    reduit  = reduction_transitive(complet)
    assert complet.fermeture() == reduit.fermeture()
```

- [ ] Les 4 tests passent
- [ ] `pytest tests/unites/test_graphe.py -q` vert

---

## 3. Étape 2 — Polytope

**Fichier :** `src/archlux/geom/polytope.py`

### Ce que ça fait

Assembler le système `A x ≤ b` + `A_eq x = b_eq` + bornes.

### Signature

```python
@dataclass(frozen=True)
class Polytope:
    A: sparse.csr_matrix
    b: np.ndarray
    A_eq: sparse.csr_matrix
    b_eq: np.ndarray
    bornes: list[tuple[float, float]]
    index: dict[str, int]          # "sejour.x" -> 12
    origines: list[str]            # ligne i -> "separation sejour|cuisine"

def construire_polytope(ordre: OrdreRelatif, ctx: Contexte) -> Polytope: ...
```

### `origines` est OBLIGATOIRE

Sans ce champ, un prix dual est « le nombre de la ligne 47 » — inutilisable.
Avec lui, c'est « le mur porteur de l'axe 3 vous coûte 4,1 points ».
**Impossible à rattraper après coup sans reconstruire le module.**

### Variables (4 par pièce)

```
index["<piece>.x"], ["<piece>.y"], ["<piece>.w"], ["<piece>.h"]
```

### Contraintes à produire

- [ ] Séparation horizontale : `x_a + w_a - x_b ≤ 0` pour chaque arête de `g.horizontal`
- [ ] Séparation verticale : `y_a + h_a - y_b ≤ 0`
- [ ] Contour : `0 ≤ x_i`, `x_i + w_i ≤ W`, idem en y
- [ ] Largeurs minimales : `w_i ≥ ℓ_min`, `h_i ≥ ℓ_min` (via `bornes`)
- [ ] Structure conservée : lignes dans `A_eq` pour les murs porteurs
- [ ] Surfaces minimales : **PAS ICI** — reportées, traitées par coupes à l'étape 4
- [ ] Remplir `index` et `origines` (une entrée lisible par ligne)

### Tests

```python
@given(ordre=ordres_valides(), ctx=contextes())
def test_dimensions_coherentes(ordre, ctx):
    p = construire_polytope(ordre, ctx)
    assert p.A.shape[0] == len(p.origines)
    assert p.A.shape[1] == len(p.index)

@given(plan=plans_valides())
def test_un_plan_valide_est_dans_le_polytope(plan):
    p = construire_polytope(deduire_ordre(plan), CTX)
    assert p.contient(vectoriser(plan), tol=1e-9)

def test_origines_sont_lisibles():
    p = construire_polytope(ORDRE_T3, CTX)
    assert all(isinstance(o, str) and len(o) > 3 for o in p.origines)
```

- [ ] Les 3 tests passent
- [ ] Budget : construction < 5 ms pour 15 pièces (`pytest-benchmark`)

---

## 4. Étape 3 — Solveur LP

**Fichier :** `src/archlux/lmo/solveur.py`

### Ce que ça fait

Résoudre `min <c, x>` sur le polytope. **Ce module ne sait pas d'où vient `c`.**
C'est cette ignorance qui permettra de réutiliser le même solveur au jalon 3.

### Signature — la respecter exactement

```python
def resoudre(
    poly: Polytope,
    c: np.ndarray,
    *,
    depart: np.ndarray | None = None,     # warm start — prévoir dès maintenant
    coupes: list[Coupe] | None = None,
    duaux: bool = False,
) -> SolutionLP: ...

@dataclass(frozen=True)
class SolutionLP:
    x: np.ndarray
    valeur: float
    statut: Literal["optimal", "infaisable", "non_borne", "limite"]
    duaux: np.ndarray | None = None
    certificat_farkas: np.ndarray | None = None
    iterations: int = 0
    temps_ms: float = 0.0
```

> **Ne pas simplifier cette signature.** `depart` et `duaux` semblent inutiles au jalon 2 mais sont indispensables aux jalons 3 et 5. Les ajouter après oblige à restructurer l'interface pour faire circuler l'état.

### Tâches

- [ ] Backend `OR-Tools` GLOP (`pywraplp.Solver.CreateSolver("GLOP")`)
- [ ] Mapper `Polytope` → variables et contraintes du solveur
- [ ] Warm start : conserver la base, reprendre par simplexe dual
- [ ] Extraire les duaux quand `duaux=True`
- [ ] Sur `infaisable` : extraire le certificat de Farkas (variables duales du problème auxiliaire)
- [ ] Renseigner `temps_ms` et `iterations`

### Tests

```python
def test_lp_trivial():
    # une seule pièce, minimiser x → x = 0
    sol = resoudre(POLY_1_PIECE, c=np.array([1.,0.,0.,0.]))
    assert sol.statut == "optimal" and sol.x[0] == pytest.approx(0.0)

@given(ordre=ordres_valides(), c=vecteurs_objectifs())
def test_solution_est_admissible(ordre, c):
    p = construire_polytope(ordre, CTX)
    sol = resoudre(p, c)
    if sol.statut == "optimal":
        assert p.contient(sol.x, tol=1e-7)

def test_infaisable_produit_un_certificat():
    p = polytope_surcontraint()          # programme > enveloppe
    sol = resoudre(p, c=ZERO)
    assert sol.statut == "infaisable"
    assert sol.certificat_farkas is not None

def test_warm_start_est_plus_rapide(benchmark):
    p = construire_polytope(ORDRE_T3, CTX)
    froid = resoudre(p, C1)
    chaud = resoudre(p, C2, depart=froid.x)
    assert chaud.temps_ms < froid.temps_ms
```

- [ ] Les 4 tests passent
- [ ] Budget : LP à froid < 10 ms, à chaud < 3 ms (15 pièces)

---

## 5. Étape 4 — Coupes de surface

**Fichier :** `src/archlux/lmo/coupes.py`

### Le problème

`w × h ≥ 9` est une **multiplication** → non linéaire → GLOP ne sait pas la traiter.

### La solution

L'ensemble `{(w,h) : w,h > 0, wh ≥ a}` est **convexe**. On le remplace par ses tangentes :
au point `(w₀, h₀)` avec `w₀h₀ = a`, la tangente est `h₀·w + w₀·h ≥ 2a`.

```python
def coupe_surface(w0: float, h0: float, a_min: float) -> Coupe:
    """Tangente à l'hyperbole wh = a_min. Valide car l'ensemble est convexe."""
    return Coupe(coeffs={"w": h0, "h": w0}, borne_inf=2 * a_min)
```

### Boucle d'ajout

```
résoudre
tant que une surface est violée et coupes < MAX_COUPES :
    ajouter coupe_surface(w_courant, h_courant, a_min)
    résoudre à nouveau (warm start)
```

### Tâches

- [ ] `coupe_surface(w0, h0, a_min)`
- [ ] `surfaces_violees(x, poly, ctx) -> list[str]`
- [ ] Boucle d'ajout dans `resoudre`, avec `MAX_COUPES = 10` par pièce
- [ ] Avertissement `log.warning("coupe.limite", piece=...)` au-delà

### Tests

```python
@given(w0=st.floats(0.5, 10), h0=st.floats(0.5, 10))
def test_la_coupe_n_exclut_aucun_point_valide(w0, h0):
    """Une tangente ne doit jamais rejeter un (w,h) dont le produit suffit."""
    a = w0 * h0
    c = coupe_surface(w0, h0, a)
    for w, h in points_avec_produit_superieur(a, n=100):
        assert c.satisfait(w, h)

@given(ordre=ordres_valides())
def test_surfaces_minimales_respectees(ordre):
    sol = resoudre(construire_polytope(ordre, CTX), C_PROXIMITE)
    for piece in ordre.pieces:
        assert aire(sol, piece) >= CTX.referentiel.a_min(piece) - 1e-6
```

- [ ] Les 2 tests passent
- [ ] Vérifier : ≤ 3 coupes par pièce en pratique sur le corpus

---

## 6. Étape 5 — Vérification exacte

**Fichier :** `src/archlux/certify/preuve.py`

### Ce que ça fait

Vérifier, **indépendamment du solveur**, que le plan de sortie est valide.

> **Ne pas faire confiance au solveur.** La vérification doit être une implémentation
> séparée, naïve et lisible. Si le solveur a un bug, c'est elle qui l'attrape.

### Signature

```python
def verifier_exactement(plan: Plan, ctx: Contexte) -> PreuveGeometrique: ...

@dataclass(frozen=True)
class PreuveGeometrique:
    valide: bool
    chevauchement: bool
    jours: bool
    surfaces_ok: bool
    structure_preservee: bool
    deplacement_max: float
    violations: tuple[str, ...] = ()
```

### Tâches

- [ ] Chevauchement : toutes les paires, via `shapely` — `O(n²)`, assumé
- [ ] Jours : `unary_union(pieces).area == contour.area` à tolérance près
- [ ] Surfaces : `aire(p) ≥ a_min(type(p))` pour chaque pièce
- [ ] Structure : les murs porteurs de `ctx.structure` sont inchangés
- [ ] `violations` : messages lisibles, ex. `"chevauchement cuisine|sdb : 0,03 m²"`
- [ ] **Aucun champ de probabilité dans ce type** (voir `ARCHITECTURE.md` §6)

### Tests

```python
def test_detecte_un_chevauchement():
    p = plan_avec_chevauchement(0.03)
    assert verifier_exactement(p, CTX).chevauchement is True

def test_detecte_un_jour():
    assert verifier_exactement(plan_avec_jour(0.5), CTX).jours is True

@given(plan=plans_valides())
def test_un_plan_valide_passe(plan):
    assert verifier_exactement(plan, CTX).valide
```

- [ ] Les 3 tests passent

---

## 7. Étape 6 — API publique

**Fichier :** `src/archlux/api.py`

### Signature — prévoir `objective` dès maintenant

```python
def legalize(
    plan: Plan,
    ctx: Contexte,
    *,
    objective=None,            # None = proximité. Utilisé au jalon 3.
    budget: float | None = None,
) -> Plan: ...
```

> `objective=None` donne la légalisation classique.
> Au jalon 3, `objective=Daylight(...)` donnera la légalisation performantielle.
> **Une seule fonction, un paramètre qui change** — c'est la thèse du projet dans l'API.

### Pipeline

```python
def legalize(plan, ctx, *, objective=None, budget=None):
    ordre = deduire_ordre(plan)
    poly  = construire_polytope(ordre, ctx)
    c     = gradient_distance(vectoriser(plan)) if objective is None else ...
    sol   = resoudre(poly, c, duaux=True)
    if sol.statut == "infaisable":
        raise Infaisable(certificat=sol.certificat_farkas, poly=poly)
    q     = devectoriser(sol.x, plan)
    preuve = verifier_exactement(q, ctx)
    if not preuve.valide:
        raise InvariantViole(preuve.violations)   # jamais silencieux
    return replace(q, certificat=Certificat(geometrie=preuve, ...))
```

### Le piège de la valeur absolue

`min Σ |x - x̂|` n'est **pas linéaire**. Introduire une variable d'écart `e` par variable :

```
e ≥ x - x̂
e ≥ x̂ - x
minimiser Σ e
```

- [ ] Variables d'écart implémentées
- [ ] `gradient_distance` produit le bon vecteur `c`
- [ ] `__init__.py` n'exporte que `legalize`, `Plan`, `Contexte`, les exceptions

---

## 8. Étape 7 — Mesure pour l'article

**Fichier :** `experiences/j2_taux_validite.py` (< 50 lignes)

- [ ] Télécharger les sorties de 3 modèles publics (HouseDiffusion, GSDiff, DiffPlanner)
- [ ] Mesurer le taux de plans valides **avant** correction
- [ ] Appliquer `legalize`, mesurer le taux **après** (doit être 100 %)
- [ ] Mesurer le déplacement maximal, moyen, et le 95ᵉ centile
- [ ] Mesurer le temps par plan
- [ ] Écrire les résultats **bruts** dans `resultats/j2_brut.csv` avant toute agrégation

```
modele,plan_id,valide_avant,valide_apres,deplacement_max_m,temps_ms,seed
housediffusion,000123,False,True,0.18,12.4,17
```

---

## 9. Checklist finale du jalon

### Code

- [ ] `geom/graphe.py` — graphe + réduction transitive + détection de cycles
- [ ] `geom/polytope.py` — assemblage + `index` + `origines`
- [ ] `lmo/solveur.py` — LP + warm start + duaux + Farkas
- [ ] `lmo/coupes.py` — tangentes de surface
- [ ] `certify/preuve.py` — vérification indépendante du solveur
- [ ] `api.py` — `legalize()` avec `objective=None`

### Tests

- [ ] Le test d'acceptation (§0) passe sur 500 cas
- [ ] Test d'idempotence : `legalize(plan_valide) == plan_valide`
- [ ] Test d'infaisabilité : programme trop gros → `Infaisable` avec certificat non vide
- [ ] `test_le_noyau_n_importe_pas_torch` passe
- [ ] Couverture > 85 % sur `geom/`, `lmo/`, `certify/`

### Performance

- [ ] Polytope < 5 ms · LP froid < 10 ms · LP chaud < 3 ms · total < 20 ms

### Qualité

- [ ] `ruff check .` propre
- [ ] `mypy src/` propre
- [ ] CI verte sur Python 3.11, 3.12, 3.13
- [ ] `CHANGELOG.md` : entrée `0.1.0`
- [ ] Version étiquetée `v0.1.0` + archivage Zenodo

### Article

- [ ] `resultats/j2_brut.csv` produit
- [ ] Figure : un plan avant / après, côte à côte
- [ ] Tableau : taux de validité et déplacement, par modèle

---

## 10. Erreurs fréquentes à ce jalon

| Symptôme | Cause | Correctif |
|---|---|---|
| Solveur lent (> 50 ms) | Réduction transitive oubliée | Appliquer `reduction_transitive` |
| Surfaces non respectées | Contrainte `w·h` passée telle quelle à GLOP | Utiliser les coupes tangentes |
| Résultat non déterministe | Ordre d'itération sur un `set` | Trier explicitement les identifiants |
| `deplacement_max` énorme | Valeur absolue mal linéarisée | Vérifier les deux contraintes d'écart |
| Chevauchements résiduels | Une paire sans séparation | `test_toute_paire_est_separee` |
| Duaux tous nuls | `duaux=True` oublié | Passer le flag |

---

## 11. Ce qu'il ne faut PAS faire à ce jalon

- [ ] ❌ Commencer les pièces en L → jalon 6
- [ ] ❌ Toucher à la lumière → jalon 3
- [ ] ❌ Simplifier la signature de `resoudre` → coût élevé au jalon 3
- [ ] ❌ Omettre `origines` dans `Polytope` → diagnostic dual impossible plus tard
- [ ] ❌ Faire confiance au solveur pour la vérification → implémentation séparée obligatoire

---

## 12. Prochaine étape

Une fois cette checklist complète : **`MILESTONE-3.md`** — substitut analytique, statistiques circulaires et boucle de Frank-Wolfe. La chaîne complète tournera alors **sans aucun apprentissage**, ce qui valide l'architecture avant toute dépense de simulation.
