"""Tables, mesures et étapes Power Query retenues par `data:`."""

import unittest

from core import console
from core.config import DocConfig
from core.models import (
    DaxMeasure,
    ModelTable,
    PowerBIReport,
    ReportPage,
    TransformationStep,
    Visual,
    VisualGroup,
)
from core.selection import organize_page
from report_generator.filters import filter_steps, filter_tables, group_measures
from report_generator.references import index_group_members


def config(**data) -> DocConfig:
    return DocConfig({"data": data})


def step(name, expression="F()") -> TransformationStep:
    return TransformationStep(name=name, expression=expression, raw_expression=expression)


class TableFilterTest(unittest.TestCase):
    def _tables(self):
        return [
            ModelTable(name="Ventes", transformation_steps=[step("Source", "Sql.Database()")]),
            ModelTable(name="Technique", is_hidden=True),
        ]

    def test_tables_masquees_exclues(self):
        kept = filter_tables(self._tables(), config(tables={"exclude_hidden": True}))
        self.assertEqual([t.name for t in kept], ["Ventes"])

    def test_etapes_filtrees_a_la_lecture_des_tables(self):
        kept = filter_tables(
            self._tables(),
            config(tables={"exclude_hidden": True, "steps": {"exclude_names": ["Source"]}}),
        )
        self.assertEqual(kept[0].transformation_steps, [])


class IgnoredSourceTest(unittest.TestCase):
    """Sources qui n'apprennent rien : la table est traitée comme sans source."""

    def _source(self, source, ignored=("{1}",)):
        tables = [ModelTable(name="Indicateurs", source=source)]
        kept = filter_tables(tables, config(tables={"ignore_sources": list(ignored)}))
        return kept[0].source

    def test_source_ignoree_effacee(self):
        self.assertEqual(self._source("{1}"), "")

    def test_comparaison_insensible_aux_espaces(self):
        self.assertEqual(self._source("{ 1 }"), "")

    def test_source_reelle_conservee(self):
        self.assertEqual(self._source('Sql.Database("srv", "db")'), 'Sql.Database("srv", "db")')

    def test_sans_liste_rien_n_est_efface(self):
        self.assertEqual(self._source("{1}", ignored=()), "{1}")


class StepFilterTest(unittest.TestCase):
    """Étapes Power Query retenues dans la synthétisation du traitement."""

    def setUp(self):
        self.steps = [
            step("Source"),
            step("b4d2029b-697d-437b-8c10-138964cd23db"),
            step("576D2754-F120-415F-885F-1DDFF338D8CC"),
            step("Navigation 1"),
            step("Type modifié2"),
            step("Colonnes renommées"),
            step("Colonnes permutées"),
            step("BASE_DOMAINE1", "Table.SelectRows(Source, each [x] > 5)"),
        ]
        self.options = {
            "exclude_names": ["Source"],
            "exclude_prefixes": [
                "Navigation",
                "Type modifié",
                "Colonnes renommées",
                "Colonnes permutées",
            ],
        }

    def test_seules_les_etapes_parlantes_sont_gardees(self):
        kept = filter_steps(self.steps, self.options)
        self.assertEqual([s.name for s in kept], ["BASE_DOMAINE1"])
        self.assertEqual(kept[0].expression, "Table.SelectRows(Source, each [x] > 5)")

    def test_etapes_sans_nom_gardees_sur_demande(self):
        kept = filter_steps(self.steps, {**self.options, "exclude_unnamed": False})
        self.assertEqual(
            [s.name for s in kept],
            [
                "b4d2029b-697d-437b-8c10-138964cd23db",
                "576D2754-F120-415F-885F-1DDFF338D8CC",
                "BASE_DOMAINE1",
            ],
        )

    def test_prefixe_insensible_a_la_casse(self):
        kept = filter_steps([step("NAVIGATION vers la table")], self.options)
        self.assertEqual(kept, [])

    def test_sans_option_rien_n_est_ecarte_hors_noms_generes(self):
        kept = filter_steps([step("Source"), step("Autre")], {})
        self.assertEqual([s.name for s in kept], ["Source", "Autre"])


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


class GroupNumberingTest(unittest.TestCase):
    """Numérotation de la légende — les numéros reportés sur la capture."""

    def setUp(self):
        self.page = ReportPage(name="p1", display_name="Accueil")
        self.page.groups = [group("g1", "Ventes", y=0), group("g2", "Marges", y=10)]
        self.page.visuals = [
            visual("v1", "CA", group="g1", y=1),
            visual("v2", "Volume", group="g1", y=2),
            visual("v3", "Marge", group="g2", y=11),
            visual("v4", "Taux", group="g2", y=12),
        ]
        organize_page(self.page, config(visuals={}))
        self.report = PowerBIReport(name="R", pages=[self.page])

    def numbers(self):
        return [[m.number for m in g.members] for g in self.page.groups]

    def test_numerotation_par_groupe(self):
        index_group_members(self.report, {})
        self.assertEqual(self.numbers(), [["1", "2"], ["1", "2"]])

    def test_numerotation_continue_sur_la_page(self):
        index_group_members(self.report, {"groups": {"numbering": {"scope": "page"}}})
        self.assertEqual(self.numbers(), [["1", "2"], ["3", "4"]])

    def test_gabarit_de_numero(self):
        index_group_members(self.report, {"groups": {"numbering": {"start": 0, "format": "#{n}"}}})
        self.assertEqual(self.numbers(), [["#0", "#1"], ["#0", "#1"]])


if __name__ == "__main__":
    unittest.main()


if __name__ == "__main__":
    unittest.main()
