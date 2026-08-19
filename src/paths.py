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


def find(name: str, near: str = "") -> str:
    """
    Chemin d'un fichier livré avec l'application.

    Args:
        name: nom ou chemin du fichier cherché
        near: dossier à consulter en premier — celui du fichier qui le
            désigne. Un template nommé dans une configuration est cherché à
            côté de cette configuration avant tout le reste.

    Le nom est retourné inchangé s'il reste introuvable : l'appelant produit
    alors son propre message d'erreur, qui cite le chemin demandé.
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

    Exposé pour que le message d'erreur puisse dire où le fichier a été
    cherché : un « template introuvable » sans cette liste n'aide personne.

      1. tel quel — relatif au dossier courant. Il n'est pas fiable : ouvert
         par glisser-déposer, l'exécutable hérite d'un dossier courant
         quelconque, sans rapport avec l'endroit où il est installé ;
      2. à côté du fichier qui le désigne (`near`) ;
      3. à côté de l'exécutable — c'est là que l'utilisateur édite le YAML et
         adapte le template ;
      4. à l'intérieur de l'exécutable — copie de secours, si le fichier livré
         a été supprimé ou déplacé.
    """
    found = [name]
    for directory in (near, app_dir(), bundled_dir()):
        if directory:
            candidate = os.path.join(directory, name)
            if candidate not in found:
                found.append(candidate)
    return found
