"""
Localisation des fichiers livrés avec l'application.
"""

import os
import sys


def is_frozen() -> bool:
    """Vrai lorsque le programme tourne depuis un exécutable PyInstaller."""
    return bool(getattr(sys, "frozen", False))


def app_dir() -> str:
    """
    Dossier de référence de l'application.

    Exécutable : le dossier du .exe, à côté duquel sont livrés le fichier de
    configuration et le template — ce sont eux que l'utilisateur adapte.
    Sinon : la racine du dépôt.
    """
    if is_frozen():
        return os.path.dirname(os.path.abspath(sys.executable))
    # Ce fichier vit dans `src/shared/` : la racine est deux dossiers plus haut.
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def bundled_dir() -> str:
    """Dossier temporaire où l'exécutable déplie les fichiers qu'il embarque."""
    return getattr(sys, "_MEIPASS", "")


def find(name: str, near: str = "") -> str:
    """
    Chemin d'un fichier livré avec l'application.
    """
    if os.path.isabs(name):
        return name

    for candidate in candidates(name, near):
        if os.path.isfile(candidate):
            return candidate

    return name


def candidates(name: str, near: str = "") -> list[str]:
    """
    Emplacements consultés par `find`, dans l'ordre.
    """
    found = [name]
    for directory in (near, app_dir(), bundled_dir()):
        if directory:
            candidate = os.path.join(directory, name)
            if candidate not in found:
                found.append(candidate)
    return found
