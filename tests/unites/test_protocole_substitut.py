"""Toute implémentation de ``Substitut`` respecte réellement le protocole.

Un `Protocol` est structurel : rien ne signale qu'une implémentation a dérivé, jusqu'au
jour où ``solve`` reçoit un objet auquel il manque ``incertitude``. Ce test transforme
cette dérive silencieuse en échec de CI.

Il vérifie aussi que les **signatures** correspondent, et pas seulement les noms : une
méthode ``gradient(self, x)`` qui aurait perdu son paramètre ``orientation`` passerait
un ``isinstance`` sans broncher.
"""

from __future__ import annotations

import inspect
from typing import Generic, Protocol

import pytest

from archlux.light.analytique import SubstitutAnalytique
from archlux.light.appris import SubstitutAppris
from archlux.light.protocole import Substitut

IMPLEMENTATIONS = [SubstitutAnalytique, SubstitutAppris]

# `baies` est arrive avec l'extension du protocole : le vecteur de decision ne porte
# que (x, y, w, h) par piece, donc aucune information de fenestration. Mesure sur 369
# appartements suisses, cible = irradiance simulee, decoupage par site : analytique
# R2 = -0,000, perceptron R2 = -0,667 — au niveau ou sous la simple moyenne. C'est un
# defaut d'entree, pas de capacite. Le parametre est **nomme et optionnel** : une
# implementation qui l'ignore reste conforme.
SIGNATURES_ATTENDUES = {
    "evaluer": ("self", "x", "orientation", "baies"),
    "gradient": ("self", "x", "orientation", "baies"),
    "incertitude": ("self", "x", "orientation", "baies"),
}


@pytest.mark.parametrize("classe", IMPLEMENTATIONS, ids=lambda c: c.__name__)
def test_implemente_le_protocole(classe: type) -> None:
    """Les quatre membres du protocole sont présents."""
    for membre in ("indicateur", *SIGNATURES_ATTENDUES):
        assert hasattr(classe, membre), f"{classe.__name__} n'a pas {membre}"


@pytest.mark.parametrize("classe", IMPLEMENTATIONS, ids=lambda c: c.__name__)
@pytest.mark.parametrize("methode", sorted(SIGNATURES_ATTENDUES))
def test_les_signatures_correspondent(classe: type, methode: str) -> None:
    """Les noms de paramètres sont identiques à ceux du protocole."""
    obtenue = tuple(inspect.signature(getattr(classe, methode)).parameters)
    assert obtenue == SIGNATURES_ATTENDUES[methode]


def _protocol_members(protocol: type) -> set[str]:
    """Members declared by ``protocol`` and its parent protocols.

    ``__protocol_attrs__`` only exists from Python 3.12 (``typing.get_protocol_members``
    from 3.13), and the CI also runs 3.11: read the class bodies instead.
    """
    members: set[str] = set()
    for base in protocol.__mro__:
        if base in (object, Protocol, Generic):
            continue
        members |= set(vars(base)) | set(getattr(base, "__annotations__", {}))
    return members


def test_le_protocole_a_exactement_quatre_membres() -> None:
    """Trois méthodes et un attribut. Élargir le protocole élargit la surface apprise.

    Chaque membre ajouté ici est une chose de plus que ``solve`` doit savoir du modèle
    de lumière — donc un pas vers le couplage que l'architecture évite.
    """
    membres = {m for m in _protocol_members(Substitut) if not m.startswith("_")}
    assert membres == {"indicateur", "evaluer", "gradient", "incertitude"}
