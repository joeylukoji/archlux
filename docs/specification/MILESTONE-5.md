# JALON 5 — Garanties de performance et certificat complet

> **Prérequis : `ARCHITECTURE.md`, `DOCUMENTATION.md`, jalon 4 terminé avec
> `accord_de_signe > 0.80`.**
> Durée visée : 5 semaines.
> **Ce jalon produit la contribution scientifique centrale du projet.**

---

## 0. Objectif et critère d'acceptation

**Objectif.** Transformer une prédiction en **borne assortie d'un taux de couverture
démontré**, et produire le certificat complet — preuve exacte, borne probabiliste,
diagnostic dual.

**Critère d'acceptation :**

> **Revue de phase 2 (2026-09-25) :** couverture mesurée sur 20 graines de calibration
> (moyenne 0,903), et critère **ajouté** : largeur moyenne < 1 écart-type de la cible
> (mesuré : 4 à 5, non atteint). Sous sélection par l'optimiseur : 0,879 en moyenne.
> Voir [`revues/j5.md`](../revues/j5.md) et [ADR 0002](../adr/0002-milestone-criteria-rewritten.md).

```python
def test_couverture_empirique():
    """Sur le jeu de TEST, jamais sur celui de calibration."""
    bornes  = [modele.borne(p) for p in JEU_TEST]
    verites = [ORACLE.evaluer(p, CTX) for p in JEU_TEST]  # SplitFluxOracle (forme fermée)
    couv = np.mean([v >= b.borne for v, b in zip(verites, bornes)])
    assert 0.86 <= couv <= 0.94          # visée 0,90
```

**La borne haute compte autant que la borne basse.** Une couverture de 0,97 quand on
vise 0,90 n'est pas rassurante : elle signale des intervalles trop larges, donc une
incertitude mal estimée, donc un système inutilement pessimiste qui refusera de bonnes
solutions.

**Hors périmètre** : apprentissage actif (jalon 6), pièces en L (jalon 6).

---

## 1. Prérequis

- [ ] Jalon 4 terminé, point de contrôle du gradient franchi
- [ ] Jeu de calibration **intact** — jamais lu par l'entraînement
- [ ] 800 – 1 200 évaluations de l'oracle gelé (`SplitFluxOracle`) pour la calibration
      (Radiance)
- [ ] `Polytope.origines` renseigné depuis le jalon 2 (indispensable ici)

---

## 2. Étape 1 — Geler le modèle et émettre le jeton

**Fichier :** `src/archlux/uq/gestion.py`

**Ordre impératif :** entraîner → geler → émettre le jeton → **puis seulement** lire la
calibration.

```python
@dataclass(frozen=True)
class JetonCalibration:
    empreinte_modele: str      # sha256 des poids
    horodatage: str
    def verifier(self) -> None: ...

def geler_et_emettre(modele) -> JetonCalibration:
    """Émet le jeton donnant accès au jeu de calibration.
    Le modèle ne doit plus être modifié après cet appel."""
```

- [ ] `geler_et_emettre` calcule l'empreinte des poids
- [ ] `pour_calibration(jeton)` refuse un jeton dont l'empreinte ne correspond pas
- [ ] L'empreinte est **journalisée** et entrera dans le manifeste

```python
def test_calibration_refuse_un_modele_modifie():
    j = geler_et_emettre(modele)
    modele.tete_valeur.weight.data += 0.01
    with pytest.raises(ModeleModifie):
        donnees.pour_calibration(j)
```

- [ ] Le test passe

---

## 3. Étape 2 — Calibration conforme

**Fichier :** `src/archlux/uq/conforme.py`

### Les quatre lignes

```python
class CalibrateurConforme:
    def ajuster(self, predictions, verites, incertitudes, *, alpha=0.10) -> None:
        scores = np.abs(verites - predictions) / incertitudes      # normalisés
        n = len(scores)
        niveau = np.ceil((n + 1) * (1 - alpha)) / n                # ← correction finie
        self.q = float(np.quantile(scores, min(niveau, 1.0)))
        self.n, self.alpha = n, alpha

    def borne(self, prediction, incertitude, sens) -> BornePerformance:
        marge = self.q * incertitude
        val = prediction - marge if sens == ">=" else prediction + marge
        return BornePerformance(borne=val, prediction=prediction, marge=marge,
                                couverture=1 - self.alpha, sens=sens,
                                n_calibration=self.n)
```

### Le piège de la ligne 4

`np.quantile(scores, 0.90)` au lieu de `ceil((n+1)(1−α))/n` est l'erreur classique.
Avec 1 000 points l'écart est minime ; avec 100, **la garantie tombe**. C'est une
correction d'échantillon fini, elle n'est pas facultative.

### Tâches

- [ ] Conforme par découpage, scores **normalisés** par l'incertitude locale
- [ ] Correction d'échantillon fini
- [ ] Un calibrateur **par indicateur** (sDA, ASE, UDI, vue) — les erreurs n'ont pas
      la même échelle
- [ ] Sens correct : `>=` pour sDA/UDI/vue, `<=` pour ASE
- [ ] Sérialisation du calibrateur avec le modèle (`q`, `n`, `alpha`)

### Tests

```python
def test_correction_echantillon_fini():
    c = CalibrateurConforme(); c.ajuster(P[:100], V[:100], S[:100], alpha=0.10)
    assert c.q > np.quantile(scores[:100], 0.90)    # strictement plus large

@given(alpha=st.floats(0.01, 0.30))
def test_couverture_sur_donnees_synthetiques(alpha):
    """Sur des données i.i.d., la couverture doit tenir."""
    c = CalibrateurConforme(); c.ajuster(*CAL_SYNTH, alpha=alpha)
    couv = np.mean([v >= c.borne(p, s, ">=").borne
                    for p, v, s in zip(*TEST_SYNTH)])
    assert couv >= 1 - alpha - 0.03

def test_sens_ase_inverse():
    b = CAL.borne(prediction=6.1, incertitude=1.0, sens="<=")
    assert b.borne > b.prediction       # ASE : borne SUPÉRIEURE
```

- [ ] Les 3 tests passent

---

## 4. Étape 3 — Diagrammes de fiabilité

**Fichier :** `src/archlux/uq/fiabilite.py`

```python
def diagramme_fiabilite(predictions, verites, incertitudes,
                        niveaux=np.linspace(0.5, 0.99, 20)) -> Figure: ...
def crps(predictions, verites, incertitudes) -> float: ...
```

- [ ] Diagramme : couverture empirique en fonction de la couverture nominale
- [ ] CRPS (score de probabilité continu classé)
- [ ] **Stratification par orientation** — la calibration peut tenir au sud et échouer au nord

```python
def test_calibration_tient_par_orientation():
    for secteur, jeu in stratifier(JEU_TEST, par_orientation=8).items():
        couv = couverture(CAL, jeu)
        assert 0.84 <= couv <= 0.96, f"calibration cassée sur {secteur}"
```

- [ ] Le test passe

---

## 5. Étape 4 — La borne comme objectif

**Fichier :** `src/archlux/light/objectif.py`

### Le mécanisme d'auto-limitation

On optimise la **borne inférieure**, pas la prédiction :

```
J(Q) = D̂(Q, θ) − q̂ · σ̂(Q, θ)
```

> Là où le substitut ne sait pas, `σ̂` est grand, la marge est large, l'objectif chute,
> **et l'optimiseur est spontanément dissuadé d'y aller.** Le garde-fou n'est pas
> ajouté : il découle de la façon dont l'incertitude est estimée.
>
> C'est le point où la statistique rejoint la géométrie : le budget `Δ` cesse d'être un
> réglage arbitraire pour devenir la traduction géométrique du domaine où les erreurs
> du réseau restent maîtrisées.

```python
class Daylight:
    def __init__(self, metric="sDA", alpha=0.10, poids=None, pessimiste=True): ...
    def __call__(self, x, plan, ctx) -> tuple[float, np.ndarray]:
        """Retourne (J, ∇J). Avec pessimiste=True, J est la borne conforme."""
```

- [ ] `pessimiste=True` par défaut
- [ ] Gradient de la borne (inclut ∇σ̂ — ne pas l'oublier)
- [ ] `poids` explicite pour le compromis sDA / ASE

```python
def test_pessimiste_penalise_l_incertitude():
    """À prédiction égale, le plan le plus incertain doit avoir un objectif plus bas."""
    assert J(plan_certain) > J(plan_incertain)
```

- [ ] Le test passe

---

## 6. Étape 5 — Contrôle de dérive

**Fichier :** `src/archlux/uq/derive.py`

### Ce qu'on mesure

```
dérive(k) = E[ D̂(Q*ₖ) − D_exact(Q*ₖ) ]
```

Une dérive positive croissante signifie que **l'optimiseur exploite les erreurs du
réseau**. Personne n'a quantifié ce phénomène sur un substitut environnemental — c'est
un résultat scientifique en soi.

```python
def mesurer_derive(optimiseur, substitut, simulateur, plans, ctx,
                   *, n_echantillons=50) -> RapportDerive: ...
```

- [ ] Prélèvement périodique parmi les plans produits par l'optimiseur
- [ ] Évaluation de l'oracle gelé, calcul de l'écart (`SplitFluxOracle`, forme fermée)
- [ ] **Couverture empirique sur les plans produits par l'optimiseur** — et non sur le
      jeu de calibration. C'est la vraie question, puisque l'échangeabilité y est douteuse
- [ ] Plan factoriel `α × Δ` pour mesurer l'effet des deux leviers

> **La couverture sous sélection est une question ouverte qui dépasse le domaine
> architectural.** Les plans produits par un optimiseur sont *sélectionnés* pour
> maximiser la prédiction : ils ne sont pas échangeables. Mesurer de combien la
> couverture se dégrade intéresse la communauté de la prédiction conforme.

```python
def test_derive_bornee():
    r = mesurer_derive(FW, RESEAU, ORACLE, PLANS, CTX)  # ORACLE = SplitFluxOracle (forme fermée, pas Radiance)
    assert r.derive_moyenne < SEUIL, "l'optimiseur exploite le substitut"
    assert r.tendance.pvalue > 0.05 or r.tendance.pente <= 0
```

- [ ] Le test passe, ou l'échec est **documenté comme résultat**

---

## 7. Étape 6 — Diagnostic dual

**Fichier :** `src/archlux/certify/dual.py`

### Ce que la fusion offre gratuitement

Les prix duaux du programme linéaire répondent à : *de combien l'objectif s'améliorerait
si je relâchais cette contrainte d'une unité ?*

```python
def traduire_duaux(duaux, origines, *, seuil=1e-6) -> tuple[PrixDual, ...]:
    return tuple(sorted(
        (PrixDual(contrainte=origines[i], prix=float(d),
                  interpretation=phrase(origines[i], d),
                  validite=intervalle_validite(i))
         for i, d in enumerate(duaux) if abs(d) > seuil),
        key=lambda p: -abs(p.prix)))
```

Sortie :

```
CE QUI VOUS COUTE DE LA LUMIERE
  1. Mur porteur, axe 3             -4,1 pts de sDA   (reculer de 20 cm : +0,8)
  2. Surface minimale cuisine 9 m2  -1,7 pt
  3. Largeur de passage degagement  -0,6 pt
  4. Contour, facade nord            0,0 pt  (non contraignant)
```

**Ni un correcteur géométrique ni un simulateur ne peut produire ces lignes.**

### L'intervalle de validité est obligatoire

Les prix duaux sont valides **localement**. Reculer un porteur de 20 cm, oui ; de 2 m,
non. Un diagnostic sans intervalle serait trompeur.

- [ ] `traduire_duaux` avec tri par valeur absolue décroissante
- [ ] `phrase()` — une formulation lisible par contrainte, depuis `origines`
- [ ] `intervalle_validite` extrait du solveur (analyse de sensibilité)
- [ ] Filtrer les contraintes non actives (prix nul)

```python
def test_le_diagnostic_est_lisible():
    d = traduire_duaux(DUAUX, ORIGINES)
    assert all(len(p.interpretation) > 20 for p in d)     # pas "ligne 47"

def test_prix_nul_pour_contrainte_non_active():
    d = traduire_duaux(DUAUX, ORIGINES)
    assert all(p.prix != 0 for p in d)
```

- [ ] Les 2 tests passent

---

## 8. Étape 7 — Le certificat complet

**Fichier :** `src/archlux/certify/rapport.py`

```
CERTIFICAT — plan T3-065-a          archlux 0.4.1     graine 17

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
  Ecart a l'optimum          <= 0,4 pt de sDA (dualite Frank-Wolfe)

DIAGNOSTIC
  Mur porteur axe 3         -4,1 pts   (reculer de 20 cm : +0,8)
  Surface min. cuisine      -1,7 pt

NON EVALUABLE
  Confort d'ete, systemes techniques, materiaux — hors perimetre
```

- [ ] Séparation typographique `[EXACT]` / `[PREDICTION]` — **non négociable**
- [ ] `n_calibration` affiché : une borne sur 50 points ne vaut pas une borne sur 1 284
- [ ] Section `NON EVALUABLE` toujours présente, jamais vide
- [ ] Écart de dualité reporté
- [ ] Sérialisation JSON avec `schema: "archlux/certificat/1.0"`

```python
def test_certificat_separe_les_natures():
    r = plan.certificat.rapport()
    assert "[EXACT]" in r and "[PREDICTION" in r

def test_pas_de_borne_sans_calibration():
    with pytest.raises(ValueError):
        BornePerformance(borne=51.4, prediction=56.2, marge=4.8,
                         couverture=0.90, sens=">=", n_calibration=0)

def test_non_evaluable_toujours_present():
    assert "NON EVALUABLE" in plan.certificat.rapport()
```

- [ ] Les 3 tests passent

---

## 9. Étape 8 — Documentation

- [ ] Docstrings sur `uq/`, `certify/borne`, `certify/dual`
- [ ] **`docs/concepts/deux-garanties.md`** — la page centrale du site. Expliquer que
      « ce plan n'a aucun chevauchement » est une **preuve** et « ce plan atteindra
      51,4 % » une **prédiction avec sa marge**
- [ ] `docs/concepts/prediction-conforme.md` — les 4 étapes, l'exemple chiffré, le piège
      de la correction d'échantillon fini
- [ ] `docs/galerie/04-lire-un-certificat.md` — champ par champ
- [ ] `docs/galerie/05-diagnostic-dual.md`
- [ ] `README.md` : jalon 5 → ✅ · `CHANGELOG.md` : `0.4.0`

---

## 10. Checklist finale

### Calibration
- [ ] Jeton émis après gel du modèle, empreinte journalisée
- [ ] Correction d'échantillon fini appliquée
- [ ] Un calibrateur par indicateur, sens correct
- [ ] Couverture sur le jeu de **test** dans [0,86 ; 0,94]
- [ ] Couverture **stratifiée par orientation** vérifiée

### Objectif et dérive
- [ ] Borne conforme comme objectif, `pessimiste=True` par défaut
- [ ] Dérive mesurée, plan factoriel `α × Δ` réalisé
- [ ] Couverture **sous sélection par l'optimiseur** mesurée et publiée

### Certificat
- [ ] `[EXACT]` et `[PREDICTION]` séparés
- [ ] `n_calibration` affiché, `NON EVALUABLE` présent
- [ ] Diagnostic dual avec intervalles de validité
- [ ] Sérialisation JSON versionnée

### Publication
- [ ] Jeu de calibration publié **avec** le modèle
- [ ] Manifeste incluant empreinte des poids et `calibration_n`

---

## 11. Erreurs fréquentes

| Symptôme | Cause | Correctif |
|---|---|---|
| Couverture ≈ 0,97 au lieu de 0,90 | Incertitude surestimée | Recalibrer `σ̂`, vérifier la tête d'écart |
| Couverture ≈ 0,78 | **Fuite du jeu de calibration** | Vérifier les chemins et le jeton |
| Garantie fausse sur petit échantillon | `np.quantile(s, 0.90)` | `ceil((n+1)(1−α))/n` |
| Bornes ASE dans le mauvais sens | Sens non paramétré | `sens="<="` pour ASE |
| Diagnostic illisible | `origines` non renseigné au jalon 2 | Reconstruire `geom` |
| Dérive croissante | L'optimiseur exploite le substitut | Resserrer `Δ`, durcir `α`, réentraîner |
| Prix duaux tous nuls | `duaux=True` oublié | Passer le flag à `lmo.resoudre` |

---

## 12. Ce qu'il ne faut PAS faire

- [ ] ❌ Toucher au jeu de calibration avant le gel du modèle
- [ ] ❌ Utiliser le quantile naïf à 0,90
- [ ] ❌ Publier le modèle **sans** son jeu de calibration → garantie invérifiable
- [ ] ❌ Présenter la borne de performance avec l'assurance de la preuve géométrique
- [ ] ❌ Omettre `NON EVALUABLE` → l'oracle mentirait sur sa couverture
- [ ] ❌ Donner un prix dual sans son intervalle de validité

---

## 13. Prochaine étape

**`MILESTONE-6.md`** — géométries non rectangulaires, apprentissage actif, export IFC,
et version 1.0.
