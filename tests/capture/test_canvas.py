"""
Retrouver le canevas dans l'image de la fenêtre, sans fenêtre ni Power BI.

Une image de Power BI, vue d'ici, c'est un fond uni avec un rectangle plus
clair au milieu et des visuels dedans : cela se fabrique en quelques octets. Ce
qui se vérifie ici est ce qui décide du cadrage de toutes les captures — et ce
qui garde le script d'y croire quand ce n'est pas ça.
"""

import unittest

from src.gui_automator import canvas, png
from src.gui_automator.canvas import Image
from src.gui_automator.geometry import Rect

CHROME = (0xF1, 0xF1, 0xF1)  # le fond de l'application, autour du canevas
PAGE = (0xFF, 0xFF, 0xFF)  # une page blanche
VISUAL = (0x33, 0x66, 0x99)  # un visuel posé dessus

RATIO = 1280 / 720


def window(
    width: int,
    height: int,
    page: Rect | None = None,
    visuals: tuple[Rect, ...] = (),
    background: tuple[int, int, int] = CHROME,
) -> Image:
    """Image de fenêtre : un fond, un canevas, et des visuels par-dessus."""
    pixels = bytearray(bytes(background) * (width * height))
    for area, color in [(page, PAGE), *[(v, VISUAL) for v in visuals]]:
        if area is None:
            continue
        for y in range(int(area.top), int(area.bottom)):
            for x in range(int(area.left), int(area.right)):
                if 0 <= x < width and 0 <= y < height:
                    start = (y * width + x) * 3
                    pixels[start : start + 3] = bytes(color)
    return Image(width, height, bytes(pixels))


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
