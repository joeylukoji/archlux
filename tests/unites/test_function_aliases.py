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
