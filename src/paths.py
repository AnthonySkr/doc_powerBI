"""
Localisation des fichiers livrés avec l'application.

En développement, tout est dans le dépôt et les chemins relatifs suffisent.
Une fois le script distribué en exécutable, ce n'est plus vrai : l'utilisateur
lance le .exe depuis n'importe où, et la configuration comme le template sont
livrés à côté de l'exécutable, pas dans le dossier courant.
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
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def bundled_dir() -> str:
    """Dossier temporaire où l'exécutable déplie les fichiers qu'il embarque."""
    return getattr(sys, "_MEIPASS", "")


def find(name: str) -> str:
    """
    Chemin d'un fichier livré avec l'application.

    Cherché dans cet ordre :
      1. tel quel — chemin absolu, ou relatif au dossier courant ;
      2. à côté de l'exécutable — c'est là que l'utilisateur édite le YAML ;
      3. à l'intérieur de l'exécutable — copie de secours, si le fichier livré
         a été supprimé ou déplacé.

    Le nom est retourné inchangé s'il reste introuvable : l'appelant produit
    alors son propre message d'erreur, qui cite le chemin demandé.
    """
    if os.path.isfile(name) or os.path.isabs(name):
        return name

    for directory in (app_dir(), bundled_dir()):
        candidate = os.path.join(directory, name) if directory else ""
        if candidate and os.path.isfile(candidate):
            return candidate

    return name
