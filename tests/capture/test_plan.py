"""
Plan de capture : ce que le rapport dit qu'il y a à photographier.

Le plan se calcule sans ouvrir Power BI. C'est ce qui permet de répondre avant
toute capture : combien de prises, de quoi, et lesquelles le rapport ne place
pas assez précisément pour qu'on puisse les cadrer.

Le document réserve un emplacement par page, un par groupe et un par visuel
documenté — **y compris les visuels d'un groupe**, qu'il détaille sous la
capture d'ensemble. Le plan en prévoit donc exactement autant.
"""

import unittest

from src.core.models import ReportPage, Visual, VisualGroup
from src.gui_automator import plan
from src.gui_automator.geometry import Rect


def visual(name: str, title: str, x=0.0, y=0.0, width=400.0, height=300.0, group="") -> Visual:
    return Visual(
        id=name,
        visual_type="clusteredColumnChart",
        title=title,
        name=name,
        pos_x=x,
        pos_y=y,
        width=width,
        height=height,
        parent_group_name=group,
    )


def page(*visuals: Visual, **values) -> ReportPage:
    built = ReportPage(
        name=values.get("name", "page_1"), display_name=values.get("title", "Ventes")
    )
    built.visuals = list(visuals)
    built.ungrouped_visuals = list(visuals)
    return built


def shots(pages: list[ReportPage], kind: str = "") -> list[plan.Shot]:
    built = plan.build(pages)[0].shots
    return [shot for shot in built if not kind or shot.kind == kind]


class PageShotTest(unittest.TestCase):
    """La page entière est une prise comme les autres — la première."""

    def test_la_page_ouvre_le_plan(self):
        first = shots([page(visual("v1", "CA"))])[0]
        self.assertEqual(first.kind, plan.PAGE)
        self.assertEqual(first.name, plan.PAGE_SHOT)
        self.assertEqual(first.title, "Ventes")

    def test_la_prise_couvre_le_canevas_entier(self):
        built = page(visual("v1", "CA"))
        built.canvas_width, built.canvas_height = 1600.0, 900.0
        self.assertEqual(shots([built])[0].area, Rect(0, 0, 1600, 900))

    def test_une_page_sans_visuel_se_capture_quand_meme(self):
        empty = ReportPage(name="page_1", display_name="Accueil")
        self.assertEqual(len(shots([empty])), 1)


class VisualShotsTest(unittest.TestCase):
    def test_une_prise_par_visuel(self):
        plans = plan.build([page(visual("v1", "CA"), visual("v2", "Marge"))])
        taken = [shot.title for shot in plans[0].shots if shot.kind == plan.VISUAL]
        self.assertEqual(taken, ["CA", "Marge"])
        self.assertEqual(plan.count(plans), 3)  # la page, et ses deux visuels

    def test_la_prise_reprend_la_place_declaree(self):
        taken = shots([page(visual("v1", "CA", x=120, y=40, width=500, height=250))], plan.VISUAL)
        self.assertEqual(taken[0].area, Rect(120, 40, 500, 250))

    def test_le_nom_technique_sert_de_cle(self):
        """Renommer un visuel dans Power BI ne doit pas égarer sa capture."""
        self.assertEqual(
            shots([page(visual("abc123", "Titre du jour"))], plan.VISUAL)[0].name, "abc123"
        )

    def test_un_visuel_sans_dimensions_est_decrit_mais_ecarte(self):
        plans = plan.build([page(visual("v1", "CA", width=0, height=0))])
        shot = plans[0].shots[-1]
        self.assertFalse(shot.is_placed)
        self.assertEqual(shot.title, "CA")
        self.assertEqual(plan.count(plans), 1)  # la page seule

    def test_le_canevas_de_la_page_est_celui_du_rapport(self):
        built = page(visual("v1", "CA"))
        built.canvas_width, built.canvas_height = 1600.0, 900.0
        plans = plan.build([built])
        self.assertEqual((plans[0].canvas.width, plans[0].canvas.height), (1600, 900))

    def test_le_rang_de_la_page_suit_le_plan(self):
        """C'est lui qui dit combien d'onglets franchir pour l'atteindre."""
        built = page(visual("v1", "CA"))
        built.order = 3
        self.assertEqual(plan.build([built])[0].order, 3)


class GroupShotsTest(unittest.TestCase):
    """Un groupe se capture d'un tenant, et ses visuels chacun de leur côté."""

    def _page_with_group(self) -> ReportPage:
        group = VisualGroup(id="g1", name="g1", title="Indicateurs")
        group.visuals = [
            visual("v1", "CA", x=0, y=0, width=200, height=100, group="g1"),
            visual("v2", "Marge", x=300, y=150, width=200, height=100, group="g1"),
        ]
        built = ReportPage(name="page_1", display_name="Ventes")
        built.groups = [group]
        built.ungrouped_visuals = [visual("v3", "Détail", x=0, y=400)]
        built.visuals = [*group.visuals, *built.ungrouped_visuals]
        return built

    def test_l_etendue_couvre_tous_les_membres(self):
        """Sans cadre déclaré, l'étendue des visuels tient lieu de cadre."""
        group_shot = shots([self._page_with_group()], plan.GROUP)[0]
        self.assertEqual(group_shot.area, Rect(0, 0, 500, 250))

    def test_le_cadre_declare_prime_sur_l_etendue(self):
        built = self._page_with_group()
        built.groups[0].pos_x, built.groups[0].pos_y = 0.0, 0.0
        built.groups[0].width, built.groups[0].height = 600.0, 400.0
        self.assertEqual(shots([built], plan.GROUP)[0].area, Rect(0, 0, 600, 400))

    def test_les_visuels_du_groupe_ont_aussi_leur_prise(self):
        """Le document les détaille un à un : il leur faut une capture chacun."""
        taken = [shot.title for shot in shots([self._page_with_group()], plan.VISUAL)]
        self.assertEqual(taken, ["CA", "Marge", "Détail"])

    def test_l_ordre_est_la_page_les_groupes_puis_les_visuels(self):
        taken = [shot.kind for shot in shots([self._page_with_group()])]
        self.assertEqual(taken, [plan.PAGE, plan.GROUP] + [plan.VISUAL] * 3)

    def test_les_sous_groupes_comptent_dans_l_etendue(self):
        group = VisualGroup(id="g1", name="g1", title="Indicateurs")
        group.visuals = [visual("v1", "CA", x=0, y=0, width=100, height=100, group="g1")]
        sub = VisualGroup(id="g2", name="g2", title="Détail")
        sub.visuals = [visual("v2", "Marge", x=600, y=400, width=100, height=100, group="g2")]
        group.subgroups = [sub]

        built = ReportPage(name="page_1", display_name="Ventes")
        built.groups = [group]
        self.assertEqual(shots([built], plan.GROUP)[0].area, Rect(0, 0, 700, 500))


class WithoutOrganisationTest(unittest.TestCase):
    """Le plan est aussi calculable sur un rapport tout juste lu."""

    def test_les_visuels_de_la_page_servent_faute_de_mieux(self):
        built = ReportPage(name="page_1", display_name="Ventes")
        built.visuals = [visual("v1", "CA")]
        self.assertEqual(len(shots([built], plan.VISUAL)), 1)

    def test_un_visuel_n_est_jamais_capture_deux_fois(self):
        """`page.visuals` porte les visuels de groupe comme les autres."""
        member = visual("v1", "CA", group="g1")
        group = VisualGroup(id="g1", name="g1", title="Indicateurs")
        group.visuals = [member]

        built = ReportPage(name="page_1", display_name="Ventes")
        built.groups = [group]
        built.visuals = [member]
        built.ungrouped_visuals = []
        self.assertEqual(len(shots([built], plan.VISUAL)), 1)


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
        self.assertEqual(plan.count(plan.only(self.plans)), 5)  # 2 pages, 3 visuels

    def test_le_rang_de_la_page_est_conserve(self):
        """Restreindre le plan ne doit pas égarer le chemin jusqu'à la page."""
        built = page(visual("v1", "CA"), name="p_stock", title="Stocks")
        built.order = 7
        self.assertEqual(plan.only(plan.build([built]), page="stock")[0].order, 7)

    def test_un_filtre_sans_correspondance_ne_garde_rien(self):
        self.assertEqual(plan.only(self.plans, page="absente"), [])


if __name__ == "__main__":
    unittest.main()
