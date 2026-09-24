# JALON 3 — Légalisation performantielle sans apprentissage

> **Note (0.10, ADR 0001).** This historical specification keeps the names of its time:
> `ResultatFW` is now `FrankWolfeResult`, and `Trace.iteres` / `objectif` / `ecarts` are
> `iterates` / `values` / `gaps`. The old `Trace` names still work, as deprecated aliases,
> so the snippets below run unchanged.

> **Prérequis : `ARCHITECTURE.md`, `DOCUMENTATION.md`, jalon 2 terminé.**
> Durée visée : 5 semaines.
> **Jalon le plus important du projet, et le plus sous-estimé.**

---

## 0. Objectif et critère d'acceptation

**Objectif.** Faire tourner la chaîne complète — polytope → Frank-Wolfe → oracle → certificat —
avec un modèle de lumière en **formules fermées**, sans aucun apprentissage.

**Pourquoi maintenant.** Ce jalon valide l'architecture entière — le flux, les interfaces,
la boucle, le démarrage à chaud, les coupes — **avant d'avoir dépensé une heure de
simulation ou d'entraînement**. Si la conception est mauvaise, on le découvre ici, au
troisième mois, pas au dix-huitième.

**Critère d'acceptation — le jalon est terminé quand ces trois tests passent :**

```python
@given(plan=plans_quelconques())
def test_tous_les_iteres_sont_valides(plan):
    r = ax.legalize(plan, CTX, objective=ANALYTIQUE, trace=True)
    assert all(POLY.contient(x) for x in r.trace.iteres)

@given(plan=plans_quelconques())
def test_objectif_monotone(plan):
    r = ax.legalize(plan, CTX, objective=ANALYTIQUE, trace=True)
    assert est_croissante(r.trace.objectif, tol=1e-9)

@given(theta=st.floats(0, 360))
def test_orientation_circulaire(theta):
    a = ax.legalize(PLAN, ctx_avec(theta),       objective=ANALYTIQUE)
    b = ax.legalize(PLAN, ctx_avec(theta + 360), objective=ANALYTIQUE)
    assert np.allclose(a.vecteur(), b.vecteur(), atol=1e-6)
```

**Hors périmètre** (ne pas commencer) : réseau de neurones, données de simulation,
prédiction conforme, pièces en L.

---

## 1. Prérequis

- [ ] `ax.legalize(plan, ctx)` fonctionne (jalon 2)
- [ ] `lmo.resoudre` accepte déjà `depart=` et `duaux=`
- [ ] `Polytope.origines` est renseigné
- [ ] CI verte, couverture > 85 % sur `geom/`, `lmo/`, `certify/`

---

## 2. Étape 1 — Statistiques circulaires

**Fichier :** `src/archlux/orient/circulaire.py`

### Pourquoi d'abord

L'orientation entre partout ensuite. La traiter comme un nombre linéaire fait que
359° et 1° sont perçus comme éloignés — **bogue invisible qu'aucune inspection visuelle
ne révèle**.

### Signatures

```python
def encode(deg: float, harmoniques: int = 3) -> np.ndarray:
    """(cos θ, sin θ, cos 2θ, sin 2θ, ...). JAMAIS le degré brut."""

def moyenne_circulaire(degres: Sequence[float]) -> float: ...
def variance_circulaire(degres: Sequence[float]) -> float: ...
def test_rayleigh(degres: Sequence[float]) -> tuple[float, float]:  # (R, p)
def regression_circulaire_lineaire(theta: np.ndarray, y: np.ndarray) -> Resultat: ...
def stratifier(donnees, par_orientation: int = 8) -> dict[str, np.ndarray]: ...
```

### Tâches

- [ ] `encode` avec harmoniques (défaut 3 → vecteur de dimension 6)
- [ ] Moyenne et variance circulaires (via somme de vecteurs unitaires)
- [ ] Test de Rayleigh (uniformité sur la rose des vents)
- [ ] Régression circulaire-linéaire : `y ~ a·cos θ + b·sin θ + c`
- [ ] `stratifier` — découpe en 8 secteurs de 45°

### Tests

```python
def test_moyenne_circulaire_franchit_zero():
    """Le piège classique : la moyenne de 350 et 10 vaut 0, pas 180."""
    assert moyenne_circulaire([350, 10]) == pytest.approx(0.0, abs=0.1)

@given(deg=st.floats(0, 360))
def test_encode_periodique(deg):
    assert np.allclose(encode(deg), encode(deg + 360), atol=1e-9)

def test_rayleigh_detecte_concentration():
    _, p = test_rayleigh([10, 12, 11, 9, 13])      # tous au nord
    assert p < 0.01
```

- [ ] Les 3 tests passent

---

## 3. Étape 2 — Le protocole `Substitut`

**Fichier :** `src/archlux/light/protocole.py`

### Le contrat — ne jamais l'élargir

```python
class Substitut(Protocol):
    """Contrat minimal. Toute implémentation le respectant est acceptée
    par le noyau — y compris un modèle analytique sans apprentissage."""

    def evaluer(self, plan: Plan, ctx: Contexte) -> Indicateurs: ...
    def gradient(self, plan: Plan, ctx: Contexte) -> np.ndarray: ...
    def incertitude(self, plan: Plan, ctx: Contexte) -> np.ndarray: ...


@dataclass(frozen=True)
class Indicateurs:
    sda: float          # autonomie lumineuse, ↑ mieux
    ase: float          # éblouissement, ↓ mieux
    udi: float
    vue: float

    def scalariser(self, poids: dict[str, float]) -> float:
        """sDA et ASE vont en sens contraire : le poids doit être VISIBLE."""
```

### Tâches

- [ ] `Protocol` avec les 3 méthodes, **et rien de plus**
- [ ] `Indicateurs` avec `scalariser(poids)` — le compromis sDA/ASE explicite
- [ ] Un test qui vérifie que `SubstitutAnalytique` satisfait le protocole (`isinstance`)

> **Trois méthodes, pas quatre.** Chaque méthode ajoutée au protocole devra être
> implémentée par le simulateur exact et par le réseau. Un protocole étroit est ce qui
> rend les trois implémentations interchangeables.

---

## 4. Étape 3 — Le substitut analytique

**Fichier :** `src/archlux/light/analytique.py`

### Ce que ça fait

Prédire l'éclairement par des formules fermées : profondeur utile depuis la baie,
largeur de baie, orientation. **Grossier, mais sans apprentissage donc sans dérive,
sans calibration, sans données.**

```python
class SubstitutAnalytique:
    """Modèle de lumière en formes fermées.

    Sert de : point de départ (jalon 3), référence (le modèle appris doit
    faire mieux), repli (si le gradient appris est inexploitable, jalon 4).
    """

    FACTEUR_PROFONDEUR = 2.5      # règle usuelle : profondeur utile ≈ 2,5 × linteau

    def evaluer(self, plan, ctx):
        total = 0.0
        for piece in plan.pieces:
            for ouv in ouvertures_de(piece, plan):
                profondeur_utile = self.FACTEUR_PROFONDEUR * ouv.hauteur_linteau
                penetration = min(profondeur(piece, ouv), profondeur_utile)
                f_orient = self._facteur_orientation(ouv, ctx.orientation)
                total += penetration * largeur_absolue(ouv, plan) * f_orient
        return Indicateurs(sda=total / plan.aire_totale(), ase=..., udi=..., vue=...)

    def gradient(self, plan, ctx):
        """Dérivées analytiques, ou différences finies sur le vecteur de plan."""

    def incertitude(self, plan, ctx):
        """Constante. Le modèle analytique n'a pas d'incertitude apprise."""
        return np.full(4, self.SIGMA_FIXE)
```

### Le facteur d'orientation

La règle de profondeur utile **dépend de l'exposition** — le facteur varie
sensiblement entre nord et sud. C'est ce qui rend le résultat dépendant du nord,
et donc l'expérience Q3 possible dès ce jalon.

- [ ] `_facteur_orientation` implémenté avec une table par secteur (8 secteurs)
- [ ] Documenter la source de la règle et sa marge d'incertitude

### Tâches

- [ ] `evaluer` — sDA proxy, ASE proxy, UDI proxy, vue proxy
- [ ] `gradient` — dérivées analytiques si possible, sinon différences finies
- [ ] `incertitude` — constante, documentée comme telle
- [ ] Toutes les constantes en attributs de classe, jamais en dur dans le corps

### Tests

```python
def test_plus_de_baie_donne_plus_de_lumiere():
    p1 = plan_avec_baie(largeur_rel=0.20)
    p2 = plan_avec_baie(largeur_rel=0.60)
    assert SUB.evaluer(p2, CTX).sda > SUB.evaluer(p1, CTX).sda

def test_piece_profonde_sature():
    """Au-delà de 2,5 × linteau, agrandir la pièce n'ajoute pas de lumière."""
    p1 = plan_profondeur(5.0)
    p2 = plan_profondeur(9.0)
    assert SUB.evaluer(p2, CTX).sda <= SUB.evaluer(p1, CTX).sda + 1e-9

def test_orientation_change_le_resultat():
    nord = SUB.evaluer(PLAN, ctx_avec(0)).sda
    sud  = SUB.evaluer(PLAN, ctx_avec(180)).sda
    assert abs(nord - sud) > 0.05

def test_gradient_coherent_avec_differences_finies():
    g = SUB.gradient(PLAN, CTX)
    df = differences_finies(SUB.evaluer, PLAN, CTX, pas=1e-4)
    assert np.corrcoef(g, df)[0, 1] > 0.99
```

- [ ] Les 4 tests passent
- [ ] `isinstance(SubstitutAnalytique(), Substitut)` est vrai

---

## 5. Étape 4 — Frank-Wolfe

**Fichier :** `src/archlux/solve/frank_wolfe.py`

### L'algorithme

```
x = legaliser_proximite(plan)          # point de départ DÉJÀ VALIDE
sommets = {x}
pour k = 0 .. K-1 :
    f, g = objectif(x)
    s = lmo.resoudre(poly, -g, depart=x)          # << LE MÊME SOLVEUR >>
    ecart = <-g, s - x>
    si ecart < tol : sortir
    si pas == "ecartement" :
        v = argmax_{v ∈ sommets} <-g, v>
        si <-g, x - v> > <-g, s - x> :
            direction, gamma_max = x - v, poids[v] / (1 - poids[v])
        sinon :
            direction, gamma_max = s - x, 1.0
    gamma = recherche_lineaire(objectif, x, direction, 0, gamma_max)
    x = x + gamma * direction
    si surface_violee(x) : poly.ajouter(coupe_surface(x))
```

### Signature

```python
def frank_wolfe(
    poly: Polytope,
    objectif: Callable[[np.ndarray], tuple[float, np.ndarray]],
    x0: np.ndarray,
    *,
    max_iter: int = 50,
    tol_dualite: float = 1e-4,
    pas: Literal["standard", "recherche", "ecartement"] = "ecartement",
    trace: bool = False,
) -> ResultatFW: ...

@dataclass(frozen=True)
class ResultatFW:
    x: np.ndarray
    valeur: float
    ecart_dualite: float        # MAJORE l'écart à l'optimum — garantie
    iterations: int
    valide_partout: bool
    trace: Trace | None = None
    duaux: np.ndarray | None = None
```

### Tâches

- [ ] Boucle de base avec pas `2/(k+2)`
- [ ] Recherche linéaire (dichotomie ou Armijo)
- [ ] **Pas d'écartement** — mémoriser les sommets visités et leurs poids
- [ ] Critère d'arrêt par écart de dualité
- [ ] **Toujours passer `depart=x`** au solveur (démarrage à chaud)
- [ ] Ajout de coupes de surface en cours de route
- [ ] `trace` : itérés, valeurs, écarts, temps par itération
- [ ] Extraction des duaux à la dernière itération

### Pourquoi le pas d'écartement

Frank-Wolfe standard converge en `O(1/k)` et zigzague près d'un sommet. Autoriser à
**reculer** d'un sommet déjà visité donne une convergence **linéaire** sur polytope.
Coût : mémoriser quelques dizaines de vecteurs.

### Tests

```python
@given(plan=plans_quelconques())
def test_monotonie(plan):
    r = frank_wolfe(POLY, OBJ, x0_valide(plan), trace=True)
    assert est_croissante(r.trace.objectif, tol=1e-9)

@given(plan=plans_quelconques())
def test_dualite_decroit(plan):
    r = frank_wolfe(POLY, OBJ, x0_valide(plan), trace=True)
    assert r.trace.ecarts[-1] <= r.trace.ecarts[0] + 1e-9

def test_dualite_majore_l_ecart_reel():
    """Sur un petit cas résoluble exactement."""
    r = frank_wolfe(POLY_PETIT, OBJ, X0, max_iter=10)
    opt = resoudre_exactement(POLY_PETIT, OBJ)
    assert opt - r.valeur <= r.ecart_dualite + 1e-6

def test_ecartement_converge_plus_vite():
    a = frank_wolfe(POLY, OBJ, X0, pas="standard",   tol_dualite=1e-5)
    b = frank_wolfe(POLY, OBJ, X0, pas="ecartement", tol_dualite=1e-5)
    assert b.iterations < a.iterations

def test_warm_start_utilise(monkeypatch):
    """Vérifier qu'on ne repart pas de zéro à chaque tour."""
    appels = []
    monkeypatch.setattr(lmo, "resoudre", tracer(appels))
    frank_wolfe(POLY, OBJ, X0, max_iter=5)
    assert all(a.kwargs.get("depart") is not None for a in appels[1:])
```

- [ ] Les 5 tests passent
- [ ] Budget : < 500 ms pour 15 pièces, 50 itérations

---

## 6. Étape 5 — Brancher sur l'API

**Fichier :** `src/archlux/api.py` (modification)

```python
def legalize(plan, ctx, *, objective=None, budget=None, trace=False):
    ordre = deduire_ordre(plan)
    poly  = construire_polytope(ordre, ctx)
    if budget is not None:
        poly = poly.avec_boite(vectoriser(plan), budget)     # région de confiance

    x0 = lmo.resoudre(poly, gradient_distance(vectoriser(plan))).x

    if objective is None:
        x, res = x0, None
    else:
        f = lambda x: objective_vers_callable(objective, x, plan, ctx)
        res = frank_wolfe(poly, f, x0, trace=trace)
        x = res.x

    q = devectoriser(x, plan)
    preuve = verifier_exactement(q, ctx)
    if not preuve.valide:
        raise InvariantViole(preuve.violations)
    return replace(q, certificat=Certificat(geometrie=preuve, ...))
```

- [ ] `budget` implémenté comme boîte `‖x − x₀‖∞ ≤ Δ` ajoutée au polytope
- [ ] `objective=None` donne exactement le comportement du jalon 2 (**test de non-régression**)
- [ ] `trace=True` remonte la trace de Frank-Wolfe

```python
def test_non_regression_jalon2():
    """objective=None doit donner le MÊME résultat qu'au jalon 2."""
    assert ax.legalize(PLAN, CTX).pieces == RESULTAT_JALON2.pieces
```

---

## 7. Étape 6 — Première expérience

**Fichier :** `experiences/j3_orientation.py` (< 50 lignes)

**L'expérience la plus démonstrative du projet, et elle est faisable sans données.**

- [ ] Un même plan, 8 orientations, légalisation performantielle à chaque fois
- [ ] Mesurer la divergence géométrique entre les 8 résultats
- [ ] Produire la figure : 8 plans côte à côte, issus d'une même proposition
- [ ] Test de Rayleigh sur le gain par orientation

> **Aujourd'hui, la correction d'un plan est indépendante de son orientation** — le
> légaliseur classique ne connaît pas le nord. Montrer que le plan corrigé change
> quand la boussole tourne est une démonstration immédiate que géométrie et physique
> ne sont pas séparables.

---

## 8. Étape 7 — Documentation

- [ ] Docstrings NumPy sur `orient/`, `light/protocole`, `light/analytique`, `solve/`
- [ ] Section `Guarantees` sur `frank_wolfe` : *tous les itérés sont admissibles ;
      `ecart_dualite` majore l'écart à l'optimum*
- [ ] `docs/galerie/02-comparer-deux-methodes.md`
- [ ] `docs/concepts/oracle-partage.md` — **la page qui explique que l'oracle de
      Frank-Wolfe est le légaliseur**, avec les deux appels côte à côte
- [ ] `README.md` : jalon 3 → ✅
- [ ] `CHANGELOG.md` : `0.2.0`

---

## 9. Checklist finale

### Code
- [ ] `orient/circulaire.py`
- [ ] `light/protocole.py` — 3 méthodes, pas plus
- [ ] `light/analytique.py`
- [ ] `solve/frank_wolfe.py` — écartement, dualité, warm start
- [ ] `api.py` étendu avec `objective` et `budget`

### Tests
- [ ] Les 3 critères d'acceptation du §0
- [ ] Non-régression du jalon 2
- [ ] Warm start effectivement utilisé
- [ ] `test_le_noyau_n_importe_pas_torch` passe toujours

### Performance
- [ ] Légalisation performantielle < 500 ms (15 pièces, 50 itérations)
- [ ] Légalisation classique toujours < 20 ms

### Livrable scientifique
- [ ] Figure des 8 orientations
- [ ] `resultats/j3_orientation.csv`

---

## 10. Erreurs fréquentes

| Symptôme | Cause | Correctif |
|---|---|---|
| Frank-Wolfe très lent | `depart=` oublié | Passer `depart=x` à chaque appel |
| Objectif non monotone | Pas trop grand | Recherche linéaire, ou `γ = 2/(k+2)` |
| Zigzag près de la convergence | Pas d'écartement absent | `pas="ecartement"` |
| Résultat identique pour toutes les orientations | Orientation non branchée dans le substitut | Vérifier `_facteur_orientation` |
| `359°` ≠ `−1°` | Encodage linéaire de l'angle | `orient.encode`, jamais le degré brut |
| Coupes qui s'accumulent sans fin | Plafond absent | `MAX_COUPES = 10` par pièce |

---

## 11. Ce qu'il ne faut PAS faire

- [ ] ❌ Commencer le réseau de neurones → jalon 4
- [ ] ❌ Lancer des simulations → jalon 4
- [ ] ❌ Ajouter une 4ᵉ méthode au protocole `Substitut`
- [ ] ❌ Coder l'orientation en degrés bruts
- [ ] ❌ Sauter le pas d'écartement « pour simplifier » → convergence dégradée

---

## 12. Prochaine étape

**`MILESTONE-4.md`** — données, substitut appris, et le **point de contrôle du projet** :
valider que le gradient appris indique la bonne direction.
