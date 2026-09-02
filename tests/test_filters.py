"""Tests des filtres et tris déclarés dans `data:`."""

import unittest

from src import console
from src.config import DocConfig
from src.generators.filters import (
    documentable_titles,
    filter_pages,
    filter_steps,
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
    TransformationStep,
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


class VisualGroupingTest(unittest.TestCase):
    """Répartition des visuels d'une page entre groupes Power BI et isolés."""

    def setUp(self):
        self.page = ReportPage(name="p1", display_name="Accueil")
        self.page.groups = [group("g1", "Ventes", y=0), group("g2", "Marges", y=10)]
        self.page.visuals = [
            visual("v1", "CA", group="g1", y=1),
            visual("v2", "Volume", group="g1", y=2),
            visual("v3", "Marge", group="g2", y=11),
            visual("v4", "Taux", group="g2", y=12),
            visual("v5", "Détail", y=20),
        ]

    def organize(self, **options):
        organize_page(self.page, config(visuals=options))
        return self.page

    def test_visuels_repartis_dans_leurs_groupes(self):
        page = self.organize()
        self.assertEqual([g.title for g in page.groups], ["Ventes", "Marges"])
        self.assertEqual([v.title for v in page.groups[0].visuals], ["CA", "Volume"])
        self.assertEqual([v.title for v in page.groups[1].visuals], ["Marge", "Taux"])
        self.assertEqual([v.title for v in page.ungrouped_visuals], ["Détail"])

    def test_page_visuals_suit_l_ordre_du_document(self):
        page = self.organize()
        self.assertEqual(
            [v.title for v in page.visuals], ["CA", "Volume", "Marge", "Taux", "Détail"]
        )

    def test_legende_du_groupe(self):
        members = self.organize().groups[0].members
        self.assertEqual([m.title for m in members], ["CA", "Volume"])

    def test_visuel_exclu_par_type_absent_du_groupe(self):
        self.page.visuals.append(visual("v6", "Bouton", group="g1", visual_type="image", y=3))
        page = self.organize(exclude_types=["image"])

        # Ni dans la légende, ni dans le détail : un visuel écarté l'est partout.
        self.assertEqual([m.title for m in page.groups[0].members], ["CA", "Volume"])
        self.assertEqual([v.title for v in page.groups[0].visuals], ["CA", "Volume"])

    def test_visuel_exclu_par_titre_absent_du_groupe(self):
        self.page.visuals.append(visual("v6", "Panier", group="g1", y=3))
        page = self.organize(exclude_titles=["volume"])

        self.assertEqual([m.title for m in page.groups[0].members], ["CA", "Panier"])
        self.assertEqual([v.title for v in page.groups[0].visuals], ["CA", "Panier"])

    def test_sous_groupe_rattache_a_son_groupe_racine(self):
        self.page.groups.append(group("g3", "Par mois", parent="g1", y=4))
        self.page.visuals.append(visual("v7", "Janvier", group="g3", y=5))
        page = self.organize()

        self.assertEqual([g.title for g in page.groups], ["Ventes", "Marges"])
        ventes = page.groups[0]
        self.assertEqual([s.title for s in ventes.subgroups], ["Par mois"])
        self.assertIn("Janvier", [v.title for v in ventes.visuals])
        self.assertEqual(ventes.members[-1].group_path, "Par mois")
        self.assertEqual(ventes.members[-1].label, "Par mois › Janvier")

    def test_groupe_sans_visuel_documente_ecarte(self):
        self.page.groups.append(group("g4", "Habillage", y=30))
        self.page.visuals.append(visual("v8", "Fond", group="g4", visual_type="shape", y=31))
        page = self.organize(exclude_types=["shape"])

        self.assertNotIn("Habillage", [g.title for g in page.groups])

    def test_groupe_vide_conserve_sur_demande(self):
        self.page.groups.append(group("g4", "Habillage", y=30))
        page = self.organize(groups={"keep_empty": True})

        self.assertIn("Habillage", [g.title for g in page.groups])

    def test_groupe_a_un_seul_visuel_efface_au_profit_du_visuel(self):
        """Un titre et une légende d'une ligne pour un seul visuel : sans objet."""
        self.page.groups.append(group("g4", "Solitaire", y=30))
        self.page.visuals.append(visual("v6", "Cumul", group="g4", y=31))
        page = self.organize()

        self.assertNotIn("Solitaire", [g.title for g in page.groups])
        # Le visuel n'est pas perdu pour autant : il est documenté seul.
        self.assertIn("Cumul", [v.title for v in page.ungrouped_visuals])
        self.assertIn("Cumul", [v.title for v in page.visuals])

    def test_groupe_a_un_seul_visuel_documente_efface(self):
        """Ce sont les visuels documentés qui comptent, pas ceux du rapport."""
        self.page.visuals.append(visual("v6", "Bouton", group="g2", visual_type="image", y=13))
        page = self.organize(exclude_types=["image"], groups={})
        self.assertEqual([g.title for g in page.groups], ["Ventes", "Marges"])

        self.page.visuals = [v for v in self.page.visuals if v.title != "Taux"]
        page = self.organize(exclude_types=["image"], groups={})
        self.assertEqual([g.title for g in page.groups], ["Ventes"])
        self.assertIn("Marge", [v.title for v in page.ungrouped_visuals])

    def test_sous_groupes_comptes_avec_leur_racine(self):
        """Un visuel dans un sous-groupe compte pour le groupe racine."""
        self.page.groups.append(group("g4", "Solitaire", y=30))
        self.page.groups.append(group("g5", "Sous", parent="g4", y=31))
        self.page.visuals.append(visual("v6", "Cumul", group="g4", y=32))
        self.page.visuals.append(visual("v7", "Détail cumul", group="g5", y=33))
        page = self.organize()

        self.assertIn("Solitaire", [g.title for g in page.groups])

    def test_groupe_a_un_seul_visuel_conserve_sur_demande(self):
        self.page.groups.append(group("g4", "Solitaire", y=30))
        self.page.visuals.append(visual("v6", "Cumul", group="g4", y=31))
        page = self.organize(groups={"keep_single": True})

        self.assertIn("Solitaire", [g.title for g in page.groups])
        self.assertNotIn("Cumul", [v.title for v in page.ungrouped_visuals])

    def test_groupe_inconnu_laisse_le_visuel_isole(self):
        self.page.visuals.append(visual("v9", "Orphelin", group="disparu", y=40))
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
        self.assertEqual(len(page.ungrouped_visuals), 5)
        self.assertEqual(page.ungrouped_visuals, page.visuals)

    def test_page_sans_groupe(self):
        self.page.groups = []
        page = self.organize()

        self.assertEqual(page.groups, [])
        self.assertEqual(
            [v.title for v in page.ungrouped_visuals], ["CA", "Détail", "Marge", "Taux", "Volume"]
        )


class ExcludedByAnswerTest(unittest.TestCase):
    """Visuels et groupes écartés par la réponse donnée au lancement."""

    def setUp(self):
        self.page = ReportPage(name="p1", display_name="Accueil")
        self.page.groups = [group("g0", "Bandeau d'en-tête", y=0), group("g1", "Ventes", y=10)]
        self.page.visuals = [
            visual("v0", "Titre page", group="g0", y=1),
            visual("v1", "Logo", group="g0", y=2),
            visual("v2", "CA", group="g1", y=11),
            visual("v3", "Volume", group="g1", y=12),
            visual("v4", "Détail", y=20),
        ]

    def organize(self, excluded):
        raw = {
            "data": {
                "visuals": {
                    "exclude_titles": "{{ inputs.exclus }}",
                    "groups": {"exclude_titles": "{{ inputs.exclus }}"},
                }
            }
        }
        resolved = DocConfig(raw).resolve_data({"inputs": {"exclus": excluded}})
        organize_page(self.page, resolved)
        return self.page

    def test_groupe_ecarte_avec_tout_son_contenu(self):
        page = self.organize(["Bandeau d'en-tête"])

        self.assertEqual([g.title for g in page.groups], ["Ventes"])
        self.assertEqual([v.title for v in page.visuals], ["CA", "Volume", "Détail"])
        # Les visuels du groupe écarté ne réapparaissent pas hors groupe
        for title in ("Titre page", "Logo"):
            self.assertNotIn(title, [v.title for v in page.ungrouped_visuals])

    def test_visuel_isole_ecarte(self):
        page = self.organize(["Détail"])

        self.assertEqual([v.title for v in page.ungrouped_visuals], [])
        self.assertEqual([g.title for g in page.groups], ["Bandeau d'en-tête", "Ventes"])

    def test_aucune_exclusion(self):
        page = self.organize([])

        self.assertEqual([g.title for g in page.groups], ["Bandeau d'en-tête", "Ventes"])
        self.assertEqual(len(page.visuals), 5)

    def test_expression_non_resolue_n_ecarte_rien(self):
        # Au moment où les questions sont posées, les filtres portent encore
        # leur expression : elle ne doit correspondre à aucun titre.
        organize_page(self.page, config(visuals={"exclude_titles": "{{ inputs.exclus }}"}))
        self.assertEqual(len(self.page.visuals), 5)


class DocumentableTitlesTest(unittest.TestCase):
    """Titres proposés au lancement pour être écartés."""

    def test_groupes_et_visuels_dedoublonnes_et_tries(self):
        pages = [
            ReportPage(name="p1", display_name="Accueil"),
            ReportPage(name="p2", display_name="Détail"),
        ]
        for page in pages:
            page.groups = [group("g0", "Bandeau d'en-tête")]
            page.visuals = [
                visual("v0", "Titre page", group="g0"),
                visual("v1", "Logo", "", "image"),
            ]
        pages[0].visuals.append(visual("v2", "CA"))

        titles = documentable_titles(PowerBIReport(name="R", pages=pages), config(visuals={}))
        self.assertEqual(titles, ["Bandeau d'en-tête", "CA", "Logo", "Titre page"])

    def test_visuels_exclus_par_type_non_proposes(self):
        page = ReportPage(name="p1", display_name="Accueil")
        page.visuals = [visual("v0", "CA"), visual("v1", "Logo", "", "image")]

        titles = documentable_titles(
            PowerBIReport(name="R", pages=[page]), config(visuals={"exclude_types": ["image"]})
        )
        self.assertEqual(titles, ["CA"])


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
