"""
Retrouver le canevas dans l'image de la fenêtre.

Le problème
───────────
Recadrer une capture sur un visuel suppose de savoir **où le canevas est
rendu à l'écran**, au pixel près. Jusqu'ici c'était déclaré : on retranchait de
la fenêtre le ruban, les volets et la barre d'onglets (`capture.window`), et
l'on supposait le canevas ajusté puis centré dans ce qui reste. Trois choses
font mentir ce calcul, et aucune ne se voit dans le compte rendu :

    des marges réglées à l'œil, fausses de quelques dizaines de pixels
    un volet replié ou déplié depuis le dernier réglage
    un rapport qui n'est pas en « Ajuster à la page », ou dont on a zoomé

Le décalage qui en résulte est le même pour toutes les prises, et chacune
garde ses proportions : on obtient des images de la bonne forme, cadrées à
côté. C'est exactement ce que l'on observait.

Ce que fait ce module
─────────────────────
Il regarde l'image plutôt que de faire confiance aux marges. Power BI dessine
le canevas sur un fond uni qui l'entoure de toutes parts : le canevas est donc
le rectangle des pixels qui **ne sont pas** de la couleur du fond.

    fond        la couleur des quatre coins de l'image, si elles s'accordent
    canevas     l'étendue de ce qui n'est pas de cette couleur

Le résultat n'est retenu que s'il a les proportions que le rapport déclare
(1280 × 720, ou ce que la page dit). Sinon, on ne devine pas : on rend la main
aux marges déclarées, en le disant. Ce contrôle est ce qui distingue une
détection d'un pari — et il attrape du même coup le rapport qui n'est pas
ajusté à la page, puisque le canevas y déborde de sa zone.

Tout ici est du calcul sur des pixels, sans écran ni Power BI : une image de
test se fabrique en quelques octets, et c'est ce que font les tests.
"""

from dataclasses import dataclass

from src.gui_automator.geometry import Rect

__all__ = ["Image", "detect", "outline"]

# Écart maximal, par canal, entre deux couleurs tenues pour la même. Le fond
# de l'application (#F1F1F1) et une page blanche ne diffèrent que de 14 : le
# seuil doit rester bien en deçà, tout en absorbant le lissage des bords.
CLOSE = 6

# Écart toléré entre les proportions du canevas détecté et celles que le
# rapport déclare. Deux pour cent, c'est une dizaine de pixels sur 900 : assez
# pour absorber une bordure, trop peu pour laisser passer un cadrage faux.
RATIO_TOLERANCE = 0.02

# Le canevas occupe l'essentiel de la zone qu'on lui laisse. Un rectangle plus
# petit que cela est autre chose — une boîte de dialogue, une infobulle.
MIN_SHARE = 0.3

# Nombre de coins qui doivent s'accorder pour tenir leur couleur pour celle du
# fond : trois sur quatre, un volet mal retranché pouvant en manger un.
AGREEING_CORNERS = 3

# Pas du balayage grossier. Les bords sont ensuite repris pixel par pixel :
# ce pas ne décide que du temps passé, jamais de la précision.
STEP = 4


@dataclass(frozen=True)
class Image:
    """
    Image brute : trois octets par pixel, lignes du haut vers le bas.

    C'est la forme que `mss` retourne (`ScreenShot.rgb`), et celle que `png`
    écrit — aucune conversion entre les deux.
    """

    width: int
    height: int
    rgb: bytes

    def at(self, x: int, y: int) -> tuple[int, int, int]:
        """Couleur d'un pixel. Hors de l'image, du noir."""
        if not (0 <= x < self.width and 0 <= y < self.height):
            return (0, 0, 0)
        start = (y * self.width + x) * 3
        return (self.rgb[start], self.rgb[start + 1], self.rgb[start + 2])

    @property
    def is_empty(self) -> bool:
        return self.width <= 0 or self.height <= 0 or len(self.rgb) < self.width * self.height * 3


def detect(image: Image, ratio: float, tolerance: float = RATIO_TOLERANCE) -> Rect | None:
    """
    Rectangle du canevas dans l'image, ou `None` s'il ne s'y reconnaît pas.

    `ratio` est le rapport largeur/hauteur que le rapport déclare pour la page.
    Les coordonnées retournées sont celles de l'image : c'est à l'appelant de
    les ramener à l'écran, en y ajoutant l'origine de ce qu'il a photographié.
    """
    if image.is_empty or ratio <= 0:
        return None

    background = _background(image)
    if background is None:
        return None

    found = _content_box(image, background)
    if found is None:
        return None

    found = _refine(image, background, found)
    return found if _plausible(found, image, ratio, tolerance) else None


def outline(image: Image, areas: list[Rect], color: tuple[int, int, int], width: int = 2) -> bytes:
    """
    Pixels de l'image, rectangles tracés par-dessus.

    Sert au calibrage : voir sur la capture de la fenêtre où le script croit
    que sont le canevas et chaque visuel vaut tous les réglages à l'aveugle.
    """
    pixels = bytearray(image.rgb)
    for area in areas:
        _draw(pixels, image, area, bytes(color), max(width, 1))
    return bytes(pixels)


# ─────────────────────────────────────────────────────────────
#  Trouver
# ─────────────────────────────────────────────────────────────


def _background(image: Image) -> tuple[int, int, int] | None:
    """
    Couleur du fond, lue aux quatre coins de l'image.

    Trois coins concordants suffisent : un volet mal retranché peut en manger
    un. Les quatre en désaccord, en revanche, disent que l'image ne montre pas
    ce qu'on croit — et l'on préfère alors ne rien détecter du tout.
    """
    margin = 2
    corners = [
        image.at(margin, margin),
        image.at(image.width - 1 - margin, margin),
        image.at(margin, image.height - 1 - margin),
        image.at(image.width - 1 - margin, image.height - 1 - margin),
    ]
    for candidate in corners:
        if sum(1 for corner in corners if _close(corner, candidate)) >= AGREEING_CORNERS:
            return candidate
    return None


def _content_box(image: Image, background: tuple[int, int, int]) -> Rect | None:
    """Étendue approchée de ce qui n'est pas du fond, par balayage grossier."""
    left, top = image.width, image.height
    right = bottom = -1

    for y in range(0, image.height, STEP):
        for x in range(0, image.width, STEP):
            if _close(image.at(x, y), background):
                continue
            left, right = min(left, x), max(right, x)
            top, bottom = min(top, y), max(bottom, y)

    if right < 0:
        return None
    return Rect(left, top, right - left + 1, bottom - top + 1)


def _refine(image: Image, background: tuple[int, int, int], found: Rect) -> Rect:
    """
    Bords exacts, repris pixel par pixel depuis l'étendue approchée.

    Le balayage grossier place chaque bord à quelques pixels près ; on repart
    de l'intérieur du rectangle et l'on avance vers l'extérieur tant que ce
    n'est pas du fond. La ligne et la colonne médianes servent de sonde : le
    canevas les traverse forcément.
    """
    row = _Line(image, int(found.top + found.height / 2), horizontal=True)
    column = _Line(image, int(found.left + found.width / 2), horizontal=False)

    left = _edge(row, background, int(found.left), step=-1)
    right = _edge(row, background, int(found.right) - 1, step=1)
    top = _edge(column, background, int(found.top), step=-1)
    bottom = _edge(column, background, int(found.bottom) - 1, step=1)
    return Rect(left, top, right - left + 1, bottom - top + 1)


@dataclass(frozen=True)
class _Line:
    """Une ligne ou une colonne de l'image, parcourue d'un bout à l'autre."""

    image: Image
    fixed: int
    horizontal: bool

    @property
    def length(self) -> int:
        return self.image.width if self.horizontal else self.image.height

    def at(self, position: int) -> tuple[int, int, int]:
        if self.horizontal:
            return self.image.at(position, self.fixed)
        return self.image.at(self.fixed, position)


def _edge(line: _Line, background: tuple[int, int, int], start: int, step: int) -> int:
    """Dernière coordonnée qui n'est pas du fond, en partant de `start`."""
    last = position = start
    while 0 <= position < line.length and not _close(line.at(position), background):
        last = position
        position += step
    return last


def _plausible(found: Rect, image: Image, ratio: float, tolerance: float) -> bool:
    """
    Le rectangle trouvé peut-il être le canevas ?

    Il doit occuper l'essentiel de l'image, et porter les proportions que le
    rapport déclare. C'est ce dernier point qui fait foi : un canevas qui n'est
    pas ajusté à la page, ou zoomé, ne les a pas.
    """
    if found.is_empty or found.height <= 0:
        return False
    if found.width < image.width * MIN_SHARE or found.height < image.height * MIN_SHARE:
        return False
    return abs(found.width / found.height - ratio) <= ratio * tolerance


def _close(color: tuple[int, int, int], other: tuple[int, int, int]) -> bool:
    """Deux couleurs indiscernables, au lissage des bords près."""
    return all(abs(a - b) <= CLOSE for a, b in zip(color, other, strict=False))


# ─────────────────────────────────────────────────────────────
#  Tracer
# ─────────────────────────────────────────────────────────────


def _draw(pixels: bytearray, image: Image, area: Rect, color: bytes, width: int) -> None:
    """Contour d'un rectangle, tracé dans les pixels de l'image."""
    area = area.rounded()
    left, top = int(area.left), int(area.top)
    right, bottom = int(area.right) - 1, int(area.bottom) - 1
    if right < left or bottom < top:
        return

    for offset in range(width):
        for x in range(left, right + 1):
            _set(pixels, image, x, top + offset, color)
            _set(pixels, image, x, bottom - offset, color)
        for y in range(top, bottom + 1):
            _set(pixels, image, left + offset, y, color)
            _set(pixels, image, right - offset, y, color)


def _set(pixels: bytearray, image: Image, x: int, y: int, color: bytes) -> None:
    if 0 <= x < image.width and 0 <= y < image.height:
        start = (y * image.width + x) * 3
        pixels[start : start + 3] = color
