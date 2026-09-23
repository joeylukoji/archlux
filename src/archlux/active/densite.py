"""Densité empirique des plans visités par l'optimiseur."""

from __future__ import annotations

import numpy as np

from archlux.erreurs import InvariantViole

__all__ = ["densite_noyau"]

_EPS = 1e-12


def densite_noyau(
    candidats: np.ndarray, reference: np.ndarray, *, bande: float | None = None
) -> np.ndarray:
    """Densité gaussienne isotrope estimée sur les sorties de l'optimiseur.

    Parameters
    ----------
    candidats : numpy.ndarray
        Shape ``(n, d)`` — plans candidats (vectorisés).
    reference : numpy.ndarray
        Shape ``(m, d)`` — plans produits par l'optimiseur (domaine utile).
    bande : float or None, optional
        Largeur de noyau. Défaut : règle de Scott sur la référence.

    Returns
    -------
    numpy.ndarray
        Densités ``(n,)``, positives. Un candidat loin de toute sortie
        d'optimiseur a une densité ~0 → priorité active nulle.
    """
    cand = np.asarray(candidats, dtype=float)
    ref = np.asarray(reference, dtype=float)
    if cand.ndim != 2 or ref.ndim != 2:
        raise InvariantViole(("candidats et reference doivent être de rang 2",))
    if cand.shape[1] != ref.shape[1]:
        raise InvariantViole(("dimensions candidats / reference incompatibles",))
    if ref.shape[0] == 0 or cand.shape[0] == 0:
        raise InvariantViole(("reference et candidats non vides exigés",))
    d = cand.shape[1]
    if bande is None:
        # Scott : n^{-1/(d+4)} * ecart-type moyen.
        sigma = float(np.mean(np.std(ref, axis=0)) + _EPS)
        bande = sigma * (ref.shape[0] ** (-1.0 / (d + 4)))
        bande = max(bande, _EPS)
    if bande <= 0.0:
        raise InvariantViole(("bande doit être > 0",))
    # densite_i ∝ mean_j exp(-||c_i - r_j||² / (2 h²))
    # Pour éviter underflow : travailler en distance au plus proche + moyenne locale.
    diff = cand[:, None, :] - ref[None, :, :]
    dist2 = np.sum(diff * diff, axis=2)
    noyaux = np.exp(-0.5 * dist2 / (bande * bande))
    return np.asarray(np.maximum(np.mean(noyaux, axis=1), _EPS), dtype=float)
