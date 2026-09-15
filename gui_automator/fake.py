"""
Captures factices, pour éprouver la chaîne sans Power BI.

Le vrai enregistreur exige Windows, Power BI Desktop installé et le rapport
ouvert. Celui-ci n'exige rien : il produit une image unie, aux dimensions
exactes du cadrage calculé, et la range où la vraie irait.

Ce n'est pas qu'un objet de test. C'est aussi ce qui permet de répondre à une
question sans quitter sa machine : **est-ce que le cadrage est bon ?** Un
dossier de captures factices se parcourt à l'œil — une image de 40 × 30 pixels
là où on attendait un graphique, c'est un visuel dont le rapport ne déclare pas
la taille, et cela se voit avant d'avoir lancé Power BI une seule fois.

Chaque prise reçoit une couleur tirée de son nom : deux captures voisines ne se
ressemblent pas, et la même prise garde la sienne d'une exécution à l'autre.
"""

import struct
import zlib

from gui_automator.geometry import Rect
from gui_automator.plan import PagePlan

__all__ = ["FakeRecorder", "solid_png"]

# Zone d'écran que l'enregistreur factice prétend occuper : un 1920 × 1080
# ordinaire, dont le rapport occupera le centre.
DEFAULT_VIEWPORT = Rect(0, 0, 1920, 1080)

# Couleurs franches et distinctes, pour qu'un dossier de captures se lise d'un
# coup d'œil.
_PALETTE = (
    (0x1F, 0x77, 0xB4),
    (0xFF, 0x7F, 0x0E),
    (0x2C, 0xA0, 0x2C),
    (0xD6, 0x27, 0x28),
    (0x94, 0x67, 0xBD),
    (0x8C, 0x56, 0x4B),
)


class FakeRecorder:
    """Enregistreur qui ne capture rien : il dessine des rectangles unis."""

    def __init__(self, viewport: Rect = DEFAULT_VIEWPORT):
        self.viewport = viewport
        # Les pages montrées et les régions prises, dans l'ordre : de quoi
        # vérifier le déroulé d'une séance sans regarder les images.
        self.shown: list[str] = []
        self.grabbed: list[Rect] = []

    def start(self) -> None:
        return

    def show_page(self, page: PagePlan) -> Rect:
        self.shown.append(page.name)
        return self.viewport

    def grab(self, area: Rect) -> bytes:
        self.grabbed.append(area)
        return solid_png(int(area.width), int(area.height), _color(area))

    def stop(self) -> None:
        return


def solid_png(width: int, height: int, color: tuple[int, int, int]) -> bytes:
    """
    Image PNG unie, écrite à la main.

    Le projet ne dépend d'aucune bibliothèque d'images, et n'a pas à en dépendre
    pour produire un rectangle de couleur : un PNG est un en-tête, des lignes
    compressées et une fin de fichier.
    """
    width, height = max(width, 1), max(height, 1)
    row = b"\x00" + bytes(color) * width
    return b"".join(
        [
            b"\x89PNG\r\n\x1a\n",
            _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)),
            _chunk(b"IDAT", zlib.compress(row * height, 6)),
            _chunk(b"IEND", b""),
        ]
    )


def _chunk(kind: bytes, payload: bytes) -> bytes:
    """Un bloc PNG : longueur, type, contenu, et le CRC des deux derniers."""
    body = kind + payload
    return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body))


def _color(area: Rect) -> tuple[int, int, int]:
    """Couleur stable, tirée du cadrage : la même prise reprend la sienne."""
    seed = int(area.left) * 31 + int(area.top) * 17 + int(area.width)
    return _PALETTE[seed % len(_PALETTE)]
