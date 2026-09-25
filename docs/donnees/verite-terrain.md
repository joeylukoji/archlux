# Vérité terrain lumineuse — où sont les étiquettes

Cette page répond à une seule question : **avec quoi entraîne-t-on réellement le
substitut ?** C'est le maillon le plus faible de la chaîne, et le passer sous
silence invaliderait toute publication.

---

## 1. L'état actuel du dépôt, sans détour

| Élément | Ce qui est livré |
|---|---|
| Corpus | 90 pavages 2×2 synthétiques, enveloppe 12 m × 9 m figée (`data.synthese`) |
| Découpage | 54 / 18 / 18 (`splits/v1/`) |
| Étiquettes | `light.simulateur.SplitFluxOracle` — **une forme fermée** |
| Modèle | `light.base.SubstitutDense`, perceptron 3 couches, poids `numpy` |
| Cible apprise | le **résidu** `SplitFluxOracle − SubstitutAnalytique` |

Les deux termes de ce résidu sont analytiques. Le réseau apprend donc la
différence entre deux formules connues, sur une famille de plans à **deux degrés
de liberté** (les deux coordonnées de coupe). Le `mae_reseau = 0,0175` contre
`mae_analytique = 6,4007` publié au jalon 4 mesure exactement cela, **sur le jeu
d'entraînement** : une régression réussie sur une fonction déterministe, sans bruit.
Ces deux chiffres ne se reproduisent plus avec le code livré (le même script donne
0,33 et 41,9) ; sur un jeu de test, en phase 2 (`resultats/j4_gradient.csv`, revue
[j4](../revues/j4.md)), l'erreur du réseau est 1,19 contre 37,3.

!!! danger "Ce que cela veut dire pour un article"
    Ce n'est **pas** un résultat d'apprentissage. Aucun relecteur n'acceptera
    « substitut d'éclairement calibré » adossé à des étiquettes produites par une
    formule fermée que le modèle de base connaît déjà. La chaîne
    (tokenisation → entraînement → gel → calibration conforme → Frank-Wolfe) est
    **exercée de bout en bout**, ce qui est un résultat d'ingénierie réel ; la
    grandeur physique, elle, n'a jamais été mesurée.

    Corollaire : `SubstitutAppris._charger_torch` **lève systématiquement**. Le
    transformeur annoncé au jalon 4 n'existe pas dans le dépôt.

---

## 2. Les trois sources d'étiquettes possibles, par coût croissant

### Option A — Swiss Dwellings (recommandée pour démarrer)

**La seule source publique qui livre géométrie et lumière appariées.**

- 45 000 appartements, ≈ 250 000 pièces, **367 colonnes de simulation par pièce**.
- Famille `sun_AAAAMMJJHHMM` : irradiance solaire (directe + diffuse) par
  hexagone de sol, équinoxe de printemps et solstice d'été.
- **CC BY 4.0**, téléchargement direct, ni demande ni partenariat.
- [doi:10.5281/zenodo.7788422](https://doi.org/10.5281/zenodo.7788422) — fiche :
  [Swiss Dwellings](swiss-dwellings.md).

| Pour | Contre |
|---|---|
| Aucune simulation à lancer | Ce n'est **pas** un sDA LM-83 : ce sont des agrégats à instants fixes |
| Volume suffisant pour un vrai découpage 60/20/20 | Climat suisse uniquement — hors distribution ailleurs |
| Baies et murs porteurs présents dans `geometries.csv` | Reconstruction WKT → `Plan` à écrire (n'existe pas dans le dépôt) |
| Licence propre, modèle republiable | Le masque urbain est inclus dans la simulation, pas dans le vecteur d'entrée |

**Conséquence obligatoire :** renommer la cible. `indicateur="sDA"` devient un
mensonge dès qu'on calibre sur `sun_*`. Publier « couverture 90 % sur
*Swiss Dwellings sun_mean, v3.0.0* », jamais « couverture 90 % sur le sDA ».

### Option B — simuler soi-même avec Radiance

Le seul chemin vers un **vrai sDA₍₃₀₀/₅₀ %₎** au sens IES LM-83.

- Géométrie : [MSD](msd.md) ou [CubiCasa5K](cubicasa.md) (baies annotées).
- Moteur : Radiance / `rtrace` (`honeybee-radiance`, `ladybug-tools`), climat EPW.
- Coût : **minutes à heures par plan**. C'est précisément ce que le substitut
  existe pour éviter — et c'est ce qui rend l'apprentissage actif (`archlux.active`)
  pertinent plutôt que décoratif.
- L'extra `sim` du `pyproject.toml` est **vide à dessein** : le moteur se branche
  derrière `light.simulateur` sans toucher au protocole `Substitut`.

Ordre de grandeur pour un article : 2 000 à 5 000 plans simulés suffisent à un
découpage 60/20/20 honnête, avec **n ≥ 500 en calibration** — au niveau α = 0,10,
\(\lceil (n+1)\cdot 0{,}90\rceil\) reste très loin de \(n\), et la borne cesse
d'être dominée par le bruit d'échantillonnage.

### Option C — corpus lacunaire + imputation des baies

Quand la géométrie vient d'un corpus sans baies : `data.imputation` centre une
baie (`s = 0,5`, `largeur_rel = 0,30`) sur chaque mur nu.

C'est une **hypothèse**, pas une mesure. La règle du dépôt tient toujours :
calibrer séparément sur le sous-jeu à baies observées et sur le jeu imputé, et
**publier les deux couvertures**. Voir [imputation](imputation.md).

---

## 3. Ce que le corpus synthétique peut et ne peut pas faire

`data.synthese.generer_corpus` reste utile, et doit rester :

- il fait tourner la CI sans télécharger des gigaoctets ;
- il est déterministe, donc les certificats sont reproductibles ;
- il porte le doublon `syn-0053` ≡ `syn-0000` qui teste la déduplication.

Il ne peut pas servir de corpus d'évaluation :

- **aucun mur** (`murs=()`) et **aucune ouverture** (`ouvertures=()`) — les jetons
  de baie de `light.jetons._jeton_ouverture` ne sont donc **jamais exercés** sur
  le corpus livré, et le WWR de `SplitFluxOracle` reste à sa valeur par défaut
  quelle que soit la fenestration réelle ;
- enveloppe unique, quatre pièces, deux degrés de liberté ;
- un seul type de topologie (pavage 2×2), donc un seul ordre relatif.

---

## 4. Ordre des opérations, sans exception

```
inventorier → dédupliquer (Hausdorff 0,02 m) → découper (60/20/20)
           → entraîner sur train → GELER les poids → émettre le jeton
           → lire calibration → calibrer conforme → ouvrir test UNE fois
```

Dédupliquer **avant** de découper. Un doublon à cheval entre entraînement et
calibration rend la couverture annoncée fausse — trop optimiste — et **rien ne le
signale** : ni les tests, ni la revue. C'est la seule erreur silencieuse du
système capable d'invalider un chiffre publié (`ARCHITECTURE.md` §10).

Le verrou d'implémentation est `uq.gestion.emettre_jeton` : le jeton n'est
émissible qu'après l'empreinte des poids gelés.

---

## 5. Ce que la jointure a donné, une fois faite

Le chargeur existe désormais (`data.chargeurs.charger_etiquettes_sd`,
`etiqueter`, `decouper_par_site`) et la jointure fonctionne :

| | |
|---|--:|
| Appartements MSD retrouvés dans Swiss Dwellings | **18 263 / 18 270** |
| Pièces habitables appariées | **98 – 99,5 %** selon le type |
| Locaux techniques (gaines, cages, ascenseurs) | **0 %** — ils n'ont pas de lumière à simuler |
| Appartements appariés intégralement | 5 817 |

Piège rencontré : MSD écrit `area_id` en flottant (`484803.0`), Swiss Dwellings en
entier (`484803`). Sans normalisation, la jointure rend **0 %**.

Le résultat de la mesure est **négatif**, et instructif — voir
[limites](../limites.md) : la granularité du protocole, pas la qualité des données,
est le facteur limitant.

## 6. Ce qu'il reste à écrire dans le dépôt

| Manque | Où il devrait vivre |
|---|---|
| Chargeur WKT → `Plan` (Swiss Dwellings / MSD) | `data/chargeurs.py` (n'existe pas) |
| Projection ouverture WKT → `(mur_id, s, largeur_rel)` | idem |
| Adaptateur Radiance derrière `Substitut` | `light/radiance.py`, extra `sim` |
| Transformeur sur jetons | `light/appris.py` — aujourd'hui `_charger_torch` lève toujours |
| Résultats de couverture sur corpus réel | `resultats/` |

**Voir aussi :** [Swiss Dwellings](swiss-dwellings.md), [MSD](msd.md),
[CubiCasa5K](cubicasa.md), [synthétique](synthetique.md),
[imputation](imputation.md), [statistique](../formules/statistique.md),
[limites](../limites.md).
