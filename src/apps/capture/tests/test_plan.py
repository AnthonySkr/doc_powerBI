"""
Plan de capture : ce que le rapport dit qu'il y a à photographier.

Le plan se calcule sans ouvrir Power BI. C'est ce qui permet de répondre avant
toute capture : combien de prises, de quoi, et lesquelles le rapport ne place
pas assez précisément pour qu'on puisse les cadrer.
"""

import unittest

from src.apps.capture import plan
from src.apps.capture.geometry import Rect
from src.shared.models import ReportPage, Visual, VisualGroup


def visual(name: str, title: str, x=0.0, y=0.0, width=400.0, height=300.0) -> Visual:
    return Visual(
        id=name,
        visual_type="clusteredColumnChart",
        title=title,
        name=name,
        pos_x=x,
        pos_y=y,
        width=width,
        height=height,
    )


def page(*visuals: Visual, **values) -> ReportPage:
    built = ReportPage(
        name=values.get("name", "page_1"), display_name=values.get("title", "Ventes")
    )
    built.visuals = list(visuals)
    built.ungrouped_visuals = list(visuals)
    return built


class VisualShotsTest(unittest.TestCase):
    def test_une_prise_par_visuel(self):
        plans = plan.build([page(visual("v1", "CA"), visual("v2", "Marge"))])
        self.assertEqual([shot.title for shot in plans[0].shots], ["CA", "Marge"])
        self.assertEqual(plan.count(plans), 2)

    def test_la_prise_reprend_la_place_declaree(self):
        plans = plan.build([page(visual("v1", "CA", x=120, y=40, width=500, height=250))])
        self.assertEqual(plans[0].shots[0].area, Rect(120, 40, 500, 250))

    def test_le_nom_technique_sert_de_cle(self):
        """Renommer un visuel dans Power BI ne doit pas égarer sa capture."""
        plans = plan.build([page(visual("abc123", "Titre du jour"))])
        self.assertEqual(plans[0].shots[0].name, "abc123")

    def test_un_visuel_sans_dimensions_est_decrit_mais_ecarte(self):
        plans = plan.build([page(visual("v1", "CA", width=0, height=0))])
        shot = plans[0].shots[0]
        self.assertFalse(shot.is_placed)
        self.assertEqual(shot.title, "CA")
        self.assertEqual(plan.count(plans), 0)

    def test_le_canevas_de_la_page_est_celui_du_rapport(self):
        built = page(visual("v1", "CA"))
        built.canvas_width, built.canvas_height = 1600.0, 900.0
        plans = plan.build([built])
        self.assertEqual((plans[0].canvas.width, plans[0].canvas.height), (1600, 900))


class GroupShotsTest(unittest.TestCase):
    """Un groupe se capture d'un tenant : son étendue vient de ses membres."""

    def _page_with_group(self) -> ReportPage:
        group = VisualGroup(id="g1", name="g1", title="Indicateurs")
        group.visuals = [
            visual("v1", "CA", x=0, y=0, width=200, height=100),
            visual("v2", "Marge", x=300, y=150, width=200, height=100),
        ]
        built = ReportPage(name="page_1", display_name="Ventes")
        built.groups = [group]
        built.ungrouped_visuals = [visual("v3", "Détail", x=0, y=400)]
        return built

    def test_l_etendue_couvre_tous_les_membres(self):
        plans = plan.build([self._page_with_group()])
        group_shot = plans[0].shots[0]
        self.assertEqual(group_shot.kind, plan.GROUP)
        self.assertEqual(group_shot.area, Rect(0, 0, 500, 250))

    def test_les_visuels_isoles_suivent_les_groupes(self):
        plans = plan.build([self._page_with_group()])
        self.assertEqual([shot.title for shot in plans[0].shots], ["Indicateurs", "Détail"])

    def test_les_sous_groupes_comptent_dans_l_etendue(self):
        group = VisualGroup(id="g1", name="g1", title="Indicateurs")
        group.visuals = [visual("v1", "CA", x=0, y=0, width=100, height=100)]
        sub = VisualGroup(id="g2", name="g2", title="Détail")
        sub.visuals = [visual("v2", "Marge", x=600, y=400, width=100, height=100)]
        group.subgroups = [sub]

        built = ReportPage(name="page_1", display_name="Ventes")
        built.groups = [group]
        self.assertEqual(plan.build([built])[0].shots[0].area, Rect(0, 0, 700, 500))


class WithoutOrganisationTest(unittest.TestCase):
    """Le plan est aussi calculable sur un rapport tout juste lu."""

    def test_les_visuels_de_la_page_servent_faute_de_mieux(self):
        built = ReportPage(name="page_1", display_name="Ventes")
        built.visuals = [visual("v1", "CA")]
        self.assertEqual(len(plan.build([built])[0].shots), 1)


class OnlyTest(unittest.TestCase):
    """Restreindre le plan, pour éprouver une capture sans dérouler le reste."""

    def setUp(self):
        self.plans = plan.build(
            [
                page(visual("v1", "CA"), visual("v2", "Marge"), name="p_ventes", title="Ventes"),
                page(visual("v3", "Stock"), name="p_stock", title="Stocks"),
            ]
        )

    def test_par_page(self):
        kept = plan.only(self.plans, page="stock")
        self.assertEqual([p.title for p in kept], ["Stocks"])

    def test_par_prise(self):
        kept = plan.only(self.plans, shot="marge")
        self.assertEqual([shot.title for p in kept for shot in p.shots], ["Marge"])

    def test_le_nom_technique_marche_aussi(self):
        self.assertEqual(len(plan.only(self.plans, shot="v3")), 1)

    def test_sans_filtre_le_plan_est_entier(self):
        self.assertEqual(plan.count(plan.only(self.plans)), 3)

    def test_un_filtre_sans_correspondance_ne_garde_rien(self):
        self.assertEqual(plan.only(self.plans, page="absente"), [])


if __name__ == "__main__":
    unittest.main()
