"""
De quoi découle le cadrage : l'image, ou les marges déclarées ?

`desktop.DesktopRecorder` pilote Power BI, ce qui ne se rejoue pas ici. Mais la
décision qu'il prend — retenir le canevas reconnu dans l'image, ou retomber
sur les marges du plan — est du calcul, et c'est celle qui décidait du cadrage
de toutes les captures d'un rapport réel. Elle se vérifie sans Windows : il
suffit de lui donner une image au lieu d'un écran.
"""

import unittest
from unittest.mock import patch

from src.core import console
from src.gui_automator import finder
from src.gui_automator.canvas import Image
from src.gui_automator.desktop import DesktopOptions, DesktopRecorder, Insets
from src.gui_automator.geometry import Rect, Size

CHROME = (0xF1, 0xF1, 0xF1)
PAGE = (0xFF, 0xFF, 0xFF)

FRAME = Rect(0, 0, 800, 600)
CANVAS = Size(1280, 720)
# Le canevas tel qu'il est dessiné dans cette fenêtre-là : 16:9, et assez
# grand pour que la reconnaissance le tienne pour le canevas.
DRAWN = Rect(64, 120, 640, 360)


def window(page: Rect | None = None) -> Image:
    """Image de fenêtre : le fond de l'application, et une page dessus."""
    pixels = bytearray(bytes(CHROME) * (int(FRAME.width) * int(FRAME.height)))
    if page is not None:
        for y in range(int(page.top), int(page.bottom)):
            for x in range(int(page.left), int(page.right)):
                start = (y * int(FRAME.width) + x) * 3
                pixels[start : start + 3] = bytes(PAGE)
    return Image(int(FRAME.width), int(FRAME.height), bytes(pixels))


def _cropped(image: Image, area: Rect) -> Image:
    """Un morceau d'image, comme la capture d'écran en ramènerait un."""
    left, top = int(area.left), int(area.top)
    width, height = int(area.width), int(area.height)
    rows = [image.rgb[((top + y) * image.width + left) * 3 :][: width * 3] for y in range(height)]
    return Image(width, height, b"".join(rows))


class Screen(DesktopRecorder):
    """
    Un enregistreur dont l'écran est une image fabriquée ici.

    Seule la frontière avec Windows est remplacée : la fenêtre trouvée, et les
    pixels qu'on en photographie. Tout le reste est le code qui tournera.
    """

    def __init__(self, image: Image, options: DesktopOptions | None = None):
        super().__init__(options)
        self.image = image
        # Les zones photographiées, dans l'ordre : de quoi vérifier *où* le
        # script regarde, et combien de fois.
        self.areas: list[Rect] = []
        self._handle = 1  # une fenêtre, pour la forme

    @property
    def reads(self) -> int:
        return len(self.areas)

    def window_frame(self) -> Rect:
        return FRAME

    def _pixels(self, area: Rect) -> Image:
        """L'image de la zone demandée, découpée dans celle de la fenêtre."""
        self.areas.append(area)
        return _cropped(self.image, area.moved(-FRAME.left, -FRAME.top).rounded())


class CanvasAreaTest(unittest.TestCase):
    def setUp(self):
        """La reconnaissance se raconte dans la console : pas pendant les tests."""
        self.enterContext(console.silenced())

    def test_le_canevas_reconnu_l_emporte_sur_les_marges(self):
        screen = Screen(window(page=DRAWN))

        self.assertEqual(screen.canvas_area(CANVAS), DRAWN)
        self.assertNotEqual(screen.canvas_area(CANVAS), screen.viewport())

    def test_faute_de_le_reconnaitre_les_marges_reprennent_la_main(self):
        """Une fenêtre tout unie : rien à reconnaître, et le plan tranche."""
        screen = Screen(window())

        self.assertEqual(screen.canvas_area(CANVAS), screen.viewport())

    def test_un_canevas_aux_mauvaises_proportions_ne_sert_pas_de_cadrage(self):
        """Rapport zoomé, ou non ajusté : les marges plutôt qu'un cadrage faux."""
        screen = Screen(window(page=Rect(64, 120, 640, 200)))

        self.assertIsNone(screen.measured_canvas(CANVAS))
        self.assertEqual(screen.canvas_area(CANVAS), screen.viewport())

    def test_le_canevas_n_est_cherche_qu_une_fois(self):
        """
        Reconnaître le canevas coûte une seconde, et il ne bouge pas.

        Une séance de trente pages ne peut pas la payer trente fois.
        """
        screen = Screen(window(page=DRAWN))

        first = screen.canvas_area(CANVAS)
        searched = screen.reads
        again = [screen.canvas_area(CANVAS) for _ in range(3)]

        self.assertEqual(again, [first] * 3)
        self.assertEqual(screen.reads, searched)  # plus rien n'est photographié

    def test_detection_coupee_le_cadrage_reste_declare(self):
        screen = Screen(window(page=DRAWN), DesktopOptions(detect_canvas=False))

        self.assertEqual(screen.canvas_area(CANVAS), screen.viewport())
        self.assertEqual(screen.reads, 0)


class PageChangeTest(unittest.TestCase):
    """À quoi l'on voit qu'une page a tourné."""

    def setUp(self):
        self.enterContext(console.silenced())

    def test_l_empreinte_se_prend_au_milieu_de_la_fenetre(self):
        """
        Ni sur la fenêtre entière — la barre de titre change d'aspect dès que
        la fenêtre prend le focus, ce qui passerait pour une page tournée —,
        ni dans les marges déclarées, qui peuvent ne montrer qu'un bout de
        ruban immobile. Au milieu, que le canevas couvre toujours.
        """
        screen = Screen(window(page=DRAWN))

        screen._fingerprint()

        self.assertEqual(screen.areas, [Rect(200, 150, 400, 300)])


class SearchAreaTest(unittest.TestCase):
    """Où l'on cherche, et depuis quel bord les marges se comptent."""

    def setUp(self):
        self.options = DesktopOptions(insets=Insets(left=1, top=10, right=100, bottom=20))
        self.enterContext(console.silenced())

    def test_on_cherche_dans_les_marges_puis_dans_toute_la_zone_utile(self):
        """De la plus étroite à la plus large : la seconde rattrape la première."""
        screen = Screen(window(page=DRAWN), self.options)

        self.assertEqual(screen.search_areas(), [screen.viewport(), screen.client_frame()])

    def test_des_marges_qui_coupent_le_canevas_ne_l_empechent_plus(self):
        """
        C'est le cas qui faussait tout : des marges déclarées trop larges
        rognaient le canevas, la reconnaissance n'y trouvait plus les
        proportions annoncées, et le cadrage retombait sur ces mêmes marges.
        """
        cropping = DesktopOptions(insets=Insets(right=400))
        screen = Screen(window(page=DRAWN), cropping)

        self.assertLess(screen.viewport().right, DRAWN.right)  # le canevas est coupé
        self.assertEqual(screen.canvas_area(CANVAS), DRAWN)

    def test_les_marges_se_comptent_depuis_la_zone_utile(self):
        """
        Et non depuis le cadre, dont une part est hors écran si la fenêtre est
        agrandie (voir `finder.client_box`).
        """
        screen = Screen(window(), self.options)
        client = (10, 10, 780, 580)

        with patch.object(finder, "client_box", return_value=client):
            self.assertEqual(screen.client_frame(), Rect(*client))
            self.assertEqual(screen.viewport(), Rect(11, 20, 679, 550))

    def test_sans_zone_utile_lisible_le_cadre_entier_fait_l_affaire(self):
        """Hors de Windows, `client_box` ne répond rien — et rien n'échoue."""
        screen = Screen(window(), self.options)

        with patch.object(finder, "client_box", return_value=None):
            self.assertEqual(screen.client_frame(), FRAME)


if __name__ == "__main__":
    unittest.main()
