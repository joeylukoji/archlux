"""Uncertainty quantification: conformal calibration and drift control."""

from __future__ import annotations

from archlux._deprecation import Alias, lazy_aliases
from archlux.uq.conforme import Calibration, ConformalCalibrator, bound, conformal_quantile
from archlux.uq.derive import DriftDiagnostic, DriftReport, check_drift, measure_drift
from archlux.uq.fiabilite import crps, reliability_diagram, stratify_by_orientation
from archlux.uq.gestion import (
    CalibrationToken,
    DataManagement,
    freeze_and_issue,
    issue_token,
    open_calibration,
)

__all__ = [
    "Calibration",
    "CalibrationToken",
    "ConformalCalibrator",
    "DataManagement",
    "DriftDiagnostic",
    "DriftReport",
    "bound",
    "check_drift",
    "conformal_quantile",
    "crps",
    "freeze_and_issue",
    "issue_token",
    "measure_drift",
    "open_calibration",
    "reliability_diagram",
    "stratify_by_orientation",
]

__getattr__ = lazy_aliases(
    __name__,
    {
        "CalibrateurConforme": Alias(ConformalCalibrator, "archlux.uq.ConformalCalibrator"),
        "DiagnosticDerive": Alias(DriftDiagnostic, "archlux.uq.DriftDiagnostic"),
        "GestionDonnees": Alias(DataManagement, "archlux.uq.DataManagement"),
        "JetonCalibration": Alias(CalibrationToken, "archlux.uq.CalibrationToken"),
        "RapportDerive": Alias(DriftReport, "archlux.uq.DriftReport"),
        "borner": Alias(bound, "archlux.uq.bound"),
        "controler_derive": Alias(check_drift, "archlux.uq.check_drift"),
        "diagramme_fiabilite": Alias(reliability_diagram, "archlux.uq.reliability_diagram"),
        "emettre_jeton": Alias(issue_token, "archlux.uq.issue_token"),
        "geler_et_emettre": Alias(  # lang-ok: French alias name
            freeze_and_issue, "archlux.uq.freeze_and_issue"
        ),
        "mesurer_derive": Alias(measure_drift, "archlux.uq.measure_drift"),
        "ouvrir_calibration": Alias(open_calibration, "archlux.uq.open_calibration"),
        "quantile_conforme": Alias(conformal_quantile, "archlux.uq.conformal_quantile"),
        "stratifier_par_orientation": Alias(
            stratify_by_orientation, "archlux.uq.stratify_by_orientation"
        ),
    },
)
