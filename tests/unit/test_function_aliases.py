"""Former French function and class names stay importable, deprecated, until 1.0.0.

PLAN.md 3.9, wave 5 (first batch). One parametrized test covers the whole table.
"""

from __future__ import annotations

import importlib
import warnings

import pytest

ALIASES = [
    ("archlux.certify", "construire_borne", "build_bound"),
    ("archlux.certify", "rendre", "render"),
    ("archlux.certify", "traduire_duaux", "translate_duals"),
    ("archlux.certify.borne", "construire_borne", "build_bound"),
    ("archlux.certify.dual", "traduire_duaux", "translate_duals"),
    ("archlux.certify.rapport", "rendre", "render"),
    ("archlux.export.svg", "rendre", "render"),
    ("archlux.feasibility", "CertificatFaisabilite", "FeasibilityCertificate"),
    ("archlux.light", "Substitut", "Surrogate"),
    ("archlux.light", "SubstitutAnalytique", "AnalyticSurrogate"),
    ("archlux.light.protocole", "Substitut", "Surrogate"),
    ("archlux.light.protocole", "Baies", "Glazing"),
    ("archlux.light.protocole", "SubstitutParPiece", "PerRoomSurrogate"),
    ("archlux.io.json_io", "charger", "load"),
    ("archlux.io.json_io", "VERSION_SCHEMA", "SCHEMA_VERSION"),
    ("archlux.io.json_io", "ecrire", "write"),
    ("archlux.io.json_io", "vers_dict", "to_dict"),
    ("archlux.io.json_io", "depuis_dict", "from_dict"),
    ("archlux.io.json_io", "manifeste_vers_dict", "manifest_to_dict"),
    ("archlux.geom.graphe", "OrdreRelatif", "RelativeOrder"),
    ("archlux.geom.graphe", "GrapheContraintes", "ConstraintGraph"),
    ("archlux.geom.graphe", "deduire_ordre", "deduce_order"),
    ("archlux.geom.graphe", "construire_graphe", "build_graph"),
    ("archlux.geom.polytope", "construire_polytope", "build_polytope"),
    ("archlux.geom.polytope", "figer_contacts", "freeze_contacts"),
    ("archlux.geom.polytope", "vectoriser", "vectorize"),
    ("archlux.geom.polytope", "devectoriser", "devectorize"),
    ("archlux.geom.polytope", "etendre_ecarts_l1", "extend_l1_slack"),
    ("archlux.geom.polytope", "CHAMPS", "FIELDS"),
    ("archlux.geom.pavage", "Trame", "Grid"),
    ("archlux.geom.pavage", "deduire_trame", "deduce_grid"),
    ("archlux.geom.pavage", "contraintes_pavage", "tiling_constraints"),
    ("archlux.geom.pavage", "etendre_pavage", "extend_tiling"),
    ("archlux.geom.rectilineaire", "PieceRectilineaire", "RectilinearRoom"),
    ("archlux.geom.rectilineaire", "decomposer", "decompose"),
    ("archlux.geom.rectilineaire", "recomposer", "recompose"),
    ("archlux.geom.rectilineaire", "etendre_fusions", "extend_merges"),
    ("archlux.geom.rectilineaire", "FUSION_DROIT", "MERGE_RIGHT"),
    ("archlux.geom.rectilineaire", "FUSION_HAUT", "MERGE_TOP"),
    ("archlux.geom.diagnostic", "diagnostiquer", "diagnose"),
    ("archlux.lmo.solveur", "SolutionLP", "LPSolution"),
    ("archlux.lmo.solveur", "resoudre", "solve"),
    ("archlux.lmo.solveur", "vider_cache", "clear_cache"),
    ("archlux.export.pathologie", "diagnostiquer", "diagnose"),
    ("archlux.light.analytique", "facteur_secteur", "sector_factor"),
    ("archlux.light.appris", "SubstitutAppris", "LearnedSurrogate"),
    ("archlux.light.base", "SubstitutDense", "DenseSurrogate"),
    ("archlux.light.base", "descripteurs", "descriptors"),
    ("archlux.light.jetons", "permuter_pieces", "permute_rooms"),
    ("archlux.light.jetons", "plan_vers_vecteur", "plan_to_vector"),
    ("archlux.light.jetons", "plan_vers_jetons", "plan_to_tokens"),
    ("archlux.light.jetons", "vecteur_vers_jetons", "vector_to_tokens"),
    ("archlux.light.jetons", "DIM_JETON", "TOKEN_DIM"),
    ("archlux.light.jetons", "CHAMPS_PAR_PIECE", "FIELDS_PER_ROOM"),
    ("archlux.light.simulateur", "facteur_lumiere_jour", "daylight_factor"),
    ("archlux.light.validation", "RapportGradient", "GradientReport"),
    ("archlux.light.validation", "valider_gradient", "validate_gradient"),
    ("archlux.types", "Indicateur", "Indicator"),
    ("archlux.uq", "CalibrateurConforme", "ConformalCalibrator"),
    ("archlux.uq", "DiagnosticDerive", "DriftDiagnostic"),
    ("archlux.uq", "GestionDonnees", "DataManagement"),
    ("archlux.uq", "JetonCalibration", "CalibrationToken"),
    ("archlux.uq", "RapportDerive", "DriftReport"),
    ("archlux.uq", "borner", "bound"),
    ("archlux.uq", "controler_derive", "check_drift"),
    ("archlux.uq", "diagramme_fiabilite", "reliability_diagram"),
    ("archlux.uq", "emettre_jeton", "issue_token"),
    ("archlux.uq", "geler_et_emettre", "freeze_and_issue"),  # lang-ok: deprecated French alias name
    ("archlux.uq", "mesurer_derive", "measure_drift"),
    ("archlux.uq", "ouvrir_calibration", "open_calibration"),
    ("archlux.uq", "quantile_conforme", "conformal_quantile"),
    ("archlux.uq.conforme", "borner", "bound"),
    ("archlux.uq.conforme", "n_minimal_conforme", "minimal_n_conformal"),
    ("archlux.uq.conforme", "quantile_conforme", "conformal_quantile"),
    ("archlux.uq.derive", "DiagnosticDerive", "DriftDiagnostic"),
    ("archlux.uq.derive", "RapportDerive", "DriftReport"),
    ("archlux.uq.derive", "controler_derive", "check_drift"),
    ("archlux.uq.derive", "mesurer_derive", "measure_drift"),
    ("archlux.uq.gestion", "GestionDonnees", "DataManagement"),
    ("archlux.uq.gestion", "JetonCalibration", "CalibrationToken"),
    ("archlux.uq.gestion", "emettre_jeton", "issue_token"),
    ("archlux.uq.gestion", "geler_et_emettre", "freeze_and_issue"),  # lang-ok: French alias name
    ("archlux.uq.gestion", "ouvrir_calibration", "open_calibration"),
    ("archlux.active", "Aleatoire", "RandomStrategy"),
    ("archlux.active", "RapportActif", "ActiveReport"),
    ("archlux.active", "densite_noyau", "kernel_density"),
    ("archlux.active.boucle", "RapportActif", "ActiveReport"),
    ("archlux.active.densite", "densite_noyau", "kernel_density"),
    ("archlux.active.selection", "Aleatoire", "RandomStrategy"),
    ("archlux.orient.circulaire", "ResultatRegression", "RegressionResult"),
    ("archlux.orient.circulaire", "encoder", "encode_orientation"),
    ("archlux.orient.circulaire", "moyenne_circulaire", "circular_mean"),
    ("archlux.orient.circulaire", "stratifier", "stratify"),
    ("archlux.export", "DiagnosticPathologie", "PathologyDiagnostic"),
    ("archlux.export", "RapportExport", "ExportReport"),
    ("archlux.export", "intervalle_wilson", "wilson_interval"),
    ("archlux.export.ifc", "RapportExport", "ExportReport"),
    ("archlux.export.svg", "rendre", "render"),
    ("archlux.export.svg", "comparer", "compare"),
    ("archlux.export.svg", "planche", "sheet"),
    ("archlux.export.wilson", "intervalle_wilson", "wilson_interval"),
    ("archlux.data.chargeurs", "AppartementMSD", "MSDApartment"),
    ("archlux.data.chargeurs", "StatistiquesChargement", "LoadStatistics"),
    ("archlux.data.chargeurs", "charger_msd", "load_msd"),
    ("archlux.data.chargeurs", "charger_etiquettes_sd", "load_sd_labels"),
    ("archlux.data.chargeurs", "etiqueter", "label"),
    ("archlux.data.chargeurs", "decouper_par_site", "split_by_site"),
    ("archlux.data.chargeurs", "TYPES_EXCLUS", "EXCLUDED_TYPES"),
    ("archlux.data.corruption", "corrompre", "corrupt"),
    ("archlux.data.decoupage", "Decoupage", "Split"),
    ("archlux.data.decoupage", "charger_decoupage", "load_split"),
    ("archlux.data.dedup", "distance_cotes", "side_distance"),
    ("archlux.data.imputation", "imputer_ouvertures", "impute_openings"),
    ("archlux.data.synthese", "generer_corpus", "generate_corpus"),
    ("archlux.data.synthese", "TAILLE_MAX", "MAX_SIZE"),
    ("archlux.bench", "Decoupage", "Split"),
    ("archlux.bench", "Intervalle", "Interval"),
    ("archlux.bench", "LigneBrute", "RawRow"),
    ("archlux.bench", "RapportBanc", "BenchReport"),
    ("archlux.bench", "Resultat", "Result"),
    ("archlux.bench", "StrateOrientation", "OrientationStratum"),
    ("archlux.bench", "bootstrap_apparie", "paired_bootstrap"),
    ("archlux.bench", "charger_decoupage", "load_split"),
    ("archlux.bench", "deriver", "derive"),
    ("archlux.bench", "emettre", "emit"),
    ("archlux.bench", "puissance", "power"),
    ("archlux.bench.graines", "deriver", "derive"),
    ("archlux.bench.manifeste", "emettre", "emit"),
    ("archlux.bench.protocole", "Decoupage", "Split"),
    ("archlux.bench.protocole", "charger_decoupage", "load_split"),
    ("archlux.bench.rapport", "RapportBanc", "BenchReport"),
    ("archlux.bench.rapport", "StrateOrientation", "OrientationStratum"),
    ("archlux.bench.run", "LigneBrute", "RawRow"),
    ("archlux.bench.run", "Resultat", "Result"),
    ("archlux.bench.stats", "Intervalle", "Interval"),
    ("archlux.bench.stats", "bootstrap_apparie", "paired_bootstrap"),
    ("archlux.bench.stats", "puissance", "power"),
    # Found untested by the review of the stack (PRs #11, #14, #15).
    ("archlux.export", "diagnostiquer", "diagnose"),
    ("archlux.bench", "ModeleTrace", "ModelTrace"),
    ("archlux.orient.circulaire", "difference_angulaire", "angular_difference"),
    ("archlux.orient.circulaire", "direction_dominante", "dominant_direction"),
    ("archlux.orient.circulaire", "regression_circulaire_lineaire", "circular_linear_regression"),
    ("archlux.orient.circulaire", "variance_circulaire", "circular_variance"),
    ("archlux.active.selection", "StrategieAcquisition", "AcquisitionStrategy"),
    ("archlux.uq", "stratifier_par_orientation", "stratify_by_orientation"),
    ("archlux.uq.fiabilite", "stratifier_par_orientation", "stratify_by_orientation"),
    ("archlux.data.chargeurs", "COLONNE_SOLEIL_DEFAUT", "DEFAULT_SUN_COLUMN"),
    ("archlux.data.dedup", "SEUIL_HAUSDORFF_M", "HAUSDORFF_THRESHOLD_M"),
    ("archlux.data.dedup", "empreinte_geometrique", "geometric_fingerprint"),
    ("archlux.data.dedup", "paires_quasi_identiques", "near_duplicate_pairs"),
    ("archlux.data.imputation", "RATIO_BAIE_DEFAUT", "DEFAULT_OPENING_RATIO"),
    ("archlux.geom.graphe", "reduction_transitive", "transitive_reduction"),
    ("archlux.geom.rectilineaire", "contraintes_fusion", "merge_constraints"),
]


@pytest.mark.parametrize(("module", "old", "new"), ALIASES)
def test_the_old_name_is_the_new_object_and_warns(module: str, old: str, new: str) -> None:
    target = importlib.import_module(module)
    message = f"{module}.{old} is deprecated, use {module}.{new}"
    with pytest.warns(DeprecationWarning, match=message.replace(".", r"\.")):
        legacy = getattr(target, old)
    assert legacy is getattr(target, new)


@pytest.mark.parametrize(("module", "old", "new"), ALIASES)
def test_a_from_import_warns_exactly_once(module: str, old: str, new: str) -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        exec(f"from {module} import {old}", {})
    assert sum(issubclass(w.category, DeprecationWarning) for w in caught) == 1


@pytest.mark.parametrize(("module", "old", "new"), ALIASES)
def test_old_names_are_not_advertised(module: str, old: str, new: str) -> None:
    target = importlib.import_module(module)
    assert old not in getattr(target, "__all__", [])
    assert new in target.__all__


def test_the_old_lmo_coupes_module_still_serves_every_name() -> None:
    """``archlux.lmo.coupes`` became ``archlux.lmo.cuts``: each old name warns and resolves."""
    import archlux.lmo.coupes as legacy_module
    import archlux.lmo.cuts as cuts

    for old, new in legacy_module._NAMES.items():
        with pytest.warns(DeprecationWarning, match=f"archlux.lmo.cuts.{new}"):
            assert getattr(legacy_module, old) is getattr(cuts, new)
