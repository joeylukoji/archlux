"""Renamed keyword parameters of public functions stay accepted, deprecated, until 1.0.0.

ADR 0001 rule 6 applied to parameters: ``to_ifc(plan, chemin=...)`` still works and warns.
Fields and methods of classes were renamed without alias (CHANGELOG, waves 3 and 5); this
table covers module-level functions only. It was built by comparing every public signature
of revision ``b35a3c8`` (before the English rename) with the current one.
"""

from __future__ import annotations

import importlib
import inspect
import warnings

import pytest

from archlux._deprecation import renamed_parameters

RENAMED = [
    ("archlux.api", "gradient_distance", {"x_propose": "x_proposed"}),
    (
        "archlux.api",
        "legalize",
        {"fusions": "merges", "pavage": "tiling", "budget_reparation": "repair_budget"},
    ),
    ("archlux.bench.seeds", "derive", {"nom": "name"}),
    (
        "archlux.bench.manifest",
        "emit",
        {
            "empreinte_donnees": "data_fingerprint",
            "decoupage": "split",
            "parametres": "parameters",
            "modele": "model",
        },
    ),
    ("archlux.bench.report", "report", {"resultat": "result", "n_secteurs": "n_sectors"}),
    (
        "archlux.bench.run",
        "run",
        {
            "empreinte_donnees": "data_fingerprint",
            "decoupage": "split",
            "modele": "model",
            "repertoire": "directory",
            "parametres": "parameters",
        },
    ),
    ("archlux.bench.stats", "holm", {"p_valeurs": "p_values"}),
    ("archlux.bench.stats", "power", {"effet": "effect"}),
    (
        "archlux.certify.bound",
        "build_bound",
        {"valeur": "value", "derive": "drift", "incertitude": "uncertainty"},
    ),
    ("archlux.certify.dual", "translate_duals", {"duaux": "duals", "seuil": "threshold"}),
    ("archlux.certify.proof", "verify_exactly", {"fusions": "merges"}),
    ("archlux.certify.report", "render", {"certificat": "certificate"}),
    (
        "archlux.data.loaders",
        "load_msd",
        {
            "chemin": "path",
            "referentiel": "regulation",
            "max_pieces": "max_rooms",
            "types_exclus": "excluded_types",
            "statistiques": "stats",
            "limite": "limit",
            "tolerance_calage": "snap_tolerance",
            "tolerance_recollage": "stitch_tolerance",
        },
    ),
    ("archlux.data.loaders", "load_sd_labels", {"chemin": "path", "colonne": "column"}),
    (
        "archlux.data.loaders",
        "label",
        {"appartement": "apartment", "etiquettes": "labels", "couverture_min": "min_coverage"},
    ),
    ("archlux.data.loaders", "split_by_site", {"appartements": "apartments"}),
    ("archlux.data.splits", "load_split", {"chemin": "path"}),
    ("archlux.data.dedup", "near_duplicate_pairs", {"seuil": "threshold"}),
    ("archlux.export.dxf", "to_dxf", {"chemin": "path"}),
    ("archlux.export.ifc", "to_ifc", {"chemin": "path"}),
    ("archlux.export.svg", "render", {"contour": "outline", "titre": "title"}),
    (
        "archlux.export.svg",
        "compare",
        {"contour": "outline", "avant": "before", "apres": "after", "titres": "titles"},
    ),
    (
        "archlux.export.svg",
        "sheet",
        {"contour": "outline", "volets": "panels", "colonnes": "columns"},
    ),
    ("archlux.export.wilson", "wilson_interval", {"succes": "successes"}),
    ("archlux.feasibility", "is_feasible", {"programme": "program"}),
    ("archlux.geom.graph", "build_graph", {"pieces": "rooms", "ordre": "order"}),
    (
        "archlux.geom.tiling",
        "deduce_grid",
        {"support_min": "min_support", "budget_reparation": "repair_budget"},
    ),
    ("archlux.geom.tiling", "snap_to_grid", {"trame": "grid"}),
    ("archlux.geom.tiling", "tiling_constraints", {"trame": "grid"}),
    ("archlux.geom.tiling", "extend_tiling", {"trame": "grid"}),
    ("archlux.geom.polytope", "devectorize", {"gabarit": "template"}),
    ("archlux.geom.rectilinear", "decompose", {"polygone": "polygon", "type_piece": "room_type"}),
    (
        "archlux.geom.rectilinear",
        "minimum_area_shares",
        {"fusions": "merges", "referentiel": "regulation"},
    ),
    ("archlux.io.json_io", "manifest_to_dict", {"manifeste": "manifest"}),
    ("archlux.io.json_io", "from_dict", {"donnees": "data"}),
    ("archlux.io.json_io", "load", {"chemin": "path"}),
    ("archlux.io.json_io", "write", {"chemin": "path"}),
    ("archlux.light.base", "descriptors", {"baies": "glazing"}),
    ("archlux.light.tokens", "vector_to_tokens", {"baies": "glazing"}),
    ("archlux.light.protocol", "point_prediction", {"baies": "glazing"}),
    (
        "archlux.light.validation",
        "validate_gradient",
        {
            "substitut": "surrogate",
            "pas": "step",
            "seuil_signe": "sign_threshold",
        },  # lang-ok: old French names
    ),
    ("archlux.lmo.cuts", "area_cut", {"a_min": "min_area", "piece": "room"}),
    ("archlux.lmo.cuts", "violated_areas", {"pieces": "rooms"}),
    (
        "archlux.lmo.cuts",
        "solve_with_areas",
        {"pieces": "rooms", "depart": "start", "duaux": "duals"},
    ),
    ("archlux.lmo.cuts", "inner_area_constraints", {"pieces": "rooms"}),
    ("archlux.lmo.solver", "solve", {"depart": "start", "coupes": "cuts", "duaux": "duals"}),
    (
        "archlux.orient.circular",
        "dominant_direction",
        {"poids": "weights", "degres": "degrees", "periode": "period"},
    ),
    ("archlux.uq.conformal", "bound", {"valeur": "value", "incertitude": "uncertainty"}),
    ("archlux.uq.registry", "freeze_and_issue", {"modele": "model", "horodatage": "timestamp"}),
    (
        "archlux.uq.registry",
        "issue_token",
        {"empreinte_poids": "weights_fingerprint", "horodatage_gel": "freeze_timestamp"},
    ),
    ("archlux.uq.registry", "open_calibration", {"jeton": "token", "racine": "root"}),
    ("archlux.active.density", "kernel_density", {"candidats": "candidates", "bande": "bandwidth"}),
    ("archlux.data.corruption", "corrupt", {"n_pieces": "n_rooms"}),
    ("archlux.geom.polytope", "build_polytope", {"ordre": "order"}),
    ("archlux.geom.rectilinear", "recompose", {"piece": "room"}),
    ("archlux.geom.rectilinear", "merge_constraints", {"piece": "room"}),
    ("archlux.geom.rectilinear", "overlap_constraints", {"piece": "room"}),
    ("archlux.geom.rectilinear", "extend_merges", {"piece": "room"}),
    ("archlux.light.tokens", "permute_rooms", {"ordre": "order"}),
    ("archlux.orient.circular", "encode", {"harmoniques": "harmonics"}),
    ("archlux.orient.circular", "encode_orientation", {"harmoniques": "harmonics"}),
    ("archlux.orient.circular", "circular_mean", {"degres": "degrees"}),
    ("archlux.orient.circular", "concentration", {"degres": "degrees"}),
    ("archlux.orient.circular", "circular_variance", {"degres": "degrees"}),
    ("archlux.orient.circular", "rayleigh", {"degres": "degrees"}),
    ("archlux.orient.circular", "stratify", {"degres": "degrees", "n_secteurs": "n_sectors"}),
    ("archlux.solve.frank_wolfe", "restrict_to_budget", {"centre": "center"}),
    ("archlux.uq.drift", "measure_drift", {"verites": "truths"}),
    (
        "archlux.uq.reliability",
        "crps",
        {"verites": "truths", "incertitudes": "uncertainties"},
    ),
    (
        "archlux.uq.reliability",
        "reliability_diagram",
        {"verites": "truths", "incertitudes": "uncertainties", "niveaux": "levels"},
    ),
    (
        "archlux.uq.reliability",
        "stratify_by_orientation",
        {"degres": "degrees", "n_secteurs": "n_sectors"},
    ),
]


def _function(module: str, name: str) -> object:
    return getattr(importlib.import_module(module), name)


@pytest.mark.parametrize(("module", "name", "renames"), RENAMED, ids=lambda v: str(v))
def test_each_old_keyword_maps_to_a_parameter_of_the_new_signature(
    module: str, name: str, renames: dict[str, str]
) -> None:
    function = _function(module, name)
    assert vars(function)["__renamed_parameters__"] == renames
    parameters = inspect.signature(function).parameters  # type: ignore[arg-type]
    for old, new in renames.items():
        assert new in parameters, f"{name}: {new} is not a parameter"
        assert old not in parameters, f"{name}: {old} is still a parameter"


def test_the_old_keyword_warns_and_gives_the_same_result() -> None:
    from archlux.bench import holm

    expected = holm(p_values=[0.01, 0.04, 0.2])
    with pytest.warns(DeprecationWarning, match=r"holm\(p_valeurs=\.\.\.\) is deprecated"):
        assert holm(p_valeurs=[0.01, 0.04, 0.2]) == expected  # type: ignore[call-arg]


def test_legalize_still_accepts_its_french_keywords() -> None:
    import archlux as ax

    ctx = ax.Context(
        structure=ax.Structure(()),
        orientation=ax.Orientation(0.0),
        regulation=ax.Regulation((), 0.5),
        outline=((0.0, 0.0), (4.0, 0.0), (4.0, 3.0), (0.0, 3.0)),
    )
    plan = ax.Plan(rooms=(ax.Room(id="a", type="living", x=0.0, y=0.0, w=4.0, h=3.0),))
    expected = ax.legalize(plan, ctx, tiling=True, repair_budget=2)
    with pytest.warns(DeprecationWarning, match="use tiling="):
        old = ax.legalize(plan, ctx, pavage=True, budget_reparation=2)  # type: ignore[call-arg]
    assert old.rooms == expected.rooms


def test_the_warning_points_at_the_caller() -> None:
    from archlux.export import wilson_interval

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        wilson_interval(succes=3, n=10)  # type: ignore[call-arg]
    assert caught[0].filename == __file__


def test_the_old_and_the_new_keyword_together_are_refused() -> None:
    from archlux.bench import holm

    with pytest.raises(TypeError, match=r"both p_valeurs= \(deprecated\) and p_values="):
        holm(p_values=[0.1], p_valeurs=[0.1])  # type: ignore[call-arg]


def test_the_new_keyword_and_positional_arguments_do_not_warn() -> None:
    from archlux.bench import holm

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert holm([0.01, 0.2]) == holm(p_values=[0.01, 0.2])


def test_the_decorator_keeps_the_name_the_doc_and_the_signature() -> None:
    def write(path: str, *, validate: bool = True) -> str:
        """Write."""
        return path

    wrapped = renamed_parameters({"chemin": "path"})(write)
    assert wrapped.__name__ == "write"
    assert wrapped.__doc__ == "Write."
    assert inspect.signature(wrapped) == inspect.signature(write)
