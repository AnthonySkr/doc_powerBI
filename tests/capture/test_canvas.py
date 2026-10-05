"""
Retrouver le canevas dans l'image de la fenêtre, sans fenêtre ni Power BI.

Une image de Power BI, vue d'ici, c'est un fond uni avec un rectangle plus
clair au milieu et des visuels dedans : cela se fabrique en quelques octets. Ce
qui se vérifie ici est ce qui décide du cadrage de toutes les captures — et ce
qui garde le script d'y croire quand ce n'est pas ça.

Deux familles de cas, parce qu'il y a deux chemins pour trouver le canevas :
le pourtour, quand le fond de l'application l'entoure, et la bordure
pointillée, quand l'habillage du rapport est de la couleur de ses pages et
qu'il n'y a plus de pourtour du tout. La seconde famille est celle d'un
rapport réel dont toutes les captures tombaient à deux cents pixels de leur
visuel — le cadrage retenu était alors celui des marges déclarées.
"""

import unittest

from src.gui_automator import canvas, png
from src.gui_automator.canvas import Image
from src.gui_automator.geometry import Rect

CHROME = (0xF1, 0xF1, 0xF1)  # le fond de l'application, autour du canevas
PAGE = (0xFF, 0xFF, 0xFF)  # une page blanche
VISUAL = (0x33, 0x66, 0x99)  # un visuel posé dessus
BORDER = (0x60, 0x5E, 0x5C)  # le pointillé dont Power BI entoure le canevas

RATIO = 1280 / 720


class Canvas:
    """
    Une image de fenêtre que l'on peint, puis que l'on fait lire au module.

    Les pixels sont ceux que `mss` ramènerait : trois octets par pixel, lignes
    du haut vers le bas. Rien ici ne dépend d'une bibliothèque d'images.
    """

    def __init__(self, width: int, height: int, background: tuple[int, int, int] = CHROME):
        self.width = width
        self.height = height
        self.pixels = bytearray(bytes(background) * (width * height))

    def fill(self, area: Rect, color: tuple[int, int, int]) -> Canvas:
        """Un rectangle plein."""
        for y in range(int(area.top), int(area.bottom)):
            for x in range(int(area.left), int(area.right)):
                self.dot(x, y, color)
        return self

    def dashes(self, area: Rect, color: tuple[int, int, int] = BORDER) -> Canvas:
        """
        Le contour pointillé du canevas : deux pixels pleins, deux vides.

        C'est le motif de Power BI Desktop, et c'est lui qui piégeait un
        balayage d'un pas de quatre — selon l'endroit où la fenêtre commençait,
        on tombait toujours sur les pleins, ou toujours sur les vides.
        """
        left, top = int(area.left), int(area.top)
        right, bottom = int(area.right) - 1, int(area.bottom) - 1
        for x in range(left, right + 1):
            if x % 4 < 2:
                self.fill(Rect(x, top, 1, 2), color).fill(Rect(x, bottom - 1, 1, 2), color)
        for y in range(top, bottom + 1):
            if y % 4 < 2:
                self.fill(Rect(left, y, 2, 1), color).fill(Rect(right - 1, y, 2, 1), color)
        return self

    def dot(self, x: int, y: int, color: tuple[int, int, int]) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            start = (y * self.width + x) * 3
            self.pixels[start : start + 3] = bytes(color)

    def image(self) -> Image:
        return Image(self.width, self.height, bytes(self.pixels))

    def cropped(self, left: int, top: int) -> Image:
        """
        L'image telle qu'elle serait si la fenêtre commençait un peu plus loin.

        C'est ce que donnent deux écrans, ou une fenêtre agrandie dont le cadre
        déborde : la bordure ne bouge pas, mais sa position dans l'image change
        de phase — et le module doit la voir quand même.
        """
        width, height = self.width - left, self.height - top
        rows = [
            self.pixels[((top + y) * self.width + left) * 3 :][: width * 3] for y in range(height)
        ]
        return Image(width, height, b"".join(bytes(row) for row in rows))


def window(
    width: int,
    height: int,
    page: Rect | None = None,
    visuals: tuple[Rect, ...] = (),
    background: tuple[int, int, int] = CHROME,
) -> Image:
    """Image de fenêtre : un fond, un canevas, et des visuels par-dessus."""
    drawn = Canvas(width, height, background)
    for area, color in [(page, PAGE), *[(v, VISUAL) for v in visuals]]:
        if area is not None:
            drawn.fill(area, color)
    return drawn.image()


def dressed_window(canvas_area: Rect, width: int = 600, height: int = 400) -> Canvas:
    """
    Une fenêtre dont l'habillage est de la couleur des pages, ruban compris.

    Le cas qui met le pourtour en échec : la page est blanche, ce qui l'entoure
    est blanc aussi, et le seul gris de l'image est celui du ruban et du volet
    — c'est-à-dire tout ce qui n'est **pas** le canevas. Ne reste, pour le
    trouver, que le pointillé qui l'entoure.
    """
    drawn = Canvas(width, height, PAGE)
    drawn.fill(Rect(0, 0, width, 40), CHROME)  # le ruban
    drawn.fill(Rect(width - 40, 0, 40, height), CHROME)  # le volet de droite
    drawn.fill(Rect(0, height - 30, width, 30), CHROME)  # la barre des onglets
    return drawn.dashes(canvas_area)


class DetectTest(unittest.TestCase):
    def test_le_canevas_est_le_rectangle_qui_n_est_pas_le_fond(self):
        image = window(800, 600, page=Rect(50, 100, 640, 360))

        self.assertEqual(canvas.detect(image, RATIO), Rect(50, 100, 640, 360))

    def test_les_visuels_ne_debordent_pas_du_canevas(self):
        """Ce qui est dessiné dessus ne change pas ses bords."""
        image = window(
            800,
            600,
            page=Rect(50, 100, 640, 360),
            visuals=(Rect(60, 110, 200, 150), Rect(400, 300, 280, 150)),
        )

        self.assertEqual(canvas.detect(image, RATIO), Rect(50, 100, 640, 360))

    def test_un_canevas_colle_au_bord_reste_trouve(self):
        image = window(660, 400, page=Rect(0, 20, 640, 360))

        self.assertEqual(canvas.detect(image, RATIO), Rect(0, 20, 640, 360))

    def test_un_canevas_aux_mauvaises_proportions_est_refuse(self):
        """Rapport non ajusté à la page, ou zoomé : on ne devine pas."""
        image = window(800, 600, page=Rect(50, 100, 640, 200))

        self.assertIsNone(canvas.detect(image, RATIO))

    def test_une_image_tout_unie_ne_donne_rien(self):
        self.assertIsNone(canvas.detect(window(800, 600), RATIO))

    def test_un_canevas_qui_remplit_tout_ne_se_distingue_pas(self):
        """Sans fond autour, rien ne dit où le canevas commence."""
        image = window(800, 600, page=Rect(0, 0, 800, 600))

        self.assertIsNone(canvas.detect(image, RATIO))

    def test_un_petit_rectangle_n_est_pas_le_canevas(self):
        """Une boîte de dialogue aux bonnes proportions n'est pas un canevas."""
        image = window(800, 600, page=Rect(300, 250, 128, 72))

        self.assertIsNone(canvas.detect(image, RATIO))

    def test_une_image_vide_ne_donne_rien(self):
        self.assertIsNone(canvas.detect(Image(0, 0, b""), RATIO))
        self.assertIsNone(canvas.detect(window(100, 100), 0))

    def test_le_canevas_d_une_page_au_format_libre(self):
        """Le rapport déclare ses proportions : elles ne sont pas toujours 16:9."""
        image = window(800, 600, page=Rect(100, 50, 400, 400))

        self.assertEqual(canvas.detect(image, 1.0), Rect(100, 50, 400, 400))


class BorderedDetectTest(unittest.TestCase):
    """
    Le canevas reconnu à son pointillé, faute de pourtour.

    Le rapport qui a fait écrire ce chemin-là : habillage blanc, pages
    blanches, et des marges déclarées qui, en plus, coupaient le canevas à
    droite. Toutes les captures sortaient de la bonne forme et deux cents
    pixels trop à gauche.
    """

    def setUp(self):
        self.area = Rect(100, 80, 384, 216)  # 16:9, et 64 % de la largeur

    def test_l_habillage_de_la_couleur_des_pages_laisse_voir_la_bordure(self):
        found = canvas.detect(dressed_window(self.area).image(), RATIO)

        self.assertEqual(found, self.area)

    def test_le_pourtour_ne_trouve_rien_sur_une_telle_fenetre(self):
        """Ce que le seul premier chemin donnait : rien, ou de travers."""
        surrounded = canvas._surrounded_box(dressed_window(self.area).image())

        self.assertNotEqual(surrounded, self.area)

    def test_la_bordure_se_voit_ou_que_la_fenetre_commence(self):
        """
        Le pointillé alterne deux pixels pleins, deux vides.

        Photographier la fenêtre un pixel plus loin ne doit pas le faire
        disparaître : c'est ce qui arrivait quand on ne lisait qu'un pixel sur
        quatre — la même bordure se voyait ou non selon le cadrage.
        """
        drawn = dressed_window(self.area)
        for offset in range(4):
            with self.subTest(offset=offset):
                found = canvas.detect(drawn.cropped(offset, offset), RATIO)

                self.assertEqual(found, self.area.moved(-offset, -offset))

    def test_un_visuel_colle_au_bord_ne_cache_pas_la_bordure(self):
        """Un visuel posé contre le bord en recouvre un tiers : il en reste."""
        drawn = dressed_window(self.area)
        drawn.fill(Rect(110, 250, 180, 48), PAGE)

        self.assertEqual(canvas.detect(drawn.image(), RATIO), self.area)

    def test_les_lignes_d_un_tableau_ne_font_pas_un_canevas(self):
        """
        Un tableau bordé de traits réguliers en porte de plus longs que lui.

        C'est ce qui interdit de retenir le premier trait rencontré : ce sont
        les quatre côtés d'un même rectangle, aux proportions de la page, qui
        désignent le canevas.
        """
        drawn = dressed_window(self.area)
        for row in range(6):
            drawn.fill(Rect(120, 120 + row * 20, 340, 1), BORDER)

        self.assertEqual(canvas.detect(drawn.image(), RATIO), self.area)

    def test_un_trait_seul_ne_borde_rien(self):
        drawn = Canvas(600, 400, PAGE)
        drawn.fill(Rect(100, 80, 384, 2), BORDER)

        self.assertIsNone(canvas.detect(drawn.image(), RATIO))

    def test_une_bordure_aux_mauvaises_proportions_est_refusee(self):
        """Rapport zoomé, ou non ajusté à la page : on ne devine pas."""
        found = canvas.detect(dressed_window(Rect(100, 80, 384, 280)).image(), RATIO)

        self.assertIsNone(found)


class LookalikeTest(unittest.TestCase):
    """
    Le haut et le bas du canevas, le bord d'un tableau à gauche, celui du
    volet Filtres à droite : un rectangle aux bonnes proportions, un peu plus
    grand que le canevas, et décalé. C'est ce qui décalait toutes les prises
    des pages où le pourtour ne se voyait pas.
    """

    def setUp(self):
        self.page = Rect(50, 40, 480, 270)
        drawn = dressed_window(self.page)
        drawn.fill(Rect(80, 40, 2, 270), BORDER)  # le bord plein d'un tableau
        drawn.fill(Rect(562, 0, 2, 400), BORDER)  # le bord du volet Filtres
        self.image = drawn.image()

    def test_le_rectangle_pointille_l_emporte_sur_un_plus_grand_a_bords_pleins(self):
        self.assertEqual(canvas.detect(self.image, RATIO), self.page)

    def test_le_canevas_deja_connu_est_prefere_s_il_est_toujours_la(self):
        self.assertEqual(canvas.detect(self.image, RATIO, hint=self.page), self.page)


class OverflowTest(unittest.TestCase):
    """
    Un visuel qui déborde du canevas élargit son pourtour : de quelques pixels,
    assez pour rester dans la tolérance, trop pour cadrer juste. La bordure
    pointillée, elle, n'a pas bougé — c'est elle qui fait foi.
    """

    def test_la_bordure_l_emporte_sur_un_pourtour_elargi(self):
        page = Rect(50, 40, 480, 270)
        drawn = Canvas(600, 400)
        drawn.fill(page, PAGE)
        drawn.fill(Rect(45, 200, 490, 60), VISUAL)  # un tableau qui déborde de 5 px
        drawn.dashes(page)
        self.assertEqual(canvas.detect(drawn.image(), RATIO), page)

    def test_sans_bordure_le_pourtour_reste_retenu(self):
        page = Rect(50, 40, 480, 270)
        image = window(600, 400, page, visuals=(Rect(45, 200, 490, 60),))
        found = canvas.detect(image, RATIO)
        self.assertIsNotNone(found)  # à peu près : c'est tout ce qu'il y a à voir
        self.assertGreater(found.width, page.width)


class OutlineTest(unittest.TestCase):
    """Le calibrage dessine sur la capture ce que le script croit voir."""

    def setUp(self):
        self.image = window(200, 200)

    def test_le_contour_est_trace_a_la_bonne_place(self):
        marked = Image(200, 200, canvas.outline(self.image, [Rect(50, 50, 100, 60)], (255, 0, 0)))

        self.assertEqual(marked.at(50, 50), (255, 0, 0))
        self.assertEqual(marked.at(149, 109), (255, 0, 0))
        self.assertEqual(marked.at(100, 80), CHROME)  # l'intérieur est intact

    def test_un_contour_qui_deborde_ne_casse_rien(self):
        marked = canvas.outline(self.image, [Rect(-20, -20, 300, 300)], (255, 0, 0))

        self.assertEqual(len(marked), len(self.image.rgb))

    def test_l_image_marquee_reste_un_png_valide(self):
        marked = canvas.outline(self.image, [Rect(10, 10, 50, 50)], (255, 0, 0))
        written = png.encode(self.image.width, self.image.height, marked)

        self.assertEqual(written[:8], b"\x89PNG\r\n\x1a\n")
        self.assertTrue(written.endswith(b"IEND\xaeB`\x82"))


if __name__ == "__main__":
    unittest.main()
