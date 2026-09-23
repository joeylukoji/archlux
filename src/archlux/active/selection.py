"""Stratégies d'acquisition : actif vs aléatoire."""

from __future__ import annotations

from typing import Protocol

import numpy as np

from archlux.erreurs import InvariantViole

__all__ = ["Aleatoire", "StrategieAcquisition", "UncertaintyTimesDensity"]


class StrategieAcquisition(Protocol):
    """Choisir ``n`` indices parmi des candidats scorés."""

    def selectionner(
        self,
        incertitudes: np.ndarray,
        densites: np.ndarray,
        *,
        n: int,
        seed: int,
        exclus: np.ndarray | None = None,
    ) -> np.ndarray:
        """Rendre ``n`` indices distincts dans ``[0, N)``."""
        ...


def _valider(
    incertitudes: np.ndarray, densites: np.ndarray, *, n: int
) -> tuple[np.ndarray, np.ndarray]:
    """Verifier tailles et bornes des entrees de selection ; rendre les vecteurs aplatis."""
    inc = np.asarray(incertitudes, dtype=float).ravel()
    dens = np.asarray(densites, dtype=float).ravel()
    if inc.size != dens.size or inc.size == 0:
        raise InvariantViole(("incertitudes et densites de longueurs incompatibles",))
    if n < 1:
        raise InvariantViole(("n de sélection doit être ≥ 1",))
    if n > inc.size:
        raise InvariantViole((f"n={n} > nombre de candidats {inc.size}",))
    return inc, dens


def _masque_disponibles(n_candidats: int, exclus: np.ndarray | None) -> np.ndarray:
    """Masque booléen des indices libres ; refuse les ``exclus`` hors ``[0, N)``."""
    masque = np.ones(n_candidats, dtype=bool)
    if exclus is None:
        return masque
    exclus_i = np.asarray(exclus, dtype=int).ravel()
    if exclus_i.size == 0:
        return masque
    if np.any(exclus_i < 0) or np.any(exclus_i >= n_candidats):
        raise InvariantViole(("indices exclus hors bornes",))
    masque[exclus_i] = False
    return masque


class UncertaintyTimesDensity:
    """``priorité = incertitude × densité``. Produit, pas somme."""

    def selectionner(
        self,
        incertitudes: np.ndarray,
        densites: np.ndarray,
        *,
        n: int,
        seed: int,
        exclus: np.ndarray | None = None,
    ) -> np.ndarray:
        """Prendre les ``n`` plus hauts scores, en ignorant ``exclus``."""
        del seed  # déterministe une fois les scores fixés
        inc, dens = _valider(incertitudes, densites, n=n)
        scores = inc * dens
        disponibles = np.flatnonzero(_masque_disponibles(inc.size, exclus))
        if disponibles.size < n:
            raise InvariantViole((f"trop peu de candidats libres ({disponibles.size}) pour n={n}",))
        ordre = disponibles[np.argsort(-scores[disponibles], kind="stable")]
        return np.asarray(ordre[:n], dtype=int)


class Aleatoire:
    """Tirage uniforme parmi les candidats libres — baseline à budget égal."""

    def selectionner(
        self,
        incertitudes: np.ndarray,
        densites: np.ndarray,
        *,
        n: int,
        seed: int,
        exclus: np.ndarray | None = None,
    ) -> np.ndarray:
        """Échantillonner ``n`` indices avec la graine fournie."""
        inc, _dens = _valider(incertitudes, densites, n=n)
        disponibles = np.flatnonzero(_masque_disponibles(inc.size, exclus))
        if disponibles.size < n:
            raise InvariantViole((f"trop peu de candidats libres ({disponibles.size}) pour n={n}",))
        rng = np.random.default_rng(seed)
        choix = rng.choice(disponibles, size=n, replace=False)
        return np.asarray(np.sort(choix), dtype=int)
