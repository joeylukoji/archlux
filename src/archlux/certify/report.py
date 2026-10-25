"""Text rendering of the certificate. The two kinds of guarantee stay separate.

No line of the report mixes the exact and the probabilistic, and no composite score
aggregates them: a reader must be able to tell, for every figure, whether it is a proof or
a prediction.
"""

from __future__ import annotations

from archlux._deprecation import Alias, lazy_aliases, renamed_parameters
from archlux._version import __version__
from archlux.certify.repair import render_repair
from archlux.types import (
    INDICATOR_SENSE,
    Certificate,
    GeometricProof,
    Manifest,
    OptimizationStatus,
    PerformanceBound,
    ValidationSummary,
)

__all__ = ["render", "render_repair"]

_OUT_OF_SCOPE = (
    "Summer comfort, technical systems, materials: out of scope "
    "(frozen split-flux oracle, not an LM-83 sDA)"
)


def _version() -> str:
    """Version of the source code, never stale install metadata.

    Returns
    -------
    str
        The package version from the source code.
    """
    return __version__


def _fmt(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}"


def _verdict(ok: bool) -> str:
    return "verified" if ok else "failed"


_BANNERS = {
    None: "[EXACT]",
    "exact": "[EXACT]",
    "numeric": "[NUMERIC]",
    "refused": "[REFUSED]",
}
"""Geometry banner per validator evidence. ``None``: a certificate without the
independent validation (built by hand, or before it existed) keeps its historical label."""


def _validation_lines(validation: ValidationSummary | None) -> str:
    if validation is None:
        return ""
    lines = [
        f"\n  Independent check      {len(validation.checked)} hard constraints satisfied"
        + (f", {len(validation.failing)} failing" if validation.failing else "")
    ]
    if validation.evidence == "numeric":
        lines.append(
            "\n  numerical validation: floating-point checks with tolerance, not an exact proof"
        )
    return "".join(lines)


def _section_geometry(proof: GeometricProof, validation: ValidationSummary | None) -> str:
    banner = _BANNERS[None if validation is None else validation.evidence]
    overlap = "none" if not proof.overlap else "present"
    gaps = "none" if not proof.gaps else "present"
    areas = "ok" if proof.areas_ok else "insufficient"
    structure = "yes" if proof.structure_kept else "no"
    displacement = f"{_fmt(proof.max_displacement)} m"
    return (
        f"GEOMETRY{banner:>47}\n"
        f"  Overlap                {overlap:<13} {_verdict(not proof.overlap)}\n"
        f"  Gaps                   {gaps:<13} {_verdict(not proof.gaps)}\n"
        f"  Minimum areas          {areas:<13} {_verdict(proof.areas_ok)}\n"
        f"  Structure kept         {structure:<13} {_verdict(proof.structure_kept)}\n"
        f"  Maximum displacement   {displacement}"
        f"{_validation_lines(validation)}"
    )


def _optimization_line(optimization: OptimizationStatus | None) -> str:
    if optimization is None:
        return ""
    if optimization.converged:
        return f"\n  optimizer: converged after {optimization.iterations} iterations"
    return (
        f"\n  optimizer: stopped ({optimization.status}) after {optimization.iterations} "
        "iterations: geometrically valid, NOT an optimised plan"
    )


def _section_performance(
    bound: PerformanceBound | None, optimization: OptimizationStatus | None = None
) -> str:
    if bound is None:
        body = "  NOT EVALUABLE: no calibration, or drift (exchangeability broken)"
        banner = "[PREDICTION: not evaluable]"
    else:
        pct = f"{bound.coverage * 100.0:.0f}"
        if bound.regime == "policy_calibrated":
            banner = f"[PREDICTION: policy-calibrated, coverage {pct} %]"
        elif bound.coverage_guaranteed:
            banner = f"[PREDICTION: coverage {pct} %]"
        else:
            # Batch 1.6: the optimizer chose this plan, the coverage is not guaranteed.
            banner = "[PREDICTION: selected plan, coverage NOT guaranteed]"
        if INDICATOR_SENSE[bound.indicator] == "<=":
            line = (
                f"  {bound.indicator}   <= {_fmt(bound.upper)}   "
                f"(predicted {_fmt(bound.value)}, "
                f"margin {_fmt(bound.upper - bound.value)})"
            )
        else:
            line = (
                f"  {bound.indicator}   >= {_fmt(bound.lower)}   "
                f"(predicted {_fmt(bound.value)}, "
                f"margin {_fmt(bound.value - bound.lower)})"
            )
        body = f"{line}\n  calibration: {bound.n_calibration} evaluations of the frozen oracle"
        if bound.regime == "policy_calibrated":
            body += (
                "\n  policy-calibrated regime: scores computed on the outputs of this frozen "
                f"policy; coverage {pct} % marginally over inputs exchangeable"
                "\n  with the calibration inputs, not for this plan individually"
            )
        if not bound.coverage_guaranteed:
            body += (
                "\n  selected regime: the plan was chosen by the optimizer; the nominal "
                f"coverage of {pct} % assumes a plan exchangeable with the calibration"
                "\n  (winner's curse). Re-evaluate this plan with the oracle before "
                "publishing a coverage."
            )
    return f"PERFORMANCE                        {banner}\n{body}{_optimization_line(optimization)}"


def _section_diagnostic(duals: tuple[tuple[str, float], ...]) -> str:
    if not duals:
        body = "  (no active constraint above the threshold)"
    else:
        body = "\n".join(f"  {label}" for label, _price in duals)
    return f"DIAGNOSTIC\n{body}"


def _header(manifest: Manifest | None) -> str:
    if manifest is None:
        return f"CERTIFICATE                             archlux {_version()}"
    return (
        f"CERTIFICATE                             archlux {manifest.version}     "
        f"seed {manifest.seed}"
    )


@renamed_parameters({"certificat": "certificate"})
def render(certificate: Certificate) -> str:
    """Render the certificate as readable text.

    Parameters
    ----------
    certificate
        Certificate to render.

    Returns
    -------
    str
        A report of two kinds. If ``certificate.performance`` is ``None``, the
        performance section says ``NOT EVALUABLE``: never a default interval. The scope
        section ``NOT EVALUABLE`` is **always** present.
    """
    parts = [
        _header(certificate.manifest),
        "",
        _section_geometry(certificate.geometry, certificate.validation),
        "",
        _section_performance(certificate.performance, certificate.optimization),
        "",
        _section_diagnostic(certificate.duals),
        "",
        "NOT EVALUABLE",
        f"  {_OUT_OF_SCOPE}",
    ]
    return "\n".join(parts) + "\n"


__getattr__ = lazy_aliases(
    __name__,
    {
        "rendre": Alias(render, "archlux.certify.report.render"),
    },
)
