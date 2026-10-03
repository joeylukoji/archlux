"""Files already migrated to English stay English (ADR 0001, PLAN.md batch E1).

``MIGRATED`` grows batch by batch; a file enters it once fully translated. The check is
deliberately simple (accented letters and common French function words) because its
job is to stop regressions, not to grade prose. Inline code and file paths are ignored:
they may legitimately name files that are not renamed yet.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

MIGRATED: tuple[str, ...] = (
    "src/archlux/_version.py",
    "src/archlux/tolerances.py",
    "src/archlux/solve/__init__.py",
    "src/archlux/certify/__init__.py",
    "src/archlux/certify/proof.py",
    "src/archlux/certify/farkas.py",
    "src/archlux/certify/preuve.py",
    "src/archlux/solve/trace.py",
    "src/archlux/solve/frank_wolfe.py",
    "tests/unit/test_trace_aliases.py",
    "tests/unit/test_module_shims.py",
    "tests/unit/test_oracle_aliases.py",
    "tests/unit/test_frank_wolfe_honesty.py",
    "tests/unit/test_rational_proof.py",
    "tests/unit/test_farkas.py",
    "tests/unit/test_regime.py",
    "tests/test_language.py",
    "tests/checkers.py",
    "tests/unit/test_svg.py",
    "tests/unit/test_load_bearing.py",
    "tests/unit/test_inner_area.py",
    "tests/unit/test_surrogate_conformance.py",
    "tests/test_hygiene.py",
    "benchmarks/guarantees/scenarios.py",
    "benchmarks/guarantees/measure.py",
    "benchmarks/guarantees/test_scenarios.py",
    "tests/docs/test_examples.py",
    "tests/properties/test_realistic_guarantees.py",
    "tests/unit/test_tolerances.py",
    "tests/unit/test_version.py",
    "tests/unit/test_tiling_grid.py",
    "tests/unit/test_l_rooms.py",
    "tests/properties/test_l_room_guarantees.py",
    "docs/adr/0001-english-first.md",
    "README.md",
    "docs/specification/ARCHITECTURE.md",
    "CONTRIBUTING.md",
    "AGENTS.md",
    "CLAUDE.md",
    "tests/properties/test_json_schema.py",
    "docs/adr/0002-milestone-criteria-rewritten.md",
    "docs/revues/j1.md",
    "docs/revues/j2.md",
    "docs/revues/j3.md",
    "docs/revues/j4.md",
    "docs/revues/j5.md",
    "docs/revues/j6.md",
    "docs/revues/j7.md",
    "docs/revues/j8.md",
    "docs/revues/j9.md",
    "docs/revues/index.md",
    "experiments/j7_msd_repair.py",
    "experiments/j7_msd_summary.py",
    "experiments/j7_msd_idempotence.py",
    "scripts/results.py",
    "tests/test_experiments.py",
    "experiments/j6_active.py",
    "experiments/j6_ifc.py",
    "src/archlux/seeds.py",
    "src/archlux/validation.py",
    "src/archlux/geom/graphe.py",
    "src/archlux/geom/graph.py",
    "src/archlux/geom/polytope.py",
    "src/archlux/geom/pavage.py",
    "src/archlux/geom/tiling.py",
    "src/archlux/geom/grid.py",
    "src/archlux/geom/grid_repair.py",
    "src/archlux/geom/rectilineaire.py",
    "src/archlux/geom/rectilinear.py",
    "src/archlux/geom/diagnostic.py",
    "src/archlux/lmo/solveur.py",
    "src/archlux/lmo/solver.py",
    "src/archlux/lmo/cuts.py",
    "src/archlux/uq/conforme.py",
    "src/archlux/uq/conformal.py",
    "src/archlux/uq/derive.py",
    "src/archlux/uq/drift.py",
    "src/archlux/uq/fiabilite.py",
    "src/archlux/uq/reliability.py",
    "src/archlux/uq/gestion.py",
    "src/archlux/uq/registry.py",
    "src/archlux/export/dxf.py",
    "src/archlux/export/ifc.py",
    "src/archlux/export/pathologie.py",
    "src/archlux/export/pathologies.py",
    "src/archlux/export/survie.py",
    "src/archlux/export/survival.py",
    "src/archlux/export/svg.py",
    "src/archlux/export/wilson.py",
    "src/archlux/export/__init__.py",
    "src/archlux/data/chargeurs.py",
    "src/archlux/data/loaders.py",
    "src/archlux/data/corruption.py",
    "src/archlux/data/decoupage.py",
    "src/archlux/data/splits.py",
    "src/archlux/data/dedup.py",
    "src/archlux/data/imputation.py",
    "src/archlux/data/synthese.py",
    "src/archlux/data/synthetic.py",
    "src/archlux/bench/graines.py",
    "src/archlux/bench/seeds.py",
    "src/archlux/bench/manifeste.py",
    "src/archlux/bench/manifest.py",
    "src/archlux/bench/protocole.py",
    "src/archlux/bench/protocol.py",
    "src/archlux/bench/rapport.py",
    "src/archlux/bench/report.py",
    "src/archlux/bench/run.py",
    "src/archlux/bench/stats.py",
    "src/archlux/bench/__init__.py",
    "src/archlux/uq/__init__.py",
    "src/archlux/active/boucle.py",
    "src/archlux/active/loop.py",
    "src/archlux/active/densite.py",
    "src/archlux/active/density.py",
    "src/archlux/active/selection.py",
    "src/archlux/active/__init__.py",
    "src/archlux/orient/circulaire.py",
    "src/archlux/orient/circular.py",
    "tests/unit/test_hostile_inputs.py",
    "tests/unit/test_type_invariants.py",
    "tests/unit/test_plan_exports.py",
    "tests/unit/test_import_cost.py",
    "tests/unit/test_typed_errors.py",
    "tests/unit/test_dual_units.py",
    "tests/unit/test_shared_types.py",
    "tests/unit/test_deprecation_helper.py",
    "tests/unit/test_exception_aliases.py",
    "tests/unit/test_model_aliases.py",
    "tests/unit/test_function_aliases.py",
    "docs/reference/schema-json.md",
    "tests/unit/test_json_room_types.py",
    "tests/properties/test_json_v1_upgrade.py",
    "src/archlux/errors.py",
    "src/archlux/io/json_io.py",
    "src/archlux/light/protocole.py",
    "src/archlux/light/protocol.py",
    "tests/test_doctests.py",
    "src/archlux/certify/borne.py",
    "src/archlux/certify/bound.py",
    "src/archlux/certify/rapport.py",
    "src/archlux/certify/report.py",
    "src/archlux/feasibility/__init__.py",
    "src/archlux/types.py",
    "src/archlux/api.py",
    "src/archlux/__init__.py",
    "src/archlux/erreurs.py",
    "tests/unit/test_rename_tool.py",
    "scripts/rename_identifiers.py",
    "scripts/rename_field.py",
    "tests/unit/test_rename_field_tool.py",
    "scripts/neutrality.py",
    "tests/test_neutrality.py",
    "src/archlux/_deprecation.py",
    "tests/unit/test_keyword_only_types.py",
    "docs/plans/phase-3-9-english-api.md",
    "src/archlux/arrays.py",
    "src/archlux/certify/dual.py",
    "tests/unit/test_seeds.py",
    "tests/unit/test_ifc_validation.py",
    "experiments/j5_coverage.py",
    "tests/unit/test_phase2_library.py",
    "experiments/j4_gradient.py",
    "experiments/j3_orientation.py",
    "tests/properties/test_milestone3_as_written.py",
    "experiments/j2_validity.py",
    "tests/properties/test_milestone2_as_written.py",
    "src/archlux/data/__init__.py",
    "src/archlux/feasibility/verdict.py",
    "src/archlux/geom/__init__.py",
    "src/archlux/io/__init__.py",
    "src/archlux/light/__init__.py",
    "src/archlux/light/analytic.py",
    "src/archlux/light/analytique.py",
    "src/archlux/light/appris.py",
    "src/archlux/light/base.py",
    "src/archlux/light/jetons.py",
    "src/archlux/light/learned.py",
    "src/archlux/light/objectif.py",
    "src/archlux/light/objective.py",
    "src/archlux/light/simulateur.py",
    "src/archlux/light/split_flux.py",
    "src/archlux/light/tokens.py",
    "src/archlux/light/validation.py",
    "src/archlux/lmo/__init__.py",
    "src/archlux/lmo/coupes.py",
    "src/archlux/orient/__init__.py",
    "docs/formulas/active-learning.md",
    "docs/formulas/analytic-surrogate.md",
    "docs/formulas/area-cuts.md",
    "docs/formulas/benchmark.md",
    "docs/formulas/bim-export.md",
    "docs/formulas/circular.md",
    "docs/formulas/exact-proof.md",
    "docs/formulas/farkas.md",
    "docs/formulas/frank-wolfe.md",
    "docs/formulas/gradient-validation.md",
    "docs/formulas/index.md",
    "docs/formulas/l1-epigraph.md",
    "docs/formulas/pipeline.md",
    "docs/formulas/rectilinear.md",
    "docs/formulas/relative-order.md",
    "docs/formulas/separated-polytope.md",
    "docs/formulas/sources.md",
    "docs/formulas/split-flux.md",
    "docs/formulas/statistics.md",
    "docs/formulas/tiling.md",
    "docs/formulas/tokens.md",
    "tests/__init__.py",
    "tests/conftest.py",
    "tests/docs/__init__.py",
    "tests/properties/__init__.py",
    "tests/properties/strategies.py",
    "tests/properties/test_architecture_invariants.py",
    "tests/properties/test_cuts.py",
    "tests/properties/test_graph.py",
    "tests/properties/test_json_io.py",
    "tests/properties/test_milestone2_acceptance.py",
    "tests/properties/test_milestone3_acceptance.py",
    "tests/properties/test_milestone4_acceptance.py",
    "tests/properties/test_milestone5_acceptance.py",
    "tests/properties/test_polytope.py",
    "tests/properties/test_proof.py",
    "tests/properties/test_solver.py",
    "tests/references/__init__.py",
    "tests/test_complexity.py",
    "tests/test_dependencies.py",
    "tests/test_identifiers.py",
    "tests/unit/__init__.py",
    "tests/unit/test_active.py",
    "tests/unit/test_analytic.py",
    "tests/unit/test_attribute_aliases.py",
    "tests/unit/test_bench_compare.py",
    "tests/unit/test_bench_run.py",
    "tests/unit/test_cache_lp.py",
    "tests/unit/test_calibration_registry.py",
    "tests/unit/test_circular.py",
    "tests/unit/test_conformal.py",
    "tests/unit/test_cuts.py",
    "tests/unit/test_dedup.py",
    "tests/unit/test_dense_surrogate.py",
    "tests/unit/test_derived_types.py",
    "tests/unit/test_diagnostic.py",
    "tests/unit/test_export.py",
    "tests/unit/test_extracted_helpers.py",
    "tests/unit/test_feasibility_package.py",
    "tests/unit/test_frank_wolfe.py",
    "tests/unit/test_frank_wolfe_steps.py",
    "tests/unit/test_graph.py",
    "tests/unit/test_json_malformed.py",
    "tests/unit/test_json_ranges.py",
    "tests/unit/test_lazy_facades.py",
    "tests/unit/test_legalize.py",
    "tests/unit/test_loaders.py",
    "tests/unit/test_milestone5_certificate.py",
    "tests/unit/test_opening.py",
    "tests/unit/test_per_room.py",
    "tests/unit/test_phase1_final_review.py",
    "tests/unit/test_polytope.py",
    "tests/unit/test_proof.py",
    "tests/unit/test_public_api.py",
    "tests/unit/test_rectilinear.py",
    "tests/unit/test_regulation.py",
    "tests/unit/test_reproducibility.py",
    "tests/unit/test_simulator.py",
    "tests/unit/test_solver.py",
    "tests/unit/test_splits.py",
    "tests/unit/test_surrogate_protocol.py",
    "tests/unit/test_tiling.py",
    "tests/unit/test_tokens.py",
    "tests/unit/test_validation_gradient.py",
    "tests/unit/test_vectorize.py",
    "scripts/prepare_data.py",
    "scripts/simulate.py",
    "scripts/validate_gradient.py",
    "experiments/j7_sd_labels.py",
    "experiments/j7_sd_per_room.py",
    "experiments/j8_generation.py",
    "experiments/j8_visuals.py",
    "experiments/j9_orientation.py",
    "experiments/README.md",
    "results/README.md",
    "results/j7_repair.md",
    "results/j7_sd_labels.md",
    "results/j7_sd_per_room.md",
    "results/j7_variance.md",
    "results/j8_divers.md",
    "results/j8_etoile.md",
    "results/j8_plausible.md",
    "results/j8_pilote.md",
    "results/visuals/index.md",
    "results/visuals/etoile/index.md",
    "results/visuals/plausible/index.md",
    "results/visuals/divers/index.md",
    "results/orientation/index.md",
)
"""Repository-relative paths that must contain no French prose."""

# Patterns are written with escapes and split literals so that this checker does not
# flag its own source.
# Latin-1 letters, minus the multiplication and division signs used in English prose.
_ACCENTED = re.compile(
    "["
    + chr(0xC0)
    + "-"
    + chr(0xD6)
    + chr(0xD8)
    + "-"
    + chr(0xF6)
    + chr(0xF8)
    + "-"
    + chr(0xFF)
    + chr(0x152)
    + chr(0x153)
    + chr(0x178)
    + "]"
)
_WORDS = (
    "l" + "e",
    "l" + "a",
    "l" + "es",
    "d" + "es",
    "u" + "ne",
    "e" + "st",
    "s" + "ont",
    "p" + "our",
    "a" + "vec",
    "d" + "ans",
    "s" + "ans",
    "m" + "ais",
    "d" + "onc",
    "q" + "ui",
    "q" + "ue",
    "p" + "as",
    "s" + "ur",
    "a" + "ux",
    "d" + "u",
    "c" + "ette",
    "l" + "eur",
    "f" + "ait",
    "d" + "e",
    "e" + "t",
    "u" + "n",
)
# Lower case or capitalized (`et`, `Et`), never all capitals: `ET` is the usual alias of
# xml.etree.ElementTree, not the French conjunction.
_FRENCH_WORDS = re.compile(
    r"\b(?:" + "|".join(f"[{w[0]}{w[0].upper()}]{w[1:]}" for w in _WORDS) + r")\b"
)
_CODE_OR_PATH = re.compile(r"`[^`]*`|[\w./-]+\.(?:md|py|json|csv|toml|yml)\b")
_LATIN_CITATION = re.compile(r"\bet al\.")
_LATEX_COMMAND = re.compile(r"\\+[A-Za-z]+")
"""``\\le``, ``\\qquad``, ``\\top``: LaTeX commands in formulas, not words."""


_ALLOWED_MARKER = "lang-ok:"
"""A line ending with ``# lang-ok: <reason>`` is exempt, e.g. a deprecated French alias
kept on purpose (ADR 0001, rule 6). The reason is mandatory and visible in review."""


def _french_markers(line: str) -> list[str]:
    if _ALLOWED_MARKER in line and line.split(_ALLOWED_MARKER, 1)[1].strip():
        return []
    # Underscores join words in identifiers: split them so that French names are seen.
    prose = _LATEX_COMMAND.sub(" ", _CODE_OR_PATH.sub(" ", line))
    prose = _LATIN_CITATION.sub(" ", prose).replace("_", " ")
    return _ACCENTED.findall(prose) + _FRENCH_WORDS.findall(prose)


_FRENCH_TRANSLATION_SUFFIX = ".fr.md"
"""The bilingual site puts the French translation of ``docs/x/page.md`` in
``docs/x/page.fr.md`` (``docs/specification/DOCUMENTATION.md``). Those pages are French
by design and are never checked, even if a broad entry of ``MIGRATED`` ever matches one."""


def _is_french_translation(relative: str) -> bool:
    return relative.endswith(_FRENCH_TRANSLATION_SUFFIX)


CHECKED: tuple[str, ...] = tuple(p for p in MIGRATED if not _is_french_translation(p))
"""``MIGRATED`` minus the French translations of the documentation site."""


@pytest.mark.parametrize("relative", CHECKED)
def test_migrated_files_contain_no_french(relative: str) -> None:
    path = ROOT / relative
    offending = [
        f"{relative}:{number}: {sorted(set(markers))} in {line.strip()[:80]!r}"
        for number, line in enumerate(path.read_text("utf-8").splitlines(), start=1)
        if (markers := _french_markers(line))
    ]
    assert not offending, "French prose in a migrated file:\n" + "\n".join(offending)


def test_every_migrated_path_exists() -> None:
    missing = [p for p in MIGRATED if not (ROOT / p).is_file()]
    assert not missing, f"MIGRATED lists files that do not exist: {missing}"


def test_french_translations_are_not_checked() -> None:
    """``page.fr.md`` is French by design; its English source ``page.md`` stays checked."""
    assert _is_french_translation("docs/gallery/01-repair-a-plan.fr.md")
    assert not _is_french_translation("docs/gallery/01-repair-a-plan.md")
    assert not any(_is_french_translation(p) for p in CHECKED)


def test_the_checker_detects_french() -> None:
    """Guard against a checker that silently accepts everything."""
    assert _french_markers("L" + "e solveur ren" + "d u" + "n plan valide.")
    assert _french_markers("surface minimale " + chr(0xE9) + "chou" + chr(0xE9) + "e")
    assert not _french_markers("The solver returns a valid plan.")
    assert not _french_markers("reads `docs/tutorials/getting-started.md` again")
    assert _french_markers("def test_l" + "e_certificat_affiche_l" + "a_version() -> None:")
    assert not _french_markers("import xml.etree.ElementTree as ET")
    assert not _french_markers(r"r^\top x \le \beta, \qquad")
    assert _french_markers("L" + r"e \le")  # the word before the command is seen
    assert not _french_markers("def pas(self):  # lang-ok: deprecated alias")
    assert _french_markers("def pas(self):  # lang-ok:")  # a reason is mandatory
    assert _french_markers("E" + "t l" + "e reste")
    assert not _french_markers("Fannjiang et al. (2022) use a 12 m " + chr(0xD7) + " 9 m grid.")
