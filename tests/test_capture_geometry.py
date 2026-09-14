"""
Cadrage des captures : du repère du rapport à celui de l'écran.

C'est le seul endroit où le recadrage se vérifie sans écran : Power BI met le
canevas à l'échelle et le centre, et c'est ce calcul-là qui décide si une
capture tombe sur le visuel ou à côté.
"""

import unittest

from src.capture.geometry import Rect, Size, fit, place, union


class FitTest(unittest.TestCase):
    """Le canevas est mis à l'échelle sans se déformer, puis centré."""

    def test_zone_aux_memes_proportions(self):
        rendered = fit(Size(1280, 720), Rect(0, 0, 1280, 720))
        self.assertEqual(rendered, Rect(0, 0, 1280, 720))

    def test_zone_plus_large_laisse_des_bandes_laterales(self):
        # 1920 × 720 pour un canevas 16:9 : la hauteur contraint, et le
        # canevas de 1280 de large est centré dans 1920.
        rendered = fit(Size(1280, 720), Rect(0, 0, 1920, 720))
        self.assertEqual(rendered, Rect(320, 0, 1280, 720))

    def test_zone_plus_haute_laisse_des_bandes_au_dessus(self):
        rendered = fit(Size(1280, 720), Rect(0, 0, 1280, 1080))
        self.assertEqual(rendered, Rect(0, 180, 1280, 720))

    def test_echelle_conservee_dans_les_deux_sens(self):
        rendered = fit(Size(1280, 720), Rect(0, 0, 640, 640))
        self.assertEqual(rendered.width / rendered.height, 1280 / 720)

    def test_origine_de_la_zone_reportee(self):
        """La zone ne commence pas au coin de l'écran : la fenêtre est ailleurs."""
        rendered = fit(Size(1280, 720), Rect(100, 200, 1280, 720))
        self.assertEqual(rendered, Rect(100, 200, 1280, 720))

    def test_zone_vide_ne_place_rien(self):
        self.assertTrue(fit(Size(1280, 720), Rect(10, 10, 0, 500)).is_empty)

    def test_canevas_vide_ne_place_rien(self):
        self.assertTrue(fit(Size(0, 0), Rect(0, 0, 1920, 1080)).is_empty)


class PlaceTest(unittest.TestCase):
    """Un visuel suit le canevas : même facteur, même origine."""

    def setUp(self):
        self.canvas = Size(1280, 720)
        # Canevas rendu à l'échelle 1,5 et décalé de (320, 100).
        self.rendered = Rect(320, 100, 1920, 1080)

    def test_visuel_au_coin_suit_l_origine(self):
        area = place(Rect(0, 0, 640, 360), self.canvas, self.rendered)
        self.assertEqual(area, Rect(320, 100, 960, 540))

    def test_visuel_decale_suit_l_echelle(self):
        area = place(Rect(640, 360, 640, 360), self.canvas, self.rendered)
        self.assertEqual(area, Rect(320 + 960, 100 + 540, 960, 540))

    def test_visuel_debordant_est_ramene_au_bord(self):
        """Power BI laisse poser un visuel hors du canevas ; l'écran, non."""
        area = place(Rect(1200, 0, 400, 200), self.canvas, self.rendered)
        self.assertEqual(area.right, self.rendered.right)

    def test_visuel_entierement_dehors_ne_donne_rien(self):
        area = place(Rect(2000, 2000, 100, 100), self.canvas, self.rendered)
        self.assertTrue(area.is_empty)

    def test_canevas_non_rendu_ne_donne_rien(self):
        area = place(Rect(0, 0, 100, 100), self.canvas, Rect(0, 0, 0, 0))
        self.assertTrue(area.is_empty)


class RectTest(unittest.TestCase):
    def test_inset_ronge_les_quatre_cotes(self):
        framed = Rect(0, 0, 1000, 800).inset(left=10, top=130, right=340, bottom=60)
        self.assertEqual(framed, Rect(10, 130, 650, 610))

    def test_inset_plus_large_que_le_rectangle_le_vide(self):
        self.assertTrue(Rect(0, 0, 100, 100).inset(left=200).is_empty)

    def test_rounded_garde_les_bords(self):
        """Arrondir la largeur ferait dériver le cadrage selon la position."""
        rounded = Rect(10.6, 20.4, 100.2, 50.3).rounded()
        self.assertEqual((rounded.left, rounded.top), (11, 20))
        self.assertEqual((rounded.right, rounded.bottom), (111, 71))

    def test_rect_vide_se_reconnait(self):
        self.assertTrue(Rect(0, 0, 0, 10).is_empty)
        self.assertFalse(Rect(0, 0, 1, 1).is_empty)


class UnionTest(unittest.TestCase):
    """L'étendue d'un groupe : Power BI ne déclare que celle de ses membres."""

    def test_etend_jusqu_aux_bords_extremes(self):
        etendue = union([Rect(100, 50, 200, 100), Rect(400, 200, 100, 100)])
        self.assertEqual(etendue, Rect(100, 50, 400, 250))

    def test_ignore_les_membres_sans_dimensions(self):
        etendue = union([Rect(10, 10, 100, 100), Rect(0, 0, 0, 0)])
        self.assertEqual(etendue, Rect(10, 10, 100, 100))

    def test_sans_membre_place_l_etendue_est_vide(self):
        self.assertTrue(union([Rect(0, 0, 0, 0)]).is_empty)
        self.assertTrue(union([]).is_empty)


if __name__ == "__main__":
    unittest.main()
