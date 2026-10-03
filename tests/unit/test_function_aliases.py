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
    ("archlux.certify.bound", "construire_borne", "build_bound"),
    ("archlux.certify.dual", "traduire_duaux", "translate_duals"),
    ("archlux.certify.report", "rendre", "render"),
    ("archlux.export.svg", "rendre", "render"),
    ("archlux.feasibility", "CertificatFaisabilite", "FeasibilityCertificate"),
    ("archlux.light", "Substitut", "Surrogate"),
    ("archlux.light", "SubstitutAnalytique", "AnalyticSurrogate"),
    ("archlux.light.protocol", "Substitut", "Surrogate"),
    ("archlux.light.protocol", "Baies", "Glazing"),
    ("archlux.light.protocol", "SubstitutParPiece", "PerRoomSurrogate"),
    ("archlux.io.json_io", "charger", "load"),
    ("archlux.io.json_io", "VERSION_SCHEMA", "SCHEMA_VERSION"),
    ("archlux.io.json_io", "ecrire", "write"),
    ("archlux.io.json_io", "vers_dict", "to_dict"),
    ("archlux.io.json_io", "depuis_dict", "from_dict"),
    ("archlux.io.json_io", "manifeste_vers_dict", "manifest_to_dict"),
    ("archlux.geom.graph", "OrdreRelatif", "RelativeOrder"),
    ("archlux.geom.graph", "GrapheContraintes", "ConstraintGraph"),
    ("archlux.geom.graph", "deduire_ordre", "deduce_order"),
    ("archlux.geom.graph", "construire_graphe", "build_graph"),
    ("archlux.geom.polytope", "construire_polytope", "build_polytope"),
    ("archlux.geom.polytope", "figer_contacts", "freeze_contacts"),
    ("archlux.geom.polytope", "vectoriser", "vectorize"),
    ("archlux.geom.polytope", "devectoriser", "devectorize"),
    ("archlux.geom.polytope", "etendre_ecarts_l1", "extend_l1_slack"),
    ("archlux.geom.polytope", "CHAMPS", "FIELDS"),
    ("archlux.geom.tiling", "Trame", "Grid"),
    ("archlux.geom.tiling", "deduire_trame", "deduce_grid"),
    ("archlux.geom.tiling", "contraintes_pavage", "tiling_constraints"),
    ("archlux.geom.tiling", "etendre_pavage", "extend_tiling"),
    ("archlux.geom.rectilinear", "PieceRectilineaire", "RectilinearRoom"),
    ("archlux.geom.rectilinear", "decomposer", "decompose"),
    ("archlux.geom.rectilinear", "recomposer", "recompose"),
    ("archlux.geom.rectilinear", "etendre_fusions", "extend_merges"),
    ("archlux.geom.rectilinear", "FUSION_DROIT", "MERGE_RIGHT"),
    ("archlux.geom.rectilinear", "FUSION_HAUT", "MERGE_TOP"),
    ("archlux.geom.diagnostic", "diagnostiquer", "diagnose"),
    ("archlux.lmo.solver", "SolutionLP", "LPSolution"),
    ("archlux.lmo.solver", "resoudre", "solve"),
    ("archlux.lmo.solver", "vider_cache", "clear_cache"),
    ("archlux.export.pathologies", "diagnostiquer", "diagnose"),
    ("archlux.light.analytic", "facteur_secteur", "sector_factor"),
    ("archlux.light.learned", "SubstitutAppris", "LearnedSurrogate"),
    ("archlux.light.base", "SubstitutDense", "DenseSurrogate"),
    ("archlux.light.base", "descripteurs", "descriptors"),
    ("archlux.light.tokens", "permuter_pieces", "permute_rooms"),
    ("archlux.light.tokens", "plan_vers_vecteur", "plan_to_vector"),
    ("archlux.light.tokens", "plan_vers_jetons", "plan_to_tokens"),
    ("archlux.light.tokens", "vecteur_vers_jetons", "vector_to_tokens"),
    ("archlux.light.tokens", "DIM_JETON", "TOKEN_DIM"),
    ("archlux.light.tokens", "CHAMPS_PAR_PIECE", "FIELDS_PER_ROOM"),
    ("archlux.light.split_flux", "facteur_lumiere_jour", "daylight_factor"),
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
    ("archlux.uq.conformal", "borner", "bound"),
    ("archlux.uq.conformal", "n_minimal_conforme", "minimal_n_conformal"),
    ("archlux.uq.conformal", "quantile_conforme", "conformal_quantile"),
    ("archlux.uq.drift", "DiagnosticDerive", "DriftDiagnostic"),
    ("archlux.uq.drift", "RapportDerive", "DriftReport"),
    ("archlux.uq.drift", "controler_derive", "check_drift"),
    ("archlux.uq.drift", "mesurer_derive", "measure_drift"),
    ("archlux.uq.registry", "GestionDonnees", "DataManagement"),
    ("archlux.uq.registry", "JetonCalibration", "CalibrationToken"),
    ("archlux.uq.registry", "emettre_jeton", "issue_token"),
    ("archlux.uq.registry", "geler_et_emettre", "freeze_and_issue"),  # lang-ok: French alias name
    ("archlux.uq.registry", "ouvrir_calibration", "open_calibration"),
    ("archlux.active", "Aleatoire", "RandomStrategy"),
    ("archlux.active", "RapportActif", "ActiveReport"),
    ("archlux.active", "densite_noyau", "kernel_density"),
    ("archlux.active.loop", "RapportActif", "ActiveReport"),
    ("archlux.active.density", "densite_noyau", "kernel_density"),
    ("archlux.active.selection", "Aleatoire", "RandomStrategy"),
    ("archlux.orient.circular", "ResultatRegression", "RegressionResult"),
    ("archlux.orient.circular", "encoder", "encode_orientation"),
    ("archlux.orient.circular", "moyenne_circulaire", "circular_mean"),
    ("archlux.orient.circular", "stratifier", "stratify"),
    ("archlux.export", "DiagnosticPathologie", "PathologyDiagnostic"),
    ("archlux.export", "RapportExport", "ExportReport"),
    ("archlux.export", "intervalle_wilson", "wilson_interval"),
    ("archlux.export.ifc", "RapportExport", "ExportReport"),
    ("archlux.export.svg", "rendre", "render"),
    ("archlux.export.svg", "comparer", "compare"),
    ("archlux.export.svg", "planche", "sheet"),
    ("archlux.export.wilson", "intervalle_wilson", "wilson_interval"),
    ("archlux.data.loaders", "AppartementMSD", "MSDApartment"),
    ("archlux.data.loaders", "StatistiquesChargement", "LoadStatistics"),
    ("archlux.data.loaders", "charger_msd", "load_msd"),
    ("archlux.data.loaders", "charger_etiquettes_sd", "load_sd_labels"),
    ("archlux.data.loaders", "etiqueter", "label"),
    ("archlux.data.loaders", "decouper_par_site", "split_by_site"),
    ("archlux.data.loaders", "TYPES_EXCLUS", "EXCLUDED_TYPES"),
    ("archlux.data.corruption", "corrompre", "corrupt"),
    ("archlux.data.splits", "Decoupage", "Split"),
    ("archlux.data.splits", "charger_decoupage", "load_split"),
    ("archlux.data.dedup", "distance_cotes", "side_distance"),
    ("archlux.data.imputation", "imputer_ouvertures", "impute_openings"),
    ("archlux.data.synthetic", "generer_corpus", "generate_corpus"),
    ("archlux.data.synthetic", "TAILLE_MAX", "MAX_SIZE"),
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
    ("archlux.bench.seeds", "deriver", "derive"),
    ("archlux.bench.manifest", "emettre", "emit"),
    ("archlux.bench.protocol", "Decoupage", "Split"),
    ("archlux.bench.protocol", "charger_decoupage", "load_split"),
    ("archlux.bench.report", "RapportBanc", "BenchReport"),
    ("archlux.bench.report", "StrateOrientation", "OrientationStratum"),
    ("archlux.bench.run", "LigneBrute", "RawRow"),
    ("archlux.bench.run", "Resultat", "Result"),
    ("archlux.bench.stats", "Intervalle", "Interval"),
    ("archlux.bench.stats", "bootstrap_apparie", "paired_bootstrap"),
    ("archlux.bench.stats", "puissance", "power"),
    # Found untested by the review of the stack (PRs #11, #14, #15).
    ("archlux.export", "diagnostiquer", "diagnose"),
    ("archlux.bench", "ModeleTrace", "ModelTrace"),
    ("archlux.orient.circular", "difference_angulaire", "angular_difference"),
    ("archlux.orient.circular", "direction_dominante", "dominant_direction"),
    ("archlux.orient.circular", "regression_circulaire_lineaire", "circular_linear_regression"),
    ("archlux.orient.circular", "variance_circulaire", "circular_variance"),
    ("archlux.active.selection", "StrategieAcquisition", "AcquisitionStrategy"),
    ("archlux.uq", "stratifier_par_orientation", "stratify_by_orientation"),
    ("archlux.uq.reliability", "stratifier_par_orientation", "stratify_by_orientation"),
    ("archlux.data.loaders", "COLONNE_SOLEIL_DEFAUT", "DEFAULT_SUN_COLUMN"),
    ("archlux.data.dedup", "SEUIL_HAUSDORFF_M", "HAUSDORFF_THRESHOLD_M"),
    ("archlux.data.dedup", "empreinte_geometrique", "geometric_fingerprint"),
    ("archlux.data.dedup", "paires_quasi_identiques", "near_duplicate_pairs"),
    ("archlux.data.imputation", "RATIO_BAIE_DEFAUT", "DEFAULT_OPENING_RATIO"),
    ("archlux.geom.graph", "reduction_transitive", "transitive_reduction"),
    ("archlux.geom.rectilinear", "contraintes_fusion", "merge_constraints"),
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
