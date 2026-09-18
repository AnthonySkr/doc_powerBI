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
Il regarde l'image plutôt que de faire confiance aux marges, et par deux
chemins — parce qu'aucun des deux ne vaut partout :

    le pourtour   Power BI pose le canevas sur un fond uni qui l'entoure de
                  toutes parts. Le canevas est alors le rectangle des pixels
                  qui **ne sont pas** de la couleur de ce fond.

    la bordure    un rapport dont l'habillage est de la couleur de ses pages
                  n'a plus de pourtour : page et fond se confondent, et le
                  premier chemin ne voit plus rien. Reste le trait pointillé
                  dont Power BI Desktop entoure le canevas, qui se cherche
                  comme un rectangle de traits dans l'image.

Le résultat n'est retenu, d'un chemin comme de l'autre, que s'il a les
proportions que le rapport déclare (1280 × 720, ou ce que la page dit). Sinon,
on ne devine pas : on rend la main aux marges déclarées, en le disant. Ce
contrôle est ce qui distingue une détection d'un pari — et il attrape du même
coup le rapport qui n'est pas ajusté à la page, puisque le canevas y déborde
de sa zone.

Tout ici est du calcul sur des pixels, sans écran ni Power BI : une image de
test se fabrique en quelques octets, et c'est ce que font les tests.
"""

from array import array
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

# ── Ce qui fait un trait de bordure ───────────────────────────
# Les seuils du second chemin. Ils portent tous sur la somme des trois canaux
# d'un pixel, et se lisent dans l'ordre où le module les emploie.

# Écart à partir duquel un pixel tranche sur son voisinage. Le trait du
# canevas (#605E5C) s'écarte de plus de 450 d'une page blanche : le seuil est
# bas exprès, pour attraper aussi les habillages sombres, où c'est le trait
# qui est le plus clair des deux.
LINE_CONTRAST = 120

# Distance à laquelle ce voisinage est lu, de part et d'autre du trait. Plus
# grande que l'épaisseur du trait — deux pixels —, assez petite pour que ce
# qu'on y lise soit encore la page, et non ce qui est posé dessus.
LINE_MARGIN = 4

# Part de sa propre longueur qu'un trait doit marquer pour compter comme
# bordure. La bordure est en pointillé : elle en marque la moitié. Une ligne
# de texte, elle, n'en marque qu'un dixième.
LINE_DENSITY = 0.2

# Écart maximal entre deux marques d'un même trait, en pixels. Au-delà, ce
# sont deux traits : c'est ce qui évite d'étirer une bordure jusqu'à un mot
# posé plus loin sur la même ligne.
LINE_GAP = 24

# Part d'un côté du rectangle que le trait qui le borde doit longer. Deux
# cinquièmes : un visuel posé contre le bord du canevas recouvre la bordure
# sur près de la moitié de sa longueur, et il en reste encore assez pour la
# suivre — c'est ce qu'on observe sur un rapport dont un tableau touche le
# bas de la page.
LINE_COVERAGE = 0.4


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

    Le pourtour d'abord — il est le moins cher et le plus sûr là où il
    s'applique —, puis la bordure de page, pour les rapports dont l'habillage
    se confond avec les pages.
    """
    if image.is_empty or ratio <= 0:
        return None

    surrounded = _surrounded_box(image)
    if surrounded is not None and _plausible(surrounded, image, ratio, tolerance):
        return surrounded
    return _bordered_box(image, ratio, tolerance)


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
#  Trouver — par le pourtour
# ─────────────────────────────────────────────────────────────


def _surrounded_box(image: Image) -> Rect | None:
    """Le canevas comme étendue de ce qui n'est pas de la couleur du fond."""
    background = _background(image)
    if background is None:
        return None

    found = _content_box(image, background)
    if found is None:
        return None
    return _refine(image, background, found)


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


# ─────────────────────────────────────────────────────────────
#  Trouver — par la bordure de page
# ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class _Band:
    """
    Un trait de l'image, repéré comme bordure possible.

    `first` et `last` sont ses coordonnées perpendiculaires : un trait a deux
    pixels d'épaisseur, parfois plus s'il est lissé. `start` et `end` sont son
    étendue — d'où il part et où il s'arrête, le long de lui-même.
    """

    first: int
    last: int
    start: int
    end: int

    def joined(self, other: _Band) -> _Band:
        """Les deux traits n'en font qu'un : même bordure, lissée sur deux rangs."""
        return _Band(
            min(self.first, other.first),
            max(self.last, other.last),
            min(self.start, other.start),
            max(self.end, other.end),
        )

    def follows(self, start: float, end: float) -> bool:
        """
        Le trait longe-t-il ce côté du rectangle, de bout en bout ou presque ?

        C'est ce qui sépare un côté de canevas d'un trait qui passait par là :
        la bordure du haut longe toute la largeur du canevas, la ligne d'un
        tableau ne longe que la sienne.
        """
        overlap = min(self.end, end) - max(self.start, start) + 1
        return overlap >= (end - start + 1) * LINE_COVERAGE


def _bordered_box(image: Image, ratio: float, tolerance: float) -> Rect | None:
    """
    Le canevas comme rectangle de traits, à défaut de pourtour.

    Quatre traits — deux horizontaux, deux verticaux — dont chacun longe le
    côté qu'il borde : c'est cela, un rectangle, et c'est ce que l'on cherche.
    Un trait isolé ne dit rien ; quatre traits qui se recoupent ne se
    rencontrent pas par hasard.

    Entre plusieurs rectangles plausibles, le plus grand : le canevas porte
    les autres, il ne tient dans aucun.
    """
    levels = _Levels(image)
    rows = _bands(levels, horizontal=True)
    columns = _bands(levels, horizontal=False)
    boxes = [box for box in _rectangles(rows, columns) if _plausible(box, image, ratio, tolerance)]
    return max(boxes, key=lambda box: box.width * box.height, default=None)


def _rectangles(rows: list[_Band], columns: list[_Band]) -> list[Rect]:
    """
    Rectangles dont les quatre côtés sont des traits qui se recoupent.

    Toutes les combinaisons sont éprouvées : une fenêtre porte une poignée de
    traits par sens, et les compter toutes coûte moins que de les trier.
    """
    boxes = []
    for top, bottom in _pairs(rows):
        for left, right in _pairs(columns):
            box = Rect(
                left.first,
                top.first,
                right.last - left.first + 1,
                bottom.last - top.first + 1,
            )
            if _bordered(box, top, bottom, left, right):
                boxes.append(box)
    return boxes


def _bordered(box: Rect, top: _Band, bottom: _Band, left: _Band, right: _Band) -> bool:
    """Les quatre traits longent-ils bien les quatre côtés du rectangle ?"""
    return (
        top.follows(box.left, box.right)
        and bottom.follows(box.left, box.right)
        and left.follows(box.top, box.bottom)
        and right.follows(box.top, box.bottom)
    )


def _pairs(bands: list[_Band]) -> list[tuple[_Band, _Band]]:
    """Les traits deux à deux, dans l'ordre où ils traversent l'image."""
    return [(first, second) for index, first in enumerate(bands) for second in bands[index + 1 :]]


class _Levels:
    """
    Niveau de chaque pixel de l'image : la somme de ses trois canaux.

    Le balayage des traits lit chaque pixel et ses deux voisins, dans les deux
    sens — une dizaine de millions de lectures pour une fenêtre ordinaire. Les
    niveaux sont donc calculés une fois, dans un tableau d'entiers courts (deux
    octets par pixel, la moitié de l'image), dont une ligne comme une colonne
    s'extraient d'une seule opération.

    Une somme plutôt qu'une luminance pondérée : un trait gris tranche autant
    sur l'une que sur l'autre, et celle-ci est de l'arithmétique entière.
    """

    def __init__(self, image: Image):
        self.width = image.width
        self.height = image.height
        self.values = array("h")
        stride = self.width * 3
        for y in range(self.height):
            row = image.rgb[y * stride : (y + 1) * stride]
            self.values.extend(row[i] + row[i + 1] + row[i + 2] for i in range(0, stride, 3))

    def line(self, position: int, horizontal: bool) -> array:
        """Une ligne ou une colonne entière de niveaux, extraite d'un coup."""
        if horizontal:
            return self.values[position * self.width : (position + 1) * self.width]
        return self.values[position :: self.width]


def _bands(levels: _Levels, horizontal: bool) -> list[_Band]:
    """
    Traits de l'image dans un sens, les rangs voisins réunis.

    Chaque rang est éprouvé, et chaque pixel du rang avec lui. Rien n'est
    échantillonné ici : le pointillé de Power BI alterne deux pixels pleins et
    deux vides, et un balayage d'un pas de quatre tombait, selon l'endroit où
    la fenêtre commence, tantôt sur les pleins, tantôt sur les vides — la même
    bordure se voyait ou disparaissait selon le cadrage.
    """
    count = levels.height if horizontal else levels.width
    found: list[_Band] = []
    for position in range(LINE_MARGIN, count - LINE_MARGIN):
        band = _band(levels, position, horizontal)
        if band is None:
            continue
        if found and band.first - found[-1].last <= 1:
            found[-1] = found[-1].joined(band)
        else:
            found.append(band)
    return found


def _band(levels: _Levels, position: int, horizontal: bool) -> _Band | None:
    """
    Le trait porté par cette ligne, s'il y en a un.

    Les marques de la ligne — les pixels qui tranchent sur leur voisinage — se
    groupent en suites ; la plus longue est le trait. Ce qui reste est ailleurs
    sur la ligne : un mot, la bordure d'un visuel, et cela ne rallonge pas le
    trait.
    """
    here = levels.line(position, horizontal)
    before = levels.line(position - LINE_MARGIN, horizontal)
    after = levels.line(position + LINE_MARGIN, horizontal)
    marks = [
        index for index, level in enumerate(here) if _stands_out(level, before[index], after[index])
    ]

    run = _longest_run(marks)
    if not run:
        return None

    start, end = run[0], run[-1]
    length = end - start + 1
    if length < len(here) * MIN_SHARE or len(run) < length * LINE_DENSITY:
        return None
    return _Band(position, position, start, end)


def _stands_out(level: int, before: int, after: int) -> bool:
    """
    Le pixel tranche-t-il sur ses deux voisins, et du même côté ?

    Du même côté, parce qu'un trait est plus sombre que la page **de part et
    d'autre** — ou plus clair, sur un habillage sombre. Un pixel pris entre un
    voisin clair et un voisin sombre est au milieu d'un dégradé, et non sur un
    trait : c'est ce qui écarte les ombres et les bords adoucis.
    """
    low, high = level - before, level - after
    return min(abs(low), abs(high)) >= LINE_CONTRAST and (low > 0) == (high > 0)


def _longest_run(marks: list[int]) -> list[int]:
    """La plus longue suite de marques dont aucune n'est isolée des autres."""
    best: list[int] = []
    start = 0
    for index in range(1, len(marks) + 1):
        if index < len(marks) and marks[index] - marks[index - 1] <= LINE_GAP:
            continue
        if index - start > len(best):
            best = marks[start:index]
        start = index
    return best


# ─────────────────────────────────────────────────────────────
#  Retenir, ou non
# ─────────────────────────────────────────────────────────────


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
