"""Tests des filtres et tris déclarés dans `data:`."""

import unittest

from src.config import DocConfig
from src.generators.filters import filter_pages, filter_tables, filter_visuals, group_measures
from src.models.data_models import DaxMeasure, ModelTable, ReportPage, Visual


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
        groups = group_measures(self.all, {"Marge"}, [], config(measures={}))
        self.assertEqual(sorted(m.name for g in groups for m in g.measures), ["CA", "Marge"])

    def test_regroupement_par_table(self):
        groups = group_measures(self.all, set(), [], config(measures={"scope": "all"}))
        self.assertEqual([g.name for g in groups], ["Ventes"])

    def test_mesures_rattachees_a_leur_table(self):
        tables = [ModelTable(name="Ventes")]
        group_measures(self.all, set(), tables, config(measures={"scope": "all"}))
        self.assertEqual(sorted(m.name for m in tables[0].measures), ["CA", "Marge"])


if __name__ == "__main__":
    unittest.main()
