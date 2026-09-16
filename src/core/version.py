"""
La version du projet, relevée sur le dernier tag `v…` du dépôt.

Le tag fait foi : `git tag v0.8` suffit, il n'y a plus de constante à corriger
ensuite. C'est le dernier tag **du dépôt** qui est retenu, et non le dernier tag
atteignable depuis la branche courante : les versions sont posées sur `main`,
qu'une branche de travail ne voit pas.

Un exécutable, lui, n'emporte pas le dépôt avec lui. La construction écrit donc
la version dans un fichier `VERSION` que PyInstaller embarque, et que le
programme lit à défaut de git (voir `powerbi-doc.spec`).
"""

import subprocess
from pathlib import Path

from src.core import paths

__all__ = ["UNKNOWN", "VERSION_FILE", "current", "write_stamp"]

# Fichier écrit à la construction, embarqué dans l'exécutable.
VERSION_FILE = "VERSION"

# Faute de tag comme de fichier : une version valide, et visiblement pas vraie.
UNKNOWN = "0.0"

# Les tags de version, et eux seuls : `v0.6`, `v0.3.1`.
_TAG_PATTERN = "v[0-9]*"

# Secondes laissées à git. Au-delà, la version ne vaut pas d'attendre.
_TIMEOUT = 5


def current() -> str:
    """Version du projet : le dernier tag, ou celle relevée à la construction."""
    if paths.is_frozen():
        # Le dépôt n'est pas là, et un `git` lancé depuis le dossier de l'exe
        # répondrait sur le dépôt de quelqu'un d'autre.
        return _from_stamp() or UNKNOWN
    return _from_git() or _from_stamp() or UNKNOWN


def write_stamp(directory: str | Path | None = None) -> Path:
    """Écrit la version dans `VERSION`, pour que l'exécutable la connaisse."""
    path = Path(directory or paths.app_dir()) / VERSION_FILE
    path.write_text(f"{current()}\n", encoding="utf-8")
    return path


def _from_git() -> str:
    """Dernier tag `v…` du dépôt, ou chaîne vide hors dépôt."""
    try:
        # Commande fixe, sans shell, lancée dans le dépôt : rien de ce qu'elle
        # reçoit ne vient de l'extérieur.
        result = subprocess.run(  # noqa: S603
            ["git", "tag", "--list", _TAG_PATTERN, "--sort=-version:refname"],  # noqa: S607
            cwd=paths.app_dir(),
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
            check=False,
        )
    except OSError, subprocess.SubprocessError:
        return ""  # git absent, ou hors d'état de répondre

    tags = result.stdout.split()
    return tags[0].removeprefix("v") if result.returncode == 0 and tags else ""


def _from_stamp() -> str:
    """Version relevée à la construction, ou chaîne vide faute de fichier."""
    try:
        return paths.find(VERSION_FILE).read_text(encoding="utf-8").strip()
    except OSError:
        return ""
