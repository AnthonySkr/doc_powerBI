"""
Où vivent les captures, et sous quel nom.

Les images ne sont pas rangées dans le document : elles vivent à côté du
`.pbip`, dans un dossier que l'utilisateur peut ouvrir, trier, retoucher ou
compléter à la main. Le document, lui, ira les y chercher.

    captures/
        page_ventes/
            v_evolution.png
            g_indicateurs.png

C'est tout le contrat entre les deux moitiés du projet : un chemin de fichier,
calculé des deux côtés à partir des mêmes identifiants techniques. Ni la
capture ne connaît le document, ni le document la capture — et remplacer une
image par une meilleure, prise autrement, revient à écrire dans ce dossier.

Les noms viennent du rapport, jamais des titres : renommer un visuel dans
Power BI ne doit pas rendre sa capture introuvable.
"""

import os
import re

__all__ = ["DEFAULT_DIRECTORY", "CaptureLibrary"]

DEFAULT_DIRECTORY = "captures"

# Ce qu'un nom de fichier garde du nom technique. Les identifiants de Power BI
# n'en sortent pas, mais un rapport retouché à la main peut en porter d'autres.
_UNSAFE = re.compile(r"[^\w.-]+", re.UNICODE)


class CaptureLibrary:
    """Le dossier des captures : y écrire, et savoir ce qu'il contient déjà."""

    def __init__(self, directory: str):
        self.directory = directory

    def path(self, page: str, shot: str) -> str:
        """Chemin de la capture d'une prise, qu'elle existe ou non."""
        return os.path.join(self.directory, _safe(page), f"{_safe(shot)}.png")

    def find(self, page: str, shot: str) -> str:
        """Chemin de la capture si elle existe, chaîne vide sinon."""
        path = self.path(page, shot)
        return path if os.path.isfile(path) else ""

    def write(self, page: str, shot: str, image: bytes) -> str:
        """Écrit une capture et retourne son chemin."""
        path = self.path(page, shot)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(image)
        return path

    def existing(self) -> list[str]:
        """
        Captures déjà présentes, en chemins relatifs au dossier, triées.

        Sert au compte rendu — et à repérer les images d'un visuel disparu du
        rapport, que rien ne vient plus remplacer.
        """
        if not os.path.isdir(self.directory):
            return []

        found: list[str] = []
        for root, _, files in os.walk(self.directory):
            relative = os.path.relpath(root, self.directory)
            found += [
                os.path.normpath(os.path.join(relative, name))
                for name in files
                if name.lower().endswith(".png")
            ]
        return sorted(found)


def _safe(name: str) -> str:
    """
    Nom de fichier tiré d'un identifiant du rapport.

    Déterministe : le document recalcule le même à partir du même rapport. Un
    identifiant vide donnerait un nom de fichier vide — il devient `sans-nom`,
    qui se voit dans le dossier.
    """
    cleaned = _UNSAFE.sub("_", (name or "").strip()).strip("._")
    return cleaned or "sans-nom"
