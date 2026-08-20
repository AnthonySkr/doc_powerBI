"""Tests des filtres et tris déclarés dans `data:`."""

import unittest

from src import console
from src.config import DocConfig
from src.generators.filters import (
    filter_pages,
    filter_tables,
    filter_visuals,
    group_measures,
    organize_page,
)
from src.generators.references import index_group_members
from src.models.data_models import (
    DaxMeasure,
    ModelTable,
    PowerBIReport,
    ReportPage,
    Visual,
    VisualGroup,
)


def config(**data) -> DocConfig:
    return DocConfig({"data": data})


class PageFilterTest(unittest.TestCase):
    def setUp(self):
        self.pages = [
            ReportPage(name="p2", display_name="Détail", order=2),
            ReportPage(name="p1", display_name="Accueil", order=1),
            ReportPage(name="p3", display_name="Technique", order=3, is_hidden=True),
        ]

    def test_tri_par_ordre_du_rapport(self):
        kept = filter_pages(self.pages, config(pages={"exclude_hidden": False}))
        self.assertEqual([p.display_name for p in kept], ["Accueil", "Détail", "Technique"])

    def test_tri_par_nom(self):
        kept = filter_pages(self.pages, config(pages={"exclude_hidden": False, "sort_by": "name"}))
        self.assertEqual([p.display_name for p in kept], ["Accueil", "Détail", "Technique"])

    def test_pages_masquees_exclues(self):
        kept = filter_pages(self.pages, config(pages={"exclude_hidden": True}))
        self.assertEqual([p.display_name for p in kept], ["Accueil", "Détail"])

    def test_exclusion_par_nom(self):
        kept = filter_pages(
            self.pages, config(pages={"exclude_hidden": False, "exclude_names": ["détail"]})
        )
        self.assertEqual([p.display_name for p in kept], ["Accueil", "Technique"])


class VisualFilterTest(unittest.TestCase):
    def setUp(self):
        self.visuals = [
            Visual(id="v1", visual_type="card", title="CA", has_measures=True, pos_x=5, pos_y=1),
            Visual(id="v2", visual_type="image", title="Logo", pos_x=0, pos_y=0),
            Visual(id="v3", visual_type="barChart", title="Marge", pos_x=0, pos_y=2),
        ]

    def test_tri_par_titre(self):
        kept = filter_visuals(self.visuals, config(visuals={}))
        self.assertEqual([v.title for v in kept], ["CA", "Logo", "Marge"])

    def test_tri_par_position(self):
        kept = filter_visuals(self.visuals, config(visuals={"sort_by": "position"}))
        self.assertEqual([v.title for v in kept], ["Logo", "CA", "Marge"])

    def test_exclusion_par_type(self):
        kept = filter_visuals(self.visuals, config(visuals={"exclude_types": ["image"]}))
        self.assertEqual([v.title for v in kept], ["CA", "Marge"])

    def test_seulement_avec_mesures(self):
        kept = filter_visuals(self.visuals, config(visuals={"only_with_measures": True}))
        self.assertEqual([v.title for v in kept], ["CA"])


class TableFilterTest(unittest.TestCase):
    def _tables(self):
        return [
            ModelTable(
                name="Ventes",
                transformation_steps=[{"name": "Source", "expression": "Sql.Database()"}],
            ),
            ModelTable(name="Technique", is_hidden=True),
        ]

    def test_tables_masquees_exclues(self):
        kept = filter_tables(self._tables(), config(tables={"exclude_hidden": True}))
        self.assertEqual([t.name for t in kept], ["Ventes"])

    def test_etapes_mises_en_forme(self):
        kept = filter_tables(
            self._tables(),
            config(tables={"exclude_hidden": True, "step_format": "{name} — {expression}"}),
        )
        self.assertEqual(kept[0].transformation_steps, ["Source — Sql.Database()"])


class MeasureGroupTest(unittest.TestCase):
    def setUp(self):
        self.all = {
            "CA": DaxMeasure(name="CA", expression="1", table_name="Ventes"),
            "Marge": DaxMeasure(
                name="Marge", expression="[CA]", table_name="Ventes", dependent_measures={"CA"}
            ),
            "Technique": DaxMeasure(
                name="Technique", expression="1", table_name="Calendrier", is_hidden=True
            ),
        }

    def test_perimetre_limite_au_rapport(self):
        groups = group_measures(self.all, {"CA"}, [], config(measures={}))
        self.assertEqual([m.name for g in groups for m in g.measures], ["CA"])

    def test_perimetre_complet(self):
        groups = group_measures(self.all, set(), [], config(measures={"scope": "all"}))
        self.assertEqual(sorted(m.name for g in groups for m in g.measures), ["CA", "Marge"])

    def test_mesure_masquee_incluse_sur_demande(self):
        groups = group_measures(
            self.all, set(), [], config(measures={"scope": "all", "include_hidden": True})
        )
        self.assertIn("Technique", [m.name for g in groups for m in g.measures])

    def test_dependance_ajoutee_pour_ne_pas_casser_les_liens(self):
        with console.silenced():
            groups = group_measures(self.all, {"Marge"}, [], config(measures={}))
        self.assertEqual(sorted(m.name for g in groups for m in g.measures), ["CA", "Marge"])

    def test_regroupement_par_table(self):
        groups = group_measures(self.all, set(), [], config(measures={"scope": "all"}))
        self.assertEqual([g.name for g in groups], ["Ventes"])

    def test_mesures_rattachees_a_leur_table(self):
        tables = [ModelTable(name="Ventes")]
        group_measures(self.all, set(), tables, config(measures={"scope": "all"}))
        self.assertEqual(sorted(m.name for m in tables[0].measures), ["CA", "Marge"])


def visual(vid, title, group="", visual_type="card", x=0.0, y=0.0) -> Visual:
    return Visual(
        id=vid,
        visual_type=visual_type,
        title=title,
        parent_group_name=group,
        name=vid,
        pos_x=x,
        pos_y=y,
    )


def group(name, title, parent="", x=0.0, y=0.0) -> VisualGroup:
    return VisualGroup(id=name, name=name, title=title, parent_group_name=parent, pos_x=x, pos_y=y)


class VisualGroupingTest(unittest.TestCase):
    """Répartition des visuels d'une page entre groupes Power BI et isolés."""

    def setUp(self):
        self.page = ReportPage(name="p1", display_name="Accueil")
        self.page.groups = [group("g1", "Ventes", y=0), group("g2", "Marges", y=10)]
        self.page.visuals = [
            visual("v1", "CA", group="g1", y=1),
            visual("v2", "Volume", group="g1", y=2),
            visual("v3", "Marge", group="g2", y=11),
            visual("v4", "Détail", y=20),
        ]

    def organize(self, **options):
        organize_page(self.page, config(visuals=options))
        return self.page

    def test_visuels_repartis_dans_leurs_groupes(self):
        page = self.organize()
        self.assertEqual([g.title for g in page.groups], ["Ventes", "Marges"])
        self.assertEqual([v.title for v in page.groups[0].visuals], ["CA", "Volume"])
        self.assertEqual([v.title for v in page.groups[1].visuals], ["Marge"])
        self.assertEqual([v.title for v in page.ungrouped_visuals], ["Détail"])

    def test_page_visuals_suit_l_ordre_du_document(self):
        page = self.organize()
        self.assertEqual([v.title for v in page.visuals], ["CA", "Volume", "Marge", "Détail"])

    def test_legende_du_groupe(self):
        members = self.organize().groups[0].members
        self.assertEqual([m.title for m in members], ["CA", "Volume"])
        self.assertTrue(all(m.documented for m in members))

    def test_legende_contient_les_visuels_exclus(self):
        self.page.visuals.append(visual("v5", "Bouton", group="g1", visual_type="image", y=3))
        page = self.organize(exclude_types=["image"])

        members = page.groups[0].members
        self.assertEqual([m.title for m in members], ["CA", "Volume", "Bouton"])
        self.assertEqual([m.documented for m in members], [True, True, False])
        # ... mais le visuel exclu n'a pas de partie détaillée
        self.assertEqual([v.title for v in page.groups[0].visuals], ["CA", "Volume"])

    def test_sous_groupe_rattache_a_son_groupe_racine(self):
        self.page.groups.append(group("g3", "Par mois", parent="g1", y=4))
        self.page.visuals.append(visual("v6", "Janvier", group="g3", y=5))
        page = self.organize()

        self.assertEqual([g.title for g in page.groups], ["Ventes", "Marges"])
        ventes = page.groups[0]
        self.assertEqual([s.title for s in ventes.subgroups], ["Par mois"])
        self.assertIn("Janvier", [v.title for v in ventes.visuals])
        self.assertEqual(ventes.members[-1].group_path, "Par mois")
        self.assertEqual(ventes.members[-1].label, "Par mois › Janvier")

    def test_groupe_sans_visuel_documente_ecarte(self):
        self.page.groups.append(group("g4", "Habillage", y=30))
        self.page.visuals.append(visual("v7", "Fond", group="g4", visual_type="shape", y=31))
        page = self.organize(exclude_types=["shape"])

        self.assertNotIn("Habillage", [g.title for g in page.groups])

    def test_groupe_vide_conserve_sur_demande(self):
        self.page.groups.append(group("g4", "Habillage", y=30))
        page = self.organize(groups={"keep_empty": True})

        self.assertIn("Habillage", [g.title for g in page.groups])

    def test_groupe_inconnu_laisse_le_visuel_isole(self):
        self.page.visuals.append(visual("v8", "Orphelin", group="disparu", y=40))
        page = self.organize()

        self.assertIn("Orphelin", [v.title for v in page.ungrouped_visuals])

    def test_groupes_qui_se_contiennent_ne_perdent_aucun_visuel(self):
        # Deux groupes qui se déclarent parents l'un de l'autre : Power BI ne
        # produit pas cela, mais le visuel reste documenté quoi qu'il arrive.
        self.page.groups = [group("a", "A", parent="b"), group("b", "B", parent="a")]
        self.page.visuals = [visual("v1", "CA", group="a")]
        page = self.organize()

        self.assertEqual([v.title for v in page.visuals], ["CA"])

    def test_tri_des_groupes_par_titre(self):
        page = self.organize(groups={"sort_by": "title"})
        self.assertEqual([g.title for g in page.groups], ["Marges", "Ventes"])

    def test_groupes_desactives(self):
        page = self.organize(groups={"enabled": False})

        self.assertEqual(page.groups, [])
        self.assertEqual(len(page.ungrouped_visuals), 4)
        self.assertEqual(page.ungrouped_visuals, page.visuals)

    def test_page_sans_groupe(self):
        self.page.groups = []
        page = self.organize()

        self.assertEqual(page.groups, [])
        self.assertEqual(
            [v.title for v in page.ungrouped_visuals], ["CA", "Détail", "Marge", "Volume"]
        )


class GroupNumberingTest(unittest.TestCase):
    """Numérotation de la légende — les numéros reportés sur la capture."""

    def setUp(self):
        self.page = ReportPage(name="p1", display_name="Accueil")
        self.page.groups = [group("g1", "Ventes", y=0), group("g2", "Marges", y=10)]
        self.page.visuals = [
            visual("v1", "CA", group="g1", y=1),
            visual("v2", "Volume", group="g1", y=2),
            visual("v3", "Marge", group="g2", y=11),
        ]
        organize_page(self.page, config(visuals={}))
        self.report = PowerBIReport(name="R", pages=[self.page])

    def numbers(self):
        return [[m.number for m in g.members] for g in self.page.groups]

    def test_numerotation_par_groupe(self):
        index_group_members(self.report, {})
        self.assertEqual(self.numbers(), [["1", "2"], ["1"]])

    def test_numerotation_continue_sur_la_page(self):
        index_group_members(self.report, {"groups": {"numbering": {"scope": "page"}}})
        self.assertEqual(self.numbers(), [["1", "2"], ["3"]])

    def test_gabarit_de_numero(self):
        index_group_members(self.report, {"groups": {"numbering": {"start": 0, "format": "#{n}"}}})
        self.assertEqual(self.numbers(), [["#0", "#1"], ["#0"]])


if __name__ == "__main__":
    unittest.main()
