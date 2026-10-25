"""Reproducibility record of a run: code version, environment, parameters, data hashes.

:func:`archlux.bench.manifest.emit` records the package version and the numerical
dependencies. A published table needs more: the exact commit (and whether the tree was
dirty), the platform, the seeds, the parameters of every algorithm, and a fingerprint
of every input and output file, so that a reader can tell whether the files they hold
are the ones the table was computed from. Corpora that cannot be redistributed are
recorded by hash only, and flagged as such.
"""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path

from archlux.bench.manifest import emit
from archlux.io.json_io import manifest_to_dict

__all__ = ["file_sha256", "git_state", "record", "write_record"]


def file_sha256(path: Path) -> str:
    """SHA-256 of a file, streamed.

    Parameters
    ----------
    path : Path
        File to hash.

    Returns
    -------
    str
        Hex digest.
    """
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def git_state(root: Path, *, ignore: Sequence[Path] = ()) -> dict[str, object]:
    """Commit and cleanliness of the working tree at ``root``.

    Parameters
    ----------
    root : Path
        Any directory inside the repository.
    ignore : Sequence[Path], optional
        Files whose modification does not count as dirty: the outputs the run itself just
        rewrote. Without this, regenerating a tracked result always reads as a dirty tree,
        and the flag no longer says whether the *code* that ran was committed.

    Returns
    -------
    dict
        ``commit`` (``None`` outside a repository or without ``git``) and ``dirty``
        (uncommitted changes to tracked files other than ``ignore``: the commit alone
        does not identify the code that ran).
    """
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True
        ).stdout.strip()
        top = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return {"commit": None, "dirty": None}
    skipped = {p.resolve() for p in ignore}
    changed = [line[3:] for line in status.splitlines() if line.strip()]
    dirty = [p for p in changed if (Path(top) / p).resolve() not in skipped]
    return {"commit": commit, "dirty": bool(dirty)}


def record(
    *,
    seed: int,
    command: str,
    parameters: Mapping[str, object],
    inputs: Sequence[Path] = (),
    outputs: Sequence[Path] = (),
    restricted: Sequence[Path] = (),
    root: Path = Path(),
) -> dict[str, object]:
    """Build the reproducibility record of one run.

    Parameters
    ----------
    seed : int
        Root seed. Mandatory.
    command : str
        Command line that reproduces the run.
    parameters : Mapping[str, object]
        Every algorithm parameter of the run (JSON-serializable).
    inputs : Sequence[Path], optional
        Input files to fingerprint.
    outputs : Sequence[Path], optional
        Output files to fingerprint.
    restricted : Sequence[Path], optional
        Inputs that may not be redistributed: hashed, flagged ``redistributable: false``.
    root : Path, optional
        Directory inside the repository, for :func:`git_state` (which ignores
        ``outputs``: the run just rewrote them).

    Returns
    -------
    dict
        ``git``, ``manifest`` (version, dependencies), ``platform``, ``seed``,
        ``command``, ``parameters``, ``files``.
    """
    files = [
        {
            "path": str(p),
            "sha256": file_sha256(p),
            "role": role,
            "redistributable": p not in restricted,
        }
        for role, paths in (("input", [*inputs, *restricted]), ("output", outputs))
        for p in paths
    ]
    return {
        "git": git_state(root, ignore=outputs),
        "manifest": manifest_to_dict(emit(seed=seed)),
        "platform": {"system": platform.system(), "machine": platform.machine()},
        "seed": seed,
        "command": command,
        "parameters": dict(parameters),
        "files": files,
    }


def write_record(path: Path, content: Mapping[str, object]) -> None:
    """Write a record as indented JSON.

    Parameters
    ----------
    path : Path
        Output file.
    content : Mapping[str, object]
        Output of :func:`record`.
    """
    path.write_text(json.dumps(content, indent=1, default=str) + "\n", encoding="utf-8")
