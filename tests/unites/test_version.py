"""A single source of truth for the version (PLAN.md, task 0.3)."""

from __future__ import annotations

import archlux
from archlux._version import __version__


def test_root_exposes_the_single_version() -> None:
    assert archlux.__version__ == __version__


def test_certificate_prints_the_source_version() -> None:
    from archlux.certify.rapport import _version

    assert _version() == __version__


def test_ifc_export_stamps_the_source_version() -> None:
    from archlux.export.ifc import _version_paquet

    assert _version_paquet() == __version__
