"""Une seule source de vérité pour la version (PLAN.md, tâche 0.3)."""

from __future__ import annotations

import archlux
from archlux._version import __version__


def test_la_racine_expose_la_version_unique() -> None:
    assert archlux.__version__ == __version__


def test_le_certificat_affiche_la_version_du_code() -> None:
    from archlux.certify.rapport import _version

    assert _version() == __version__


def test_l_export_ifc_estampille_la_version_du_code() -> None:
    from archlux.export.ifc import _version_paquet

    assert _version_paquet() == __version__
