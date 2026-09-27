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

## Exceptions (rename wave 1, PLAN.md 3.9)

| French (current) | English (target) | Notes |
|---|---|---|
| `OrdreIncoherent` | `InconsistentOrder` | attribute `axe` becomes `axis` |
| `SeparationManquante` | `MissingSeparation` | attribute `paire` becomes `pair` |
| `Infaisable` | `Infeasible` | attributes `certificat_farkas` to `farkas_certificate`, `origines` to `origins` |
| `InvariantViole` | `InvariantViolation` | attribute `violations` is unchanged |
| `CalibrationVerrouillee` | `CalibrationLocked` | |
| `ModeleModifie` | `ModelModified` | subclass of `CalibrationLocked` |
| `SubstitutInvalide` | `InvalidSurrogate` | |
| `InvalidInput`, `UnsupportedInput`, `GridNotRecoverable`, `GapNeedsTiling` | `InvalidInput`, `UnsupportedInput`, `GridNotRecoverable`, `GapNeedsTiling` | unchanged: already English |

## Fields of the model types (rename wave 3, no alias)

| French field | English field | Type |
|---|---|---|
| `porteur`, `epaisseur` | `load_bearing`, `thickness` | `Wall` |
| `mur_id`, `largeur_rel`, `hauteur_allege`, `hauteur_linteau` | `wall_id`, `relative_width`, `sill_height`, `head_height` | `Opening` |
| `pieces`, `murs`, `ouvertures`, `contour`, `certificat` | `rooms`, `walls`, `openings`, `outline`, `certificate` | `Plan` |
| `murs_porteurs`, `poteaux` | `load_bearing_walls`, `columns` | `Structure` |
| `aires_min`, `largeur_min`, method `a_min` | `min_areas`, `min_width`, method `min_area` | `Regulation` |
| `referentiel`, `programme`, `contour` | `regulation`, `program`, `outline` | `Context` |
| `valide`, `chevauchement`, `jours`, `surfaces_ok`, `structure_preservee`, `deplacement_max` | `valid`, `overlap`, `gaps`, `areas_ok`, `structure_kept`, `max_displacement` | `GeometricProof` |
| `indicateur`, `valeur`, `borne_inf`, `borne_sup`, `couverture` | `indicator`, `value`, `lower`, `upper`, `coverage` | `PerformanceBound` |
| `geometrie`, `duaux`, `manifeste` | `geometry`, `duals`, `manifest` | `Certificate` |
| `horodatage`, `graine`, `empreinte_donnees`, `decoupage`, `environnement`, `parametres`, `modele` | `timestamp`, `seed`, `data_fingerprint`, `split`, `environment`, `parameters`, `model` | `Manifest` |
| `poids`, `calibration_n` | `weights_fingerprint`, `calibration_n` | `ModelTrace` (was `ModeleTrace`) |

Unchanged because they already read as English or are standard terms: `id`, `type`, `x`, `y`,
`w`, `h`, `version`, `performance`, `violations`, `regime`, `n_calibration`, `alpha`,
`trace`, `orientation`, `structure`, `deg`.

Public parameters that follow the same rename: `pavage` becomes `tiling`,
`budget_reparation` becomes `repair_budget`, `fusions` becomes `merged_rooms`.

## Public functions and methods (rename wave 5, first batch)

| French (current) | English (target) | Notes |
|---|---|---|
| `Room.aire`, `Room.centre` | `Room.area`, `Room.center` | properties |
| `Wall.longueur` | `Wall.length` | property |
| `Opening.segment_absolu()` | `Opening.absolute_segment()` | derived on demand, never stored |
| `Plan.ids_pieces` | `Plan.room_ids` | sorted room ids |
| `Certificate.rapport()` | `Certificate.report()` | text report |
| `rendre` (`certify.rapport`, `export.svg`) | `render` | |
| `construire_borne` | `build_bound` | |
| `traduire_duaux` | `translate_duals` | |
| `CertificatFaisabilite` | `FeasibilityCertificate` | fields `origines` to `origins`, `certificat_farkas` to `farkas_certificate` |
| `expliquer()` | `explain()` | |
| `Verdict.faisable`, `Verdict.certificat` | `Verdict.feasible`, `Verdict.certificate` | |

## Geometry and LMO modules (rename wave 5, batch 4)

| French (current) | English (target) | Notes |
|---|---|---|
| `OrdreRelatif` (field `pieces`) | `RelativeOrder` (field `rooms`) | |
| `GrapheContraintes` (`a_separation`, `fermeture`) | `ConstraintGraph` (`has_separation`, `closure`) | |
| `deduire_ordre`, `construire_graphe`, `reduction_transitive` | `deduce_order`, `build_graph`, `transitive_reduction` | |
| `construire_polytope`, `figer_contacts`, `vectoriser`, `devectoriser`, `etendre_ecarts_l1` | `build_polytope`, `freeze_contacts`, `vectorize`, `devectorize`, `extend_l1_slack` | parameter `gabarit` becomes `template` |
| `Polytope.bornes`, `origines`, `origines_eq`, `labels_eq()`, `contient()` | `bounds`, `origins`, `origins_eq`, `eq_labels()`, `contains()` | |
| `CHAMPS` | `FIELDS` | |
| `Trame` | `Grid` | fields `lignes_x`, `lignes_y`, `ancrees_x`, `ancrees_y` become `x_lines`, `y_lines`, `anchored_x`, `anchored_y`; `n_cellules` becomes `n_cells` |
| `deduire_trame`, `contraintes_pavage`, `etendre_pavage` | `deduce_grid`, `tiling_constraints`, `extend_tiling` | parameters `trame`, `support_min` become `grid`, `min_support` |
| `PieceRectilineaire` (field `fusions`) | `RectilinearRoom` (field `merges`) | |
| `decomposer`, `recomposer`, `contraintes_fusion`, `etendre_fusions` | `decompose`, `recompose`, `merge_constraints`, `extend_merges` | parameters `polygone`, `type_piece` become `polygon`, `room_type` |
| `FUSION_DROIT`, `FUSION_HAUT` | `MERGE_RIGHT`, `MERGE_TOP` | |
| `diagnostiquer` | `diagnose` | fields `recouvrements`, `part_jour`, `part_trou`, `morceaux`, `cellules`, `cote` become `overlaps`, `gap_share`, `hole_share`, `fragments`, `cells`, `size` |
| `resoudre`, `vider_cache` | `solve`, `clear_cache` | parameters `depart`, `coupes` become `start`, `cuts` |
| `SolutionLP` | `LPSolution`; fields `valeur`, `statut`, `duaux`, `certificat_farkas`, `certificat_farkas_eq`, `temps_ms` become `value`, `status`, `duals`, `farkas_certificate`, `farkas_certificate_eq`, `time_ms` | |
| `Coupe` (`coeffs`, `borne_inf`, `origine`, `satisfait()`) | `Cut` (`coefficients`, `lower_bound`, `origin`, `satisfied()`) | |
| `coupe_surface`, `surfaces_violees`, `resoudre_avec_surfaces`, `MAX_COUPES_PAR_PIECE` | `area_cut`, `violated_areas`, `solve_with_areas`, `MAX_CUTS_PER_ROOM` | |

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
| `SimulateurExact` (deprecated alias, as is `ExactSimulator`) | `SplitFluxOracle`, done in PLAN.md batch 1.8 (a frozen closed-form oracle: never "exact", never "ground truth") |
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

## Light modules (rename wave 5, batch 5)

| French (current) | English (target) | Notes |
|---|---|---|
| `SubstitutAnalytique`, `SubstitutAppris`, `SubstitutDense` | `AnalyticSurrogate`, `LearnedSurrogate`, `DenseSurrogate` | |
| `facteur_secteur`, `descripteurs`, `facteur_lumiere_jour` | `sector_factor`, `descriptors`, `daylight_factor` | |
| `permuter_pieces`, `plan_vers_vecteur`, `plan_vers_jetons`, `vecteur_vers_jetons` | `permute_rooms`, `plan_to_vector`, `plan_to_tokens`, `vector_to_tokens` | |
| `DIM_JETON`, `CHAMPS_PAR_PIECE` | `TOKEN_DIM`, `FIELDS_PER_ROOM` | |
| `RapportGradient`, `valider_gradient` | `GradientReport`, `validate_gradient` | |
| `Indicateur` | `Indicator` | type alias in `archlux.types` |
| methods `ajuster`, `sauver`, `n_parametres` | `fit`, `save`, `n_parameters` | surrogates and `CalibrateurConforme` |

## Uncertainty, active learning and orientation modules (rename wave 5, batch 6)

| French (current) | English (target) | Notes |
|---|---|---|
| `CalibrateurConforme`, `borner`, `n_minimal_conforme`, `quantile_conforme` | `ConformalCalibrator`, `bound`, `minimal_n_conformal`, `conformal_quantile` | `archlux.uq.conforme` |
| `DiagnosticDerive`, `RapportDerive`, `controler_derive`, `mesurer_derive` | `DriftDiagnostic`, `DriftReport`, `check_drift`, `measure_drift` | `archlux.uq.derive` |
| `diagramme_fiabilite`, `stratifier_par_orientation` | `reliability_diagram`, `stratify_by_orientation` | `archlux.uq.fiabilite` |
| `GestionDonnees`, `JetonCalibration`, `emettre_jeton`, `geler_et_emettre`, `ouvrir_calibration` | `DataManagement`, `CalibrationToken`, `issue_token`, `freeze_and_issue`, `open_calibration` | `archlux.uq.gestion`; fields `empreinte_poids`, `horodatage_gel` become `weights_fingerprint`, `freeze_timestamp`; method `verifier` becomes `verify`; methods `pour_entrainement`, `pour_test`, `pour_calibration` become `for_training`, `for_test`, `for_calibration` (no alias) |
| `RapportActif`, `Aleatoire`, `StrategieAcquisition`, `densite_noyau` | `ActiveReport`, `RandomStrategy`, `AcquisitionStrategy`, `kernel_density` | `archlux.active` |
| `ResultatRegression`, `difference_angulaire`, `direction_dominante`, `encoder`, `moyenne_circulaire`, `regression_circulaire_lineaire`, `stratifier`, `variance_circulaire` | `RegressionResult`, `angular_difference`, `dominant_direction`, `encode_orientation`, `circular_mean`, `circular_linear_regression`, `stratify`, `circular_variance` | `archlux.orient.circulaire` |
| parameters/fields `valeur`, `couverture`, `horodatage`, `modele`, `poids`, `jeton` | `value`, `coverage`, `timestamp`, `model`, `weights`, `token` | across `uq` and `orient`, no alias (not public class names) |

## Export, data and bench modules (rename wave 5, batch 7)

| French (current) | English (target) | Notes |
|---|---|---|
| `RapportExport`, `DiagnosticPathologie`, `intervalle_wilson` | `ExportReport`, `PathologyDiagnostic`, `wilson_interval` | `archlux.export` |
| `comparer`, `planche` | `compare`, `sheet` | `archlux.export.svg` |
| `AppartementMSD`, `StatistiquesChargement`, `charger_msd`, `charger_etiquettes_sd`, `etiqueter`, `decouper_par_site` | `MSDApartment`, `LoadStatistics`, `load_msd`, `load_sd_labels`, `label`, `split_by_site` | `archlux.data.chargeurs`; constants `COLONNE_SOLEIL_DEFAUT`, `TYPES_EXCLUS` become `DEFAULT_SUN_COLUMN`, `EXCLUDED_TYPES` |
| `corrompre` | `corrupt` | `archlux.data.corruption`; field `piece_id`/`axe` become `room_id`/`axis`; Mode values `deplacer`/`elargir`/`retrecir`/`aplatir` become `move`/`widen`/`narrow`/`flatten` |
| `Decoupage`, `charger_decoupage` | `Split`, `load_split` | `archlux.data.decoupage`; fields `nom`/`entrainement`/`empreinte` become `name`/`train`/`fingerprint` |
| `empreinte_geometrique`, `distance_cotes`, `paires_quasi_identiques`, `SEUIL_HAUSDORFF_M` | `geometric_fingerprint`, `side_distance`, `near_duplicate_pairs`, `HAUSDORFF_THRESHOLD_M` | `archlux.data.dedup` |
| `imputer_ouvertures`, `RATIO_BAIE_DEFAUT` | `impute_openings`, `DEFAULT_OPENING_RATIO` | `archlux.data.imputation` |
| `generer_corpus`, `TAILLE_MAX` | `generate_corpus`, `MAX_SIZE` | `archlux.data.synthese` |
| `deriver`, `emettre` | `derive`, `emit` | `archlux.bench.graines`, `archlux.bench.manifeste` |
| `RapportBanc`, `StrateOrientation`, `LigneBrute`, `Resultat`, `Intervalle`, `bootstrap_apparie`, `puissance` | `BenchReport`, `OrientationStratum`, `RawRow`, `Result`, `Interval`, `paired_bootstrap`, `power` | `archlux.bench.{rapport,run,stats}` |
| identifiers `contour`, `murs`, `ouvertures`, `pieces`, `poids`, `couverture`, `manifeste` (local names, not Plan or Manifest fields) | `outline`, `walls`, `openings`, `rooms`, `weights`, `coverage`, `manifest` | across `export` and `data`, no alias (locals, not public fields) |
