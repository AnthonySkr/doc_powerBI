"""
Localisation des fichiers livrés avec l'application.

Le plan et le template se cherchent à trois endroits (voir `candidates`). Les
fichiers posés à côté de l'exécutable font foi : c'est ainsi qu'on adapte le
plan sans reconstruire.
"""

import sys
from pathlib import Path

__all__ = ["app_dir", "bundled_dir", "candidates", "find", "is_frozen"]


def is_frozen() -> bool:
    """Vrai lorsque le programme tourne depuis un exécutable PyInstaller."""
    return bool(getattr(sys, "frozen", False))


def app_dir() -> Path:
    """
    Dossier de référence de l'application.

    Exécutable : le dossier du .exe, à côté duquel sont livrés le plan et le
    template — ce sont eux que l'utilisateur adapte. Sinon : la racine du dépôt,
    deux dossiers au-dessus de `src/core/`.
    """
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def bundled_dir() -> Path | None:
    """Dossier temporaire où l'exécutable déplie les fichiers qu'il embarque."""
    unpacked = getattr(sys, "_MEIPASS", "")
    return Path(unpacked) if unpacked else None


def find(name: str | Path, near: str | Path | None = None) -> Path:
    """Chemin d'un fichier livré avec l'application, le premier qui existe."""
    name = Path(name)
    if name.is_absolute():
        return name

    for candidate in candidates(name, near):
        if candidate.is_file():
            return candidate

    return name


def candidates(name: str | Path, near: str | Path | None = None) -> list[Path]:
    """Emplacements consultés par `find`, dans l'ordre."""
    name = Path(name)
    found = [name]
    for directory in (near, app_dir(), bundled_dir()):
        if not directory:
            continue
        candidate = Path(directory) / name
        if candidate not in found:
            found.append(candidate)
    return found
