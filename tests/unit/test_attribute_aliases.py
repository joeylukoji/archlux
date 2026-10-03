"""Renamed fields, class constants and methods stay readable, deprecated, until 1.0.0.

ADR 0001 rule 6 applied to the attributes renamed in chantier E, wave 1b, through
``archlux._deprecation.renamed_attributes``: the old name reads the new attribute and warns,
and an old field name stays accepted as a constructor keyword.
"""

from __future__ import annotations

import importlib
import warnings
from dataclasses import FrozenInstanceError, dataclass

import pytest

from archlux._deprecation import renamed_attributes

RENAMED = [
    (
        "archlux.active.loop",
        "ActiveReport",
        {
            "largeur_intervalle_finale": "final_interval_width",
            "historique_largeur": "width_history",
            "calibration_independante": "independent_calibration",
        },
    ),
    (
        "archlux.active.loop",
        "Loop",
        {"simulateur": "simulator", "part_calibration": "calibration_share"},
    ),
    ("archlux.active.selection", "UncertaintyTimesDensity", {"selectionner": "select"}),
    ("archlux.active.selection", "RandomStrategy", {"selectionner": "select"}),
    (
        "archlux.light.analytic",
        "AnalyticSurrogate",
        {
            "indicateur_vise": "target_indicator",
            "FACTEUR_PROFONDEUR": "DEPTH_FACTOR",
            "HAUTEUR_LINTEAU": "HEAD_HEIGHT",
            "KAPPA_SUD": "KAPPA_SOUTH",
            "FACTEURS_SECTEUR": "SECTOR_FACTORS",
        },
    ),
    (
        "archlux.light.base",
        "DenseSurrogate",
        {
            "indicateur_vise": "target_indicator",
            "largeur": "width",
            "echelle_base": "base_scale",
            "decalage_base": "base_offset",
        },
    ),
    (
        "archlux.light.learned",
        "LearnedSurrogate",
        {
            "chemin_poids": "weights_path",
            "empreinte_poids": "weights_fingerprint",
            "gele": "frozen",
            "indicateur_vise": "target_indicator",
        },
    ),
    ("archlux.light.objective", "Daylight", {"q_chapeau": "q_hat", "pessimiste": "pessimistic"}),
    (
        "archlux.light.split_flux",
        "SplitFluxOracle",
        {"indicateur_vise": "target_indicator", "ECHELLE_DF": "DF_SCALE"},
    ),
    (
        "archlux.light.validation",
        "GradientReport",
        {
            "erreur_relative_max": "max_relative_error",
            "cosinus_moyen": "mean_cosine",
            "accord_de_signe": "sign_agreement",
            "graine": "seed",
            "conforme": "passed",
        },
    ),
    ("archlux.orient.circular", "RegressionResult", {"residus": "residuals"}),
    ("archlux.uq.conformal", "Calibration", {"empreinte_jeu": "data_fingerprint"}),
    (
        "archlux.uq.conformal",
        "ConformalCalibrator",
        {"empreinte_jeu": "data_fingerprint", "borne": "bound"},
    ),
    (
        "archlux.uq.drift",
        "DriftDiagnostic",
        {"echangeable": "exchangeable", "statistique": "statistic"},
    ),
    (
        "archlux.uq.drift",
        "DriftReport",
        {
            "derive_moyenne": "mean_drift",
            "tendance_pente": "trend_slope",
            "tendance_pvalue": "trend_pvalue",
            "n_echantillons": "n_samples",
        },
    ),
    ("archlux.uq.registry", "DataManagement", {"racine": "root"}),
]


@pytest.mark.parametrize(("module", "name", "renames"), RENAMED, ids=lambda v: str(v))
def test_each_old_attribute_names_an_existing_new_one(
    module: str, name: str, renames: dict[str, str]
) -> None:
    cls = getattr(importlib.import_module(module), name)
    for old, new in renames.items():
        assert hasattr(cls, new) or new in getattr(cls, "__dataclass_fields__", {}), new
        with pytest.warns(DeprecationWarning, match=f"{name}.{old} is deprecated, use {new}"):
            getattr(cls, old)


def test_an_old_field_reads_the_new_one_and_an_old_keyword_builds_it() -> None:
    from archlux.light.analytic import AnalyticSurrogate
    from archlux.light.objective import Daylight

    with pytest.warns(DeprecationWarning, match=r"Daylight\.__init__\(q_chapeau=\.\.\.\)"):
        objective = Daylight(AnalyticSurrogate(), q_chapeau=2.0)  # type: ignore[call-arg]
    assert objective.q_hat == 2.0
    with pytest.warns(DeprecationWarning, match=r"Daylight\.q_chapeau is deprecated"):
        assert objective.q_chapeau == 2.0  # type: ignore[attr-defined]


def test_an_old_class_constant_reads_on_the_class() -> None:
    from archlux.light.analytic import AnalyticSurrogate

    with pytest.warns(DeprecationWarning, match="use KAPPA_SOUTH"):
        assert AnalyticSurrogate.KAPPA_SUD == AnalyticSurrogate.KAPPA_SOUTH  # type: ignore[attr-defined]


def test_writing_an_old_name_writes_the_new_one_and_respects_frozen() -> None:
    @renamed_attributes({"chemin": "path"})
    @dataclass
    class Mutable:
        path: str

    @renamed_attributes({"chemin": "path"})
    @dataclass(frozen=True)
    class Frozen:
        path: str

    item = Mutable("a")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        item.chemin = "b"  # type: ignore[attr-defined]
        assert item.path == "b"
        with pytest.raises(FrozenInstanceError):
            Frozen("a").chemin = "b"  # type: ignore[attr-defined]


def test_the_warning_points_at_the_caller() -> None:
    from archlux.light.analytic import AnalyticSurrogate
    from archlux.light.objective import Daylight

    objective = Daylight(AnalyticSurrogate(), q_hat=1.0)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        objective.pessimiste  # type: ignore[attr-defined]  # noqa: B018
    assert caught[0].filename == __file__
