# Glossary (French → English)

The code base is migrating from French to English (ADR
[0001](adr/0001-english-first.md)). This glossary fixes the English name of every
domain term **once**, so that each migration batch renames consistently. A term is added
here *before* it is used in a renamed module; changing an entry after its module has
been migrated is a breaking change.

## Data model

| French (current) | English (target) | Notes |
|---|---|---|
| `Plan` | `Plan` | unchanged |
| pièce / `Piece` | room / `Room` | |
| mur / `Mur` | wall / `Wall` | |
| porteur (`Mur.porteur`) | load-bearing (`Wall.load_bearing`) | |
| poteau | column | `Structure.columns` |
| structure porteuse / `Structure` | load-bearing structure / `Structure` | |
| ouverture / `Ouverture` | opening / `Opening` | |
| baie / `Baies` | glazing / `Glazing` | window geometry passed to surrogates |
| hauteur d'allège / de linteau | sill height / head height | |
| contour | outline | |
| enveloppe | envelope | |
| contexte / `Contexte` | context / `Context` | |
| référentiel / `Referentiel` | regulation / `Regulation` | set of regulatory minima |
| programme | room program | list of required rooms |
| orientation / `Orientation(deg=)` | orientation / `Orientation(deg=)` | azimuth in degrees |
| certificat / `Certificat` | certificate / `Certificate` | |
| preuve géométrique / `PreuveGeometrique` | geometric proof / `GeometricProof` | exact, no probability |
| borne de performance / `BornePerformance` | performance bound / `PerformanceBound` | probabilistic |
| manifeste / `Manifeste` | manifest / `Manifest` | |

## Room types (string values, JSON schema v2)

| French | English |
|---|---|
| `sejour` | `living_room` |
| `chambre` | `bedroom` |
| `cuisine` | `kitchen` |
| `sdb` | `bathroom` |
| `wc` | `toilet` |
| `couloir`, dégagement | `corridor` |

## Geometry and solver

| French | English |
|---|---|
| légalisation / `legalize` | legalization / `legalize` |
| ordre relatif / `OrdreRelatif` | relative order / `RelativeOrder` |
| séparation | separation |
| chevauchement | overlap |
| jour | uncovered gap (checker kind `coverage`) |
| pavage | tiling |
| trame | grid |
| réparation de la trame | grid repair |
| déplacement | displacement |
| budget | budget |
| coupe (de surface) | (area) cut |
| épigraphe L1 | L1 epigraph |
| solveur / oracle linéaire | solver / linear minimization oracle (LMO) |
| démarrage à chaud (`depart=`) | warm start (`start=`) |
| duaux, prix implicites | duals, shadow prices |
| certificat de Farkas | Farkas certificate |
| infaisable / `Infaisable` | infeasible / `Infeasible` |
| invariant violé / `InvariantViole` | invariant violation / `InvariantViolation` |
| vérifier exactement | verify exactly |

## Frank-Wolfe (`solve`)

| French | English |
|---|---|
| `ResultatFW` | `FrankWolfeResult` |
| itéré | iterate |
| sommet (FW, away) | vertex (FW, away) |
| pas | step |
| poids (des sommets) | weights |
| valeur (du substitut) | value |
| écart de dualité / gap (FW) | stationarity gap (field `gap` of `FrankWolfeResult`) |
| trace, `iteres`, `ecarts`, `objectif` | trace, `iterates`, `gaps`, `values` |
| `temps_lp_ms`, `n_coupes` | `lp_ms`, `n_cuts` |
| `depart` | `start` |
| `duaux` | `duals` |
| baies (paramètre) | `glazing` (the protocol keyword stays `baies` until batch E6 of `light`) |

## Daylight and uncertainty

| French | English |
|---|---|
| éclairement | daylight (quantity: illuminance) |
| substitut / `Substitut` | surrogate / `Surrogate` |
| `SubstitutAnalytique` | `AnalyticSurrogate` |
| `SimulateurExact`, renamed `OracleSplitFlux` in PLAN.md batch 1.8 (old name deprecated) | `SplitFluxOracle` (a frozen closed-form oracle: never "exact", never "ground truth") |
| `SubstitutDense` | `DenseSurrogate` |
| jetons | tokens |
| prédiction conforme | conformal prediction |
| calibration, jeu de calibration | calibration, calibration set |
| couverture | coverage |
| dérive | drift |
| fiabilité | reliability |
| apprentissage actif | active learning |

## Project and data

| French | English |
|---|---|
| jalon | milestone |
| graine | seed |
| banc d'essai | benchmark (`bench`) |
| découpage (train/calibration/test) | split |
| corpus, chargeur | corpus, loader |
| appartement, logement | apartment, dwelling |
| résultats bruts | raw results |

## Modules and files

| French | English | | French | English |
|---|---|---|---|---|
| `erreurs.py` | `errors.py` | | `graphe.py` | `graph.py` |
| `pavage.py` | `tiling.py` | | `rectilineaire.py` | `rectilinear.py` |
| `solveur.py` | `solver.py` | | `coupes.py` | `cuts.py` |
| `analytique.py` | `analytic.py` | | `simulateur.py` | `split_flux.py` |
| `jetons.py` | `tokens.py` | | `objectif.py` | `objective.py` |
| `appris.py` | `learned.py` | | `protocole.py` | `protocol.py` |
| `circulaire.py` | `circular.py` | | `conforme.py` | `conformal.py` |
| `derive.py` | `drift.py` | | `fiabilite.py` | `reliability.py` |
| `gestion.py` | `registry.py` | | `boucle.py` | `loop.py` |
| `densite.py` | `density.py` | | `selection.py` | `selection.py` |
| `preuve.py` | `proof.py` (done: batch E10, old module kept as a deprecated shim) | | `borne.py` | `bound.py` |
| `rapport.py` | `report.py` | | `dual.py` | `dual.py` |
| `chargeurs.py` | `loaders.py` | | `decoupage.py` | `splits.py` |
| `synthese.py` | `synthetic.py` | | `corruption.py` | `corruption.py` |
| `pathologie.py` | `pathologies.py` | | `survie.py` | `survival.py` |
| `graines.py` | `seeds.py` | | `manifeste.py` | `manifest.py` |
| `protocole.py` (bench) | `protocol.py` | | `json_io.py` | `json_io.py` |
| `tests/unites` | `tests/unit` | | `tests/proprietes` | `tests/properties` |
| `experiences/` | `experiments/` | | `resultats/` | `results/` |
