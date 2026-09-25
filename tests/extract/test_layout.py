"""
Places des membres de groupe, ramenées au repère de la page.

Power BI écrit la place d'un membre de groupe tantôt dans le repère de la
page, tantôt dans celui du groupe qui le contient — et un groupe imbriqué se
compte alors depuis le coin de son parent. Le cadre déclaré de chaque groupe
tranche, maillon par maillon.
"""

import unittest

from src.core.models import ReportPage, Visual, VisualGroup
from src.pbi_extractor.report.layout import to_page_coordinates


def visual(name: str, x: float, y: float, width=200.0, height=100.0, group="") -> Visual:
    return Visual(
        id=name,
        visual_type="card",
        title=name,
        elements=[],
        filters=[],
        has_measures=False,
        pos_x=x,
        pos_y=y,
        width=width,
        height=height,
        name=name,
        parent_group_name=group,
    )


def group(name: str, x: float, y: float, width: float, height: float, parent="") -> VisualGroup:
    return VisualGroup(
        id=name,
        name=name,
        title=name,
        parent_group_name=parent,
        pos_x=x,
        pos_y=y,
        width=width,
        height=height,
    )


def page(groups: list[VisualGroup], visuals: list[Visual]) -> ReportPage:
    built = ReportPage(name="page_1", display_name="Ventes")
    built.groups = groups
    built.visuals = visuals
    return built


def place(item: Visual | VisualGroup) -> tuple[float, float]:
    return (item.pos_x, item.pos_y)


class OneLevelTest(unittest.TestCase):
    """Un groupe à la racine : son cadre tranche entre les deux lectures."""

    def _settled(self, x: float, y: float) -> Visual:
        member = visual("v1", x, y, group="g1")
        to_page_coordinates(page([group("g1", 400, 200, 500, 300)], [member]))
        return member

    def test_des_coordonnees_de_page_sont_gardees(self):
        self.assertEqual(place(self._settled(450, 250)), (450, 250))

    def test_des_coordonnees_de_groupe_sont_ramenees_a_la_page(self):
        """Hors du cadre du groupe : c'est qu'elles partent de son coin."""
        self.assertEqual(place(self._settled(10, 20)), (410, 220))

    def test_un_visuel_hors_du_groupe_des_deux_facons_reste_tel_quel(self):
        """Ni dans le cadre, ni ramené dedans : le rapport a raison, pas nous."""
        self.assertEqual(place(self._settled(900, 900)), (900, 900))

    def test_sans_cadre_declare_rien_n_est_deplace(self):
        member = visual("v1", 10, 20, group="g1")
        to_page_coordinates(page([group("g1", 400, 200, 0, 0)], [member]))
        self.assertEqual(place(member), (10, 20))

    def test_un_visuel_hors_groupe_n_est_pas_touche(self):
        alone = visual("v1", 10, 20)
        to_page_coordinates(page([group("g1", 400, 200, 500, 300)], [alone]))
        self.assertEqual(place(alone), (10, 20))

    def test_dans_le_cadre_des_deux_facons_l_etendue_tranche(self):
        """
        Deux visuels qui remplissent le groupe depuis son coin : lus comme de
        la page, ils tiendraient aussi dans le cadre, mais ne l'épouseraient
        pas.
        """
        members = [visual("v1", 0, 0, 250, 150, "g1"), visual("v2", 250, 150, 250, 150, "g1")]
        to_page_coordinates(page([group("g1", 100, 100, 500, 300)], members))
        self.assertEqual([place(m) for m in members], [(100, 100), (350, 250)])


class NestedTest(unittest.TestCase):
    """
    Un groupe dans un groupe : chaque maillon se compte depuis son parent.

    C'est le cas du calibrage : un graphique cadré à la bonne taille, mais au
    coin du canevas, parce que seul le dernier maillon était corrigé.
    """

    def test_toute_la_chaine_est_remontee(self):
        outer = group("g1", 0, 220, 460, 500)
        inner = group("g2", 0, 0, 460, 260, parent="g1")
        chart = visual("v1", 10, 6, 440, 250, group="g2")
        to_page_coordinates(page([inner, outer], [chart]))

        self.assertEqual(place(inner), (0, 220))
        self.assertEqual(place(chart), (10, 226))

    def test_des_coordonnees_de_page_a_tous_les_niveaux_sont_gardees(self):
        outer = group("g1", 100, 200, 600, 400)
        inner = group("g2", 150, 250, 300, 200, parent="g1")
        chart = visual("v1", 160, 260, 280, 180, group="g2")
        to_page_coordinates(page([outer, inner], [chart]))

        self.assertEqual(place(inner), (150, 250))
        self.assertEqual(place(chart), (160, 260))

    def test_un_groupe_qui_se_contient_ne_boucle_pas(self):
        looped = group("g1", 100, 100, 200, 200, parent="g1")
        member = visual("v1", 10, 10, 50, 50, group="g1")
        to_page_coordinates(page([looped], [member]))
        self.assertEqual(place(member), (10, 10))


if __name__ == "__main__":
    unittest.main()
