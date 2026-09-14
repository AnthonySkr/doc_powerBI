"""
Du repère du rapport à celui de l'écran.

Power BI place ses visuels dans un **canevas logique** — 1280 × 720 par défaut
— et chaque visuel y déclare sa place. À l'écran, ce canevas est rendu dans une
zone dont la taille dépend de la fenêtre : Power BI l'y met à l'échelle en
conservant ses proportions, puis le centre dans ce qui reste. D'où les bandes
vides de part et d'autre d'un rapport 16:9 dans une fenêtre plus large.

Recadrer une capture sur un seul visuel se ramène donc à deux calculs :

    fit(canevas, zone)      où le canevas atterrit dans la zone visible
    place(visuel, ...)      où un visuel atterrit, le canevas étant posé là

Tout ici est du calcul : pas une ligne qui dépende de Power BI, de Windows ou
d'un écran. C'est le module où les cadrages se vérifient — et le seul de
`src.apps.capture` qui se teste entièrement sans rien ouvrir.
"""

from dataclasses import dataclass

__all__ = ["Rect", "Size", "fit", "place", "union"]


@dataclass(frozen=True)
class Size:
    """Dimensions d'un canevas, dans son propre repère."""

    width: float
    height: float

    @property
    def is_empty(self) -> bool:
        return self.width <= 0 or self.height <= 0


@dataclass(frozen=True)
class Rect:
    """
    Rectangle, coin supérieur gauche et dimensions.

    Sert dans les deux repères — celui du rapport et celui de l'écran. C'est
    l'appelant qui sait lequel ; les deux ne se mélangent que dans `place`.
    """

    left: float
    top: float
    width: float
    height: float

    @property
    def right(self) -> float:
        return self.left + self.width

    @property
    def bottom(self) -> float:
        return self.top + self.height

    @property
    def size(self) -> Size:
        return Size(self.width, self.height)

    @property
    def is_empty(self) -> bool:
        return self.width <= 0 or self.height <= 0

    def inset(self, left: float = 0, top: float = 0, right: float = 0, bottom: float = 0) -> Rect:
        """
        Rectangle rogné de chaque côté — les marges d'une fenêtre, par exemple.

        Un rognage plus large que le rectangle ne le retourne pas : il le rend
        vide, ce que `is_empty` signale.
        """
        return Rect(
            self.left + left,
            self.top + top,
            max(self.width - left - right, 0),
            max(self.height - top - bottom, 0),
        )

    def scaled(self, factor: float) -> Rect:
        """Rectangle homothétique, origine comprise."""
        return Rect(
            self.left * factor, self.top * factor, self.width * factor, self.height * factor
        )

    def moved(self, dx: float, dy: float) -> Rect:
        return Rect(self.left + dx, self.top + dy, self.width, self.height)

    def rounded(self) -> Rect:
        """
        Rectangle ramené à des pixels entiers, sans jamais rétrécir.

        Les bords sont arrondis séparément : arrondir la largeur plutôt que le
        bord droit ferait dériver le cadrage d'un pixel selon la position.
        """
        left, top = round(self.left), round(self.top)
        return Rect(left, top, round(self.right) - left, round(self.bottom) - top)

    def clamped(self, bounds: Rect) -> Rect:
        """
        Rectangle ramené à l'intérieur de `bounds`.

        Un visuel qui déborde du canevas — cela existe, Power BI le permet —
        donnerait sinon une zone de capture hors de l'écran.
        """
        left = min(max(self.left, bounds.left), bounds.right)
        top = min(max(self.top, bounds.top), bounds.bottom)
        right = min(max(self.right, bounds.left), bounds.right)
        bottom = min(max(self.bottom, bounds.top), bounds.bottom)
        return Rect(left, top, right - left, bottom - top)


def fit(canvas: Size, viewport: Rect) -> Rect:
    """
    Place le canevas dans la zone visible : mis à l'échelle, puis centré.

    C'est le « Ajuster à la page » de Power BI. Le facteur retenu est le plus
    petit des deux, sans quoi le canevas déborderait dans l'autre sens.

    Un canevas ou une zone de dimension nulle ne se place nulle part : le
    rectangle retourné est vide, et l'appelant renonce à capturer.
    """
    if canvas.is_empty or viewport.is_empty:
        return Rect(viewport.left, viewport.top, 0, 0)

    factor = min(viewport.width / canvas.width, viewport.height / canvas.height)
    width, height = canvas.width * factor, canvas.height * factor
    return Rect(
        viewport.left + (viewport.width - width) / 2,
        viewport.top + (viewport.height - height) / 2,
        width,
        height,
    )


def place(area: Rect, canvas: Size, rendered: Rect) -> Rect:
    """
    Rectangle écran d'un visuel, le canevas étant rendu dans `rendered`.

    Args:
        area: place du visuel dans le canevas, telle que le rapport la déclare
        canvas: dimensions de ce canevas
        rendered: où ce canevas est rendu à l'écran (voir `fit`)

    Le résultat est ramené dans `rendered` : un visuel qui déborde du canevas
    est capturé jusqu'à son bord, pas au-delà.
    """
    if canvas.is_empty or rendered.is_empty:
        return Rect(rendered.left, rendered.top, 0, 0)

    factor = rendered.width / canvas.width
    return area.scaled(factor).moved(rendered.left, rendered.top).clamped(rendered)


def union(areas: list[Rect]) -> Rect:
    """
    Plus petit rectangle contenant tous les autres.

    Un groupe de visuels se capture d'un seul tenant : c'est l'étendue de ses
    membres qui donne son cadre, Power BI ne déclarant pas celle du groupe.
    """
    present = [area for area in areas if not area.is_empty]
    if not present:
        return Rect(0, 0, 0, 0)

    left = min(area.left for area in present)
    top = min(area.top for area in present)
    right = max(area.right for area in present)
    bottom = max(area.bottom for area in present)
    return Rect(left, top, right - left, bottom - top)
