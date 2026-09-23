# JALON 4 — Substitut appris et validation du gradient

> **Prérequis : `ARCHITECTURE.md`, `DOCUMENTATION.md`, jalon 3 terminé.**
> Durée visée : 10 semaines. Poste le plus lourd du projet.
> **Contient le point de contrôle du projet (§7). Ne pas le franchir par optimisme.**

---

## 0. Objectif et critère d'acceptation

**Objectif.** Remplacer le substitut analytique par un réseau entraîné sur l'oracle
d'éclairement gelé (`SimulateurExact` ; (Radiance) hors chemin critique) — et
**vérifier qu'il indique la bonne direction**, pas seulement la bonne valeur.

**Critère d'acceptation — deux conditions, la seconde est bloquante :**

```python
# 1. Le réseau prédit mieux que l'analytique
assert mae(reseau, JEU_TEST) < mae(ANALYTIQUE, JEU_TEST)

# 2. POINT DE CONTRÔLE — le gradient est exploitable
# ORACLE = SimulateurExact (Radiance)
rapport = ax.light.valider_gradient(reseau, ORACLE, echantillon(80), CTX)
assert rapport.accord_de_signe > 0.80, (
    "Le substitut n'indique pas la bonne direction. "
    "NE PAS passer au jalon 5 avant correction.")
```

**Hors périmètre** : prédiction conforme (jalon 5), apprentissage actif (jalon 6).

---

## 1. Prérequis

- [ ] Jalon 3 terminé : la chaîne tourne avec `SubstitutAnalytique`
- [ ] `pip install "archlux[ml]"` fonctionne (`archlux[sim]` est vide)
- [ ] Accès aux corpus : MSD (CC BY-SA 4.0), Swiss Dwellings, CubiCasa5K — **ou** corpus synthétique CI
- [ ] Oracle gelé : `SimulateurExact` (Radiance)

---

## 2. Étape 1 — Données : télécharger, dédupliquer, découper

**Fichier :** `src/archlux/data/` + `scripts/preparer_donnees.py`

### Ordre impératif

```
télécharger → inventorier → DÉDUPLIQUER → découper → normaliser → apparier
```

**Dédupliquer AVANT de découper.** L'inverse ne sert à rien : les quasi-doublons
franchissent alors les frontières et contaminent le jeu de test.

### Le découpage en TROIS

| Jeu | Part | Rôle | Interdit |
|---|---|---|---|
| `train/` | 60 % | Ajuster les poids | — |
| `calibration/` | 20 % | Quantile conforme (jalon 5) | **Jamais vu à l'entraînement ni au réglage** |
| `test/` | 20 % | Mesure finale | Ouvert une seule fois |

```python
class GestionDonnees:
    def pour_entrainement(self) -> Dataset:
        return charger(self._train)            # seul chemin exposé ici

    def pour_calibration(self, jeton: JetonCalibration) -> Dataset:
        jeton.verifier()                       # émis après gel du modèle
        return charger(self._calib)
```

> **Le jeton n'est pas de la paranoïa.** Une fuite du jeu de calibration produit une
> garantie fausse — trop optimiste — et **rien ne le signale** : ni les tests, ni la
> validation, ni la relecture. C'est la seule erreur silencieuse du système capable
> d'invalider une affirmation publiée.

### Tâches

- [ ] Chargeurs MSD, Swiss Dwellings, CubiCasa5K → `Plan`
- [ ] `dedup()` — empreinte géométrique + distance de Hausdorff, seuil documenté
- [ ] Découpage **figé**, publié en `splits/{train,calibration,test}.txt`
- [ ] Normalisation : mètres, origine, grille — **mesurer l'erreur d'arrondi**
- [ ] `GestionDonnees` avec les trois répertoires séparés
- [ ] Fiche descriptive par corpus dans `docs/donnees/`

### Appariement lumière ↔ fenêtres

Le corpus qui porte les simulations n'a pas les fenêtres détaillées ; celui qui a les
fenêtres n'a pas les simulations.

- [ ] Apparier ce qui peut l'être → petit jeu de référence, haute qualité
- [ ] Imputer le reste : baie centrée par mur extérieur, ratio tiré de la distribution observée
- [ ] **Documenter l'imputation et mesurer son effet** — comparer la calibration obtenue
      sur le jeu propre et sur le jeu imputé. C'est une contribution méthodologique.

### Tests

```python
def test_aucun_identifiant_partage():
    t, c, s = charger_splits()
    assert not (set(t) & set(c)) and not (set(t) & set(s)) and not (set(c) & set(s))

def test_aucun_doublon_franchit_une_frontiere():
    for a, b in paires_quasi_identiques(seuil=0.02):
        assert split_de(a) == split_de(b)

def test_distributions_comparables():
    """Les trois jeux doivent avoir des statistiques proches."""
    for stat in ["n_pieces", "surface", "compacite"]:
        assert ks_test(train[stat], test[stat]).pvalue > 0.05
```

- [ ] Les 3 tests passent

---

## 3. Étape 2 — Vérité terrain

**Fichier :** `src/archlux/light/simulateur.py` + `scripts/simuler.py`

L'oracle **obligatoire** est `SimulateurExact` (forme fermée, CI). Un lot
(Radiance) est **hors chemin critique** : même protocole `Substitut`, jamais
importé par le noyau, jamais exigé pour passer au jalon 5.

### Lancer TÔT (Radiance seulement)

C'est le poste le plus long en temps machine. **Il n'est pas un prérequis du jalon.**
S'il est lancé, le faire pendant qu'on écrit le reste.

### Budget (Radiance, optionnel)

| Usage | Simulations |
|---|---|
| Entraînement | 1 500 – 3 000 |
| Calibration (jalon 5) | 800 – 1 200 |
| Contrôle de dérive | 300 – 500 |
| Évaluation finale | 2 000 – 4 000 |
| **Total** | **5 000 – 8 000** (≈ 800–1 300 h CPU) |

### Tâches

- [ ] `SimulateurExact` respecte le protocole `Substitut` (`gradient` par différences finies)
- [ ] (Radiance) Convertisseur `Plan` → modèle de simulation
- [ ] (Radiance) **Figer** le fichier climatique et le modèle de ciel, et les journaliser
- [ ] (Radiance) Lancement par lots, parallélisé entre plans
- [ ] (Radiance) Stocker : identifiant, orientation, indicateurs, **paramètres de simulation**, durée

### Tests

```python
def test_simulation_deterministe():
    """Non négociable : sans déterminisme, la calibration conforme est invalide."""
    oracle = SimulateurExact()  # (Radiance)
    a = oracle.evaluer(x, orientation)
    b = oracle.evaluer(x, orientation)
    assert a == b

def test_simulateur_respecte_le_protocole():
    assert isinstance(SimulateurExact(), Substitut)  # (Radiance)
```

- [ ] Les 2 tests passent
- [ ] (Radiance) Les paramètres de simulation sont dans chaque ligne du fichier de résultats

---

## 4. Étape 3 — Tokenisation

**Fichier :** `src/archlux/light/jetons.py`

### La décision structurante

**Entrée = ensemble de jetons. JAMAIS une image.**

Sur une image, déplacer un mur de 2 cm ne change aucun pixel : gradient nul, optimiseur
aveugle, **projet impossible**. C'est le piège le plus séduisant du jalon.

### Le vocabulaire

| Jeton | Attributs |
|---|---|
| Pièce | `x, y, w, h`, type (encodage à chaud), périmètre extérieur, compacité |
| Ouverture | mur, `s`, `largeur_rel`, allège, linteau, **azimut du mur** |
| Global | orientation (cos/sin + harmoniques), surface totale, nombre de pièces |

```python
def plan_vers_jetons(plan: Plan, ctx: Contexte) -> tuple[np.ndarray, np.ndarray]:
    """Retourne (jetons [N, d], masque [N])."""
```

### Tâches

- [ ] Encodage des trois familles de jetons
- [ ] Masque de remplissage pour un nombre variable de pièces
- [ ] Orientation via `orient.encode`, jamais en degrés bruts
- [ ] **Normalisation des attributs** (centrer-réduire), constantes stockées avec le modèle

### Tests

```python
@given(plan=plans_quelconques())
def test_jetons_continus(plan):
    """Déplacer un mur de 2 cm doit changer les jetons."""
    j1, _ = plan_vers_jetons(plan, CTX)
    j2, _ = plan_vers_jetons(deplacer_mur(plan, 0.02), CTX)
    assert not np.allclose(j1, j2)

@given(plan=plans_quelconques())
def test_invariance_par_permutation(plan):
    """L'ordre des pièces dans l'ensemble ne doit pas changer la prédiction."""
    assert np.allclose(MODELE(jetons(plan)), MODELE(jetons(permuter(plan))), atol=1e-5)
```

- [ ] Les 2 tests passent — le premier est **le test anti-image**

---

## 5. Étape 4 — Modèle simple d'abord

**Fichier :** `src/archlux/light/base.py`

### Pourquoi commencer simple

Un perceptron sur descripteurs se code en une journée et **valide toute la chaîne
d'entraînement** — chargeurs, normalisation, journalisation, points de contrôle. Il vaut
mieux avoir un pipeline correct au premier mois qu'une belle architecture au troisième.

- [ ] ~100 descripteurs calculés à la main
- [ ] Réseau dense 3 couches
- [ ] Entraînement complet, courbes d'apprentissage
- [ ] **Validation du gradient sur ce modèle** (§7) — si elle échoue déjà ici,
      c'est la **tokenisation** qui est en cause, pas l'architecture

---

## 6. Étape 5 — Transformeur sur ensemble

**Fichier :** `src/archlux/light/appris.py`

```python
class SubstitutAppris(L.LightningModule):
    def __init__(self, d_entree=32, d=128, couches=4, n_tetes=4, lr=3e-4):
        super().__init__()
        self.save_hyperparameters()
        self.proj = nn.Linear(d_entree, d)
        self.enc = nn.TransformerEncoder(
            nn.TransformerEncoderLayer(d, n_tetes, 4 * d,
                                       batch_first=True, norm_first=True),
            couches)
        self.tete_valeur = nn.Linear(d, 4)      # sDA, ASE, UDI, vue
        self.tete_ecart  = nn.Linear(d, 4)      # log σ

    def forward(self, jetons, masque):
        h = self.enc(self.proj(jetons), src_key_padding_mask=masque)
        h = masque_moyenne(h, masque)
        return self.tete_valeur(h), self.tete_ecart(h).exp()

    def training_step(self, lot, _):
        mu, sigma = self(lot["jetons"], lot["masque"])
        perte = F.smooth_l1_loss(mu, lot["cible"])            # robuste aux aberrants
        perte = perte + 0.1 * nll_gaussienne(mu, sigma, lot["cible"])
        self.log("train/perte", perte, prog_bar=True)
        return perte

    def configure_optimizers(self):
        opt = torch.optim.AdamW(self.parameters(), lr=self.hparams.lr, weight_decay=1e-2)
        sch = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=200)
        return {"optimizer": opt, "lr_scheduler": sch}
```

```python
L.seed_everything(17, workers=True)
trainer = L.Trainer(
    max_epochs=200, precision="bf16-mixed", deterministic=True,
    callbacks=[ModelCheckpoint(monitor="val/mae_sda", mode="min"),
               EarlyStopping(monitor="val/mae_sda", patience=20)],
    logger=CSVLogger("journaux/"),
)
```

### Tâches

- [ ] Transformeur, **200 k – 2 M paramètres, pas plus**
- [ ] Deux têtes : valeur et incertitude, apprises conjointement
- [ ] Cibles **normalisées** (sDA en %, vue dans [0,1] : sans normalisation la perte
      est dominée par la première)
- [ ] Perte de Huber, pas quadratique
- [ ] `deterministic=True` et `seed_everything(..., workers=True)`
- [ ] Journal CSV, pas de service externe

### Pourquoi ne pas surdimensionner

Un gros modèle mémorise, et ses intervalles conformes se dégradent hors distribution —
**c'est-à-dire exactement là où l'optimiseur veut aller.** Sur ce projet, un modèle plus
petit vaut mieux qu'un modèle plus juste en moyenne.

### Tests

```python
def test_meilleur_que_analytique():
    assert mae(RESEAU, JEU_TEST) < mae(ANALYTIQUE, JEU_TEST)

def test_erreur_stratifiee_par_orientation():
    """Une bonne moyenne peut cacher un mauvais comportement au nord."""
    for secteur, jeu in stratifier(JEU_TEST, par_orientation=8).items():
        assert mae(RESEAU, jeu) < SEUIL_MAX, f"échec sur {secteur}"

def test_taille_raisonnable():
    assert sum(p.numel() for p in RESEAU.parameters()) < 2_000_000
```

- [ ] Les 3 tests passent

---

## 7. Étape 6 — POINT DE CONTRÔLE : valider le gradient

**Fichier :** `src/archlux/light/validation.py`

### Le mode d'échec silencieux

Un substitut peut avoir une **excellente erreur moyenne** et un **gradient inexploitable**.
Le système tournerait, convergerait, et optimiserait dans la mauvaise direction —
**sans jamais produire d'erreur**.

### Le protocole

```python
def valider_gradient(
    substitut: Substitut, simulateur: SimulateurExact,
    plans: list[Plan], ctx: Contexte,
    *, pas: float = 0.10, variables: list[str] | None = None,
) -> RapportGradient:
    """Compare le gradient du substitut aux différences finies du simulateur exact.

    Pour chaque plan et chaque variable : déplacer de ±pas, simuler les deux,
    calculer la pente réelle, comparer au gradient prédit.
    """
```

### Le critère de décision

| Accord de signe | Décision |
|---|---|
| > 0,90 | Excellent — continuer |
| 0,80 – 0,90 | Acceptable — continuer en surveillant |
| **< 0,80** | **ARRÊT. Revoir le substitut avant le jalon 5** |

### Que faire si ça échoue — dans l'ordre

1. **Vérifier que l'entrée n'est pas une image déguisée.** Un descripteur trop grossier
   a le même effet qu'une rastérisation.
2. **Enrichir par des paires proches** : deux plans différant d'un seul mur de 10 cm,
   tous deux simulés. Ce sont exactement les exemples dont le réseau a besoin.
3. **Réduire la taille du modèle.** Un gradient lisse vaut mieux qu'un gradient précis
   mais bruité.
4. **Se replier sur `SubstitutAnalytique`** — direction approximative mais fiable, sans
   apprentissage. Le projet continue, avec un résultat plus modeste.

### Tâches

- [ ] `valider_gradient` avec corrélation **et** accord de signe
- [ ] Stratification par variable et par orientation
- [ ] `assert` bloquant dans `scripts/valider_gradient.py`, pas seulement dans la doc
- [ ] Rapport écrit dans `resultats/j4_gradient.md`

> Coût : deux simulations exactes par variable et par plan. À faire sur un **petit
> échantillon (60–100 plans)**, et **tôt**. Découvrir un gradient inexploitable au
> sixième mois coûte trois semaines ; au dix-huitième, il coûte le projet.

---

## 8. Étape 7 — Brancher et comparer

- [ ] `ax.legalize(plan, ctx, objective=ax.light.Daylight(...))` utilise le réseau
- [ ] Comparer analytique vs appris sur la **qualité du plan corrigé**, pas seulement
      sur l'erreur de prédiction
- [ ] Évaluer **par simulation exacte**, jamais par le réseau (erreur circulaire)

```python
def test_pas_d_evaluation_circulaire():
    """L'API de comparaison doit exiger un évaluateur explicite."""
    with pytest.raises(TypeError):
        ax.bench.compare(plans=..., methods=[...])     # evaluate_by manquant
```

---

## 9. Étape 8 — Documentation

- [ ] Docstrings sur `data/`, `light/jetons`, `light/appris`, `light/validation`
- [ ] `docs/tutoriels/entrainer-un-substitut.md`
- [ ] `docs/concepts/pourquoi-pas-une-image.md` — **justifier la décision
      contre-intuitive**, un relecteur de vision la contestera
- [ ] `docs/donnees/` — une fiche par corpus, avec licence et limites
- [ ] `README.md` : jalon 4 → ✅ · `CHANGELOG.md` : `0.3.0`

---

## 10. Checklist finale

### Données
- [ ] Trois répertoires séparés, jeton de calibration en place
- [ ] Déduplication avant découpage, seuil documenté
- [ ] `splits/*.txt` publiés
- [ ] (Radiance, optionnel) 5 000 – 8 000 simulations produites, paramètres journalisés
- [ ] Imputation des ouvertures documentée et son effet mesuré

### Modèle
- [ ] Modèle simple puis transformeur, les deux évalués
- [ ] < 2 M paramètres
- [ ] Erreur **stratifiée par orientation**
- [ ] Meilleur que `SubstitutAnalytique`

### Point de contrôle
- [ ] `accord_de_signe > 0.80` — **sinon, ne pas passer au jalon 5**
- [ ] `resultats/j4_gradient.md` produit

### Qualité
- [ ] `deterministic=True`, graines partout
- [ ] `test_le_noyau_n_importe_pas_torch` passe **toujours**
- [ ] CI verte, doctests verts

---

## 11. Erreurs fréquentes

| Symptôme | Cause | Correctif |
|---|---|---|
| Gradient inutilisable, bonne erreur moyenne | Entrée trop grossière ou rastérisée | Enrichir la tokenisation |
| Perte dominée par un indicateur | Cibles non normalisées | Centrer-réduire chaque sortie |
| Le modèle mémorise | Trop de paramètres | Réduire à < 2 M |
| Résultats non reproductibles | `deterministic` oublié | `Trainer(deterministic=True)` + `seed_everything(workers=True)` |
| Scores de test trop bons | Doublons ou fuite | Vérifier déduplication et découpage |
| Bonne moyenne, mauvais au nord | Pas de stratification | Stratifier toutes les évaluations |

---

## 12. Ce qu'il ne faut PAS faire

- [ ] ❌ Utiliser une image / un CNN en entrée → gradient nul → projet impossible
- [ ] ❌ Ouvrir le jeu de calibration → garantie fausse, silencieusement
- [ ] ❌ Sauter la validation du gradient « parce que la MAE est bonne »
- [ ] ❌ Découper avant de dédupliquer
- [ ] ❌ (Radiance) Changer de fichier climatique en cours de route
- [ ] ❌ Faire importer `torch` par le noyau

---

## 13. Prochaine étape

**`MILESTONE-5.md`** — calibration conforme, certificat complet et diagnostic dual.
