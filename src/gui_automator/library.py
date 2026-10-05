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

import re
from pathlib import Path

__all__ = ["CaptureLibrary"]

# Ce qu'un nom de fichier garde du nom technique. Les identifiants de Power BI
# n'en sortent pas, mais un rapport retouché à la main peut en porter d'autres.
_UNSAFE = re.compile(r"[^\w.-]+", re.UNICODE)


class CaptureLibrary:
    """Le dossier des captures : y écrire, et savoir ce qu'il contient déjà."""

    def __init__(self, directory: str | Path):
        self.directory = Path(directory)

    def path(self, page: str, shot: str) -> Path:
        """Chemin de la capture d'une prise, qu'elle existe ou non."""
        return self.directory / _safe(page) / f"{_safe(shot)}.png"

    def find(self, page: str, shot: str) -> Path | None:
        """Chemin de la capture si elle existe, None sinon."""
        path = self.path(page, shot)
        return path if path.is_file() else None

    def write(self, page: str, shot: str, image: bytes) -> Path:
        """Écrit une capture et retourne son chemin."""
        path = self.path(page, shot)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(image)
        return path

    def existing(self) -> list[Path]:
        """
        Captures déjà présentes, en chemins relatifs au dossier, triées.

        Sert au compte rendu — et à repérer les images d'un visuel disparu du
        rapport, que rien ne vient plus remplacer.
        """
        if not self.directory.is_dir():
            return []

        found = (p for p in self.directory.rglob("*") if p.suffix.lower() == ".png")
        return sorted(p.relative_to(self.directory) for p in found)


def _safe(name: str) -> str:
    """
    Nom de fichier tiré d'un identifiant du rapport.

    Déterministe : le document recalcule le même à partir du même rapport. Un
    identifiant vide donnerait un nom de fichier vide — il devient `sans-nom`,
    qui se voit dans le dossier.
    """
    cleaned = _UNSAFE.sub("_", (name or "").strip()).strip("._")
    return cleaned or "sans-nom"
