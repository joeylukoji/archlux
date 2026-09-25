# JALON 6 — Consolidation et version 1.0

> **Prérequis : `ARCHITECTURE.md`, `DOCUMENTATION.md`, jalon 5 terminé.**
> Durée visée : 6 semaines. Livrable : `archlux 1.0.0`.

---

## 0. Objectif et critère d'acceptation

**Objectif.** Passer d'un prototype de recherche à une bibliothèque que quelqu'un d'autre
installe et utilise : géométries réelles, budget de simulation maîtrisé, sorties
exploitables en CAO/BIM, documentation complète.

**Critère d'acceptation — le test le plus exigeant du projet :**

> **Revue de phase 2 (2026-09-25) :** critère **non atteint** (aucun utilisateur externe
> ne l'a passé ; phase 5). « L'actif perd » est retiré (aucune différence détectée sur 30
> campagnes indépendantes) ; les fichiers IFC, rejetés par ifcopenshell jusque-là, le
> passent désormais. Voir [`revues/j6.md`](../revues/j6.md) et
> [ADR 0002](../adr/0002-milestone-criteria-rewritten.md).

```python
def test_utilisateur_externe():
    """Une personne qui n'a jamais vu le code doit réussir en 10 minutes."""
    # 1. pip install archlux
    # 2. copier l'exemple de docs/galerie/01
    # 3. l'exécuter sur son propre plan
    # → un plan valide et un certificat sortent
```

À faire vérifier **par une personne réelle extérieure au projet**, pas par un test
automatique. C'est la seule mesure honnête de l'utilisabilité.

---

## 1. Prérequis

- [ ] Jalons 1 à 5 terminés
- [ ] Couverture conforme validée sur le jeu de test
- [ ] Dépôt public avec **au moins 6 mois d'historique** et développement étalé

---

## 2. Étape 1 — Géométries non rectangulaires

**Fichier :** `src/archlux/geom/rectilineaire.py`

### Le problème

Le modèle rectangulaire couvre l'essentiel du résidentiel, mais MSD conserve
délibérément des géométries non-Manhattan, et les pièces en L sont courantes.

### La méthode : décomposition avec contraintes de fusion

Une pièce en L = deux rectangles + une contrainte les rendant solidaires.

```python
@dataclass(frozen=True)
class PieceRectilineaire:
    id: str
    rectangles: tuple[Piece, ...]          # 2 à 4
    fusions: tuple[tuple[int, int, str], ...]   # (i, j, "partage_bord_droit")
```

**Le polytope reste linéaire** : les contraintes de fusion sont des égalités.

- [ ] Décomposition automatique d'un polygone rectilinéaire en rectangles minimaux
- [ ] Contraintes de fusion → lignes de `A_eq`
- [ ] Vérification exacte adaptée (`shapely` gère déjà les polygones quelconques)
- [ ] Recomposition en polygone pour l'export

```python
@given(poly=polygones_rectilineaires())
def test_decomposition_recompose(poly):
    assert recomposer(decomposer(poly)).equals(poly)

@given(plan=plans_avec_pieces_en_L())
def test_validite_preservee(plan):
    assert ax.legalize(plan, CTX).certificat.geometrie.valide
```

- [ ] Les 2 tests passent
- [ ] Budget : < 40 ms pour 15 pièces dont 4 en L

> **Piège :** la décomposition d'un polygone en L n'est pas unique. Fixer une convention
> (coupe verticale à gauche d'abord) et la documenter, sinon les résultats ne sont pas
> reproductibles.

---

## 3. Étape 2 — Apprentissage actif

**Fichier :** `src/archlux/active/`

### La règle de sélection

```
priorité(Q) = incertitude(Q) × fréquence(Q | optimiseur)
```

**Un produit, pas une somme.** Sans le second facteur, on simule des plans aberrants sur
lesquels le réseau doute légitimement mais qui n'apparaîtront jamais. Sans le premier, on
simule des cas déjà maîtrisés. Un facteur nul suffit à écarter un candidat.

```python
class Loop:
    def __init__(self, substitut, simulateur, acquire, budget: int): ...
    def run(self, proposal_distribution) -> RapportActif: ...
```

- [ ] `UncertaintyTimesDensity` — estimation de densité sur les sorties de l'optimiseur
- [ ] Boucle : sélectionner → simuler → réentraîner → recalibrer
- [ ] **Recalibrer le conforme après chaque cycle** (le modèle a changé, le jeton aussi)
- [ ] Comparaison contre tirage aléatoire, à budget égal

```python
def test_actif_bat_l_aleatoire():
    a = Loop(acquire=Aleatoire(), budget=500).run(PROPOSALS)
    b = Loop(acquire=UncertaintyTimesDensity(), budget=500).run(PROPOSALS)
    assert b.largeur_intervalle_finale < a.largeur_intervalle_finale
```

- [ ] Le test passe, ou l'échec est publié comme résultat

**Résultat attendu :** même qualité avec 5 à 10 fois moins de simulations. C'est ce qui
diviserait le budget total du projet.

---

## 4. Étape 3 — Export IFC et DXF

**Fichier :** `src/archlux/export/`

```python
def to_ifc(plan: Plan, chemin: Path, *, validate: bool = True) -> RapportExport: ...
def to_dxf(plan: Plan, chemin: Path) -> None: ...
def survival_rate(plans: list[Plan]) -> tuple[float, tuple[float, float]]: ...
```

### La mesure qui n'existe nulle part

**Aucun travail publié ne donne le taux de survie des sorties de modèles génératifs à un
export validé.** Le chiffre est probablement bas et il conditionne toute revendication
d'utilité industrielle.

- [x] `to_ifc` (SPF IFC4 minimal ; extra `bim` / IfcOpenShell optionnel), murs / espaces / ouvertures
- [x] Validation de pathologie intégrée, `validate=True` par défaut
- [x] Taxonomie des pathologies : auto-intersection, arête nulle, sommets dupliqués,
      solide non fermé
- [x] Intervalle de **Wilson** pour la proportion (pas l'intervalle normal : les taux
      sont proches des extrêmes et l'approximation normale y donne des bornes négatives)
- [x] Le certificat est **annexé** au fichier IFC (propriété personnalisée)

```python
@given(plan=plans_valides())
def test_export_valide(plan):
    assert to_ifc(plan, tmp, validate=True).valide

def test_taux_de_survie_avec_wilson():
    taux, (lo, hi) = survival_rate(SORTIES_MODELES_PUBLICS)
    assert 0 <= lo <= taux <= hi <= 1
```

- [x] Les 2 tests passent
- [x] `resultats/j6_survie_ifc.csv` produit (phase 2 : remplacé par `resultats/j6_ifc.csv`, validé par ifcopenshell)

---

## 5. Étape 4 — Banc d'essai reproductible

**Fichier :** `src/archlux/bench/`

```python
@dataclass(frozen=True)
class Manifest:
    archlux: str
    horodatage: str
    graine: int
    empreinte_donnees: str
    decoupage: str
    environnement: dict[str, str]
    modele: dict[str, str | int | float]     # poids, calibration_n, alpha
    parametres: dict
```

- [x] `Manifest` écrit **à chaque exécution**, sans exception
- [x] `bench.compare()` avec `evaluate_by` **obligatoire, sans défaut**
- [x] Résultats bruts écrits **avant** toute agrégation
- [x] Stratification par orientation imposée dans `report()`
- [x] Tests statistiques : bootstrap apparié, TOST, analyse de puissance

```python
def test_manifeste_complet():
    m = bench.run(...).manifest
    assert m.modele["poids"] and m.modele["calibration_n"] > 0

def test_evaluate_by_obligatoire():
    with pytest.raises(TypeError):
        bench.compare(plans=..., methods=["proximity", "performance"])
```

- [x] Les 2 tests passent

**C'est l'étape la plus rentable du jalon, et celle qu'on a envie de bâcler.**

### Galerie — 5 exemples, chacun sur un écran

- [x] `01-corriger-un-plan.md`
- [x] `02-comparer-deux-methodes.md`
- [x] `03-detecter-une-infaisabilite.md`
- [x] `04-lire-un-certificat.md`
- [x] `05-diagnostic-dual.md`

Chacun : **Problème → Solution → Résultat → Ce qu'il faut retenir → Voir aussi**, sur un
plan **réel**, jamais fictif.

### Tutoriels

- [x] `premiers-pas.md`
- [x] `legalisation-performantielle.md`
- [x] `calibrer-un-substitut.md`

### Concepts

- [x] `deux-garanties.md` — **la page centrale**
- [x] `polytope.md` · `oracle-partage.md` · `prediction-conforme.md`
- [x] `pourquoi-pas-une-image.md`

### `limites.md` — obligatoire

- [x] Estimations de phase amont, pas d'étude réglementaire
- [x] Hypothèse d'échangeabilité, et sa fragilité sous sélection
- [x] Périmètre du `NON EVALUABLE`
- [x] Pas d'avis juridique
- [x] Ce que la vérification automatique ne peut pas établir

> Un outil qui produit des chiffres réglementaires et ne dit pas ce qu'il ne vérifie pas
> est dangereux. Cette page n'est pas facultative.

### Contribution

- [x] `CONTRIBUTING.md` — exigé par les revues de logiciel
- [x] Gouvernance : décisions, revue, versions
- [x] Renvoi explicite aux règles de dépendance de `ARCHITECTURE.md`

---

## 7. Étape 6 — Préparer la publication logicielle

- [ ] **≥ 6 mois d'historique public** avec développement **étalé**, pas concentré
- [ ] Licence approuvée (Apache 2.0)
- [ ] Tests automatisés, couverture publiée
- [ ] Documentation complète et en ligne
- [ ] Traces de contribution externe : issues, discussions
- [ ] Issue tracker lisible sans inscription
- [ ] **Preuve d'usage réel par un tiers** — condition de recevabilité

> Les revues de logiciel refusent les outils sans adoption démontrable. Si personne
> d'autre n'utilise `archlux`, il est trop tôt : mieux vaut attendre et solliciter deux
> ou trois utilisateurs pilotes.

---

## 8. Étape 7 — Version 1.0

- [x] Interface publique **gelée** — toute rupture devient `2.0`
- [x] `CHANGELOG.md` : `1.0.0`
- [ ] Étiquette `v1.0.0` + archivage avec identifiant pérenne
- [ ] Publication sur l'index de paquets
- [ ] Publier : code, poids, **jeu de calibration**, découpages, résultats bruts
- [x] `CITATION.cff` avec l'identifiant de version

```python
def test_api_publique_stable():
    """Verrouille l'interface : toute suppression casse ce test."""
    attendu = {"legalize", "Plan", "Contexte", "Certificat",
               "Infaisable", "InvariantViole", "light", "bench", "feasibility"}
    assert attendu <= set(archlux.__all__)
```

- [x] Le test passe

---

## 9. Checklist finale du jalon

### Fonctionnalités
- [x] Pièces en L, décomposition documentée et reproductible
- [x] Apprentissage actif, comparé au tirage aléatoire
- [x] Export IFC validé, taux de survie mesuré avec intervalle de Wilson
- [x] Banc d'essai avec manifestes

### Documentation
- [x] 5 exemples de galerie sur plans réels
- [x] 3 tutoriels · 5 pages de concepts
- [x] `limites.md` complet
- [x] `CONTRIBUTING.md`
- [x] Doctests verts, couverture docstrings ≥ 95 %, `mkdocs build --strict` propre

### Publication
- [ ] ≥ 6 mois d'historique étalé
- [ ] Usage externe démontrable
- [ ] Jeu de calibration publié avec le modèle
- [ ] Version étiquetée et archivée

### Qualité
- [ ] `test_le_noyau_n_importe_pas_torch` passe
- [ ] Tous les budgets de performance tenus
- [ ] CI verte sur 3 versions de Python
- [ ] **Un utilisateur externe réussit en 10 minutes**

---

## 10. Erreurs fréquentes

| Symptôme | Cause | Correctif |
|---|---|---|
| Décomposition en L non reproductible | Convention de coupe non fixée | Fixer et documenter |
| Polytope explose avec les pièces en L | Décomposition trop fine | Rectangles maximaux, pas minimaux |
| Actif pas meilleur que l'aléatoire | Densité mal estimée | Vérifier la distribution de proposition |
| Export IFC toujours invalide | Solides non fermés | Vérifier la recomposition des polygones |
| Intervalle de survie négatif | Approximation normale | Intervalle de Wilson |
| Refus de la revue logicielle | Historique trop court ou concentré | Attendre, et solliciter des utilisateurs |
| Documentation bâclée | Reportée à la fin | La rédiger **pendant** chaque jalon |

---

## 11. Ce qu'il ne faut PAS faire

- [ ] ❌ Soumettre à une revue de logiciel sans usage externe démontré
- [ ] ❌ Publier le modèle sans son jeu de calibration
- [ ] ❌ Sauter `limites.md`
- [ ] ❌ Geler l'API avant que la galerie ne soit écrite (les exemples révèlent
      les défauts d'interface)
- [ ] ❌ Décomposer les polygones sans convention documentée
- [ ] ❌ Considérer le jalon terminé sans qu'un tiers ait réussi l'exemple 01

---

## 12. Après la version 1.0

Extensions possibles, aucune n'est requise :

| Extension | Effort | Ce que ça ouvre |
|---|---|---|
| Substitut acoustique ou thermique | Faible — le protocole existe | Nouveaux publics scientifiques |
| Objectifs composites pondérés | Faible | Compromis multi-physiques |
| Multi-niveaux (cohérence verticale) | Élevé | Échelle du bâtiment |
| Oracle réglementaire déclaratif | Moyen | Marché des bureaux de contrôle |
| Non-résidentiel (formalisme de circulation) | Élevé | Marché tertiaire |

**Le protocole `Substitut` rend la première ligne quasi gratuite** : écrire une classe à
trois méthodes, zéro ligne modifiée dans le noyau. C'est le dividende de la décision
d'architecture AD-03.
