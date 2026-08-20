"""Tests de la lecture du rapport PBIR : projections, filtres, titres."""

import unittest

from src.models.data_models import VisualGroup
from src.parsers.report.fields import field_name, parse_elements, parse_filters
from src.parsers.report.pages import UNTITLED_GROUP, _title, parse_group, parse_visual


def measure_field(entity="Ventes", prop="Chiffre d'affaires"):
    return {"Measure": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}


def column_field(entity="Calendrier", prop="Mois"):
    return {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}


def hierarchy_field(hierarchy="Dates", level="Mois", entity="Calendrier"):
    return {
        "HierarchyLevel": {
            "Level": level,
            "Expression": {
                "Hierarchy": {
                    "Hierarchy": hierarchy,
                    "Expression": {
                        "PropertyVariationSource": {"Expression": {"SourceRef": {"Entity": entity}}}
                    },
                }
            },
        }
    }


class ProjectionTest(unittest.TestCase):
    def _elements(self, projection, role="Values"):
        return parse_elements({"queryState": {role: {"projections": [projection]}}})

    def test_mesure(self):
        element = self._elements(
            {"queryRef": "Ventes.Chiffre d'affaires", "field": measure_field()}
        )[0]
        self.assertEqual(element.type_category, "Mesure")
        self.assertEqual(element.table_name, "Ventes")
        self.assertEqual(element.model_name, "Chiffre d'affaires")
        self.assertEqual(element.role, "Values")

    def test_colonne(self):
        element = self._elements(
            {"queryRef": "Calendrier.Mois", "field": column_field()}, role="Category"
        )[0]
        self.assertEqual(element.type_category, "Colonne")
        self.assertEqual(element.display_name, "Mois")

    def test_hierarchie(self):
        element = self._elements({"queryRef": "Calendrier.Dates.Mois", "field": hierarchy_field()})[
            0
        ]
        self.assertEqual(element.type_category, "Hiérarchie")
        self.assertEqual(element.table_name, "Calendrier")
        self.assertEqual(element.property_name, "Mois")

    def test_alias_du_visuel_sans_effet_sur_le_nom_du_modele(self):
        element = self._elements(
            {"queryRef": "Ventes.Chiffre d'affaires", "displayName": "CA", "field": measure_field()}
        )[0]
        self.assertEqual(element.display_name, "CA")
        self.assertEqual(element.model_name, "Chiffre d'affaires")

    def test_projection_sans_query_ref_ignoree(self):
        self.assertEqual(self._elements({"field": measure_field()}), [])

    def test_champ_inconnu(self):
        element = self._elements({"queryRef": "X.Y", "field": {"Autre": {}}})[0]
        self.assertEqual(element.type_category, "Inconnu")

    def test_query_state_absent(self):
        self.assertEqual(parse_elements({}), [])


class FilterTest(unittest.TestCase):
    def _filter(self, condition, field=None):
        return parse_filters(
            [{"field": field or column_field(prop="Actif"), "filter": {"Where": [condition]}}]
        )

    def test_inclusion(self):
        result = self._filter(
            {"Condition": {"In": {"Values": [[{"Literal": {"Value": "'Oui'"}}]]}}}
        )[0]
        self.assertEqual(result.filter_type, "Inclut")
        self.assertEqual(result.values, ["Oui"])
        self.assertEqual(result.to_string(), "Calendrier.Actif (Inclut: Oui)")

    def test_exclusion(self):
        result = self._filter(
            {
                "Condition": {
                    "Not": {"Expression": {"In": {"Values": [[{"Literal": {"Value": "'Non'"}}]]}}}
                }
            }
        )[0]
        self.assertEqual(result.filter_type, "Exclut")
        self.assertEqual(result.values, ["Non"])

    def test_comparaison(self):
        result = self._filter(
            {
                "Condition": {
                    "Comparison": {
                        "ComparisonKind": "GreaterThan",
                        "Right": {"Literal": {"Value": "100"}},
                    }
                }
            }
        )[0]
        self.assertEqual(result.to_string(), "Calendrier.Actif (GreaterThan 100)")

    def test_filtre_sans_condition_ignore(self):
        self.assertEqual(parse_filters([{"field": column_field(), "filter": {}}]), [])

    def test_liste_vide(self):
        self.assertEqual(parse_filters([]), [])


class FieldNameTest(unittest.TestCase):
    def test_mesure(self):
        self.assertEqual(field_name(measure_field()), "Ventes.Chiffre d'affaires")

    def test_colonne(self):
        self.assertEqual(field_name(column_field()), "Calendrier.Mois")

    def test_hierarchie(self):
        self.assertEqual(field_name(hierarchy_field()), "Dates.Mois")

    def test_champ_inconnu(self):
        self.assertEqual(field_name({}), "Champ inconnu")


class VisualTitleTest(unittest.TestCase):
    def test_titre_saisi(self):
        node = {
            "visualContainerObjects": {
                "title": [{"properties": {"text": {"expr": {"Literal": {"Value": "'CA'"}}}}}]
            }
        }
        self.assertEqual(_title(node), "CA")

    def test_sans_titre(self):
        self.assertIsNone(_title({}))

    def test_titre_calcule_non_litteral(self):
        node = {"visualContainerObjects": {"title": [{"properties": {"text": {"expr": {}}}}]}}
        self.assertIsNone(_title(node))


class VisualGroupParserTest(unittest.TestCase):
    def test_conteneur_de_groupe(self):
        group = parse_group(
            {
                "name": "g1",
                "position": {"x": 10, "y": 20},
                "visualGroup": {"displayName": "Suivi des ventes", "groupMode": "ScaleMode"},
            },
            "dossier",
        )
        self.assertIsInstance(group, VisualGroup)
        self.assertEqual(group.id, "dossier")
        self.assertEqual(group.name, "g1")
        self.assertEqual(group.title, "Suivi des ventes")
        self.assertEqual(group.group_mode, "ScaleMode")
        self.assertEqual((group.pos_x, group.pos_y), (10, 20))

    def test_groupe_sans_nom(self):
        group = parse_group({"visualGroup": {"displayName": "  "}}, "dossier")
        self.assertEqual(group.title, UNTITLED_GROUP)
        self.assertEqual(group.name, "dossier")  # le dossier fait office de nom

    def test_groupe_imbrique(self):
        group = parse_group({"parentGroupName": "g1", "visualGroup": {}}, "g2")
        self.assertEqual(group.parent_group_name, "g1")

    def test_visuel_rattache_a_un_groupe(self):
        visual = parse_visual(
            {"name": "v1", "parentGroupName": "g1", "visual": {"visualType": "card"}}, "dossier"
        )
        self.assertEqual(visual.name, "v1")
        self.assertEqual(visual.parent_group_name, "g1")

    def test_visuel_sans_groupe(self):
        visual = parse_visual({"visual": {"visualType": "card"}}, "dossier")
        self.assertEqual(visual.parent_group_name, "")
        self.assertEqual(visual.name, "dossier")

    def test_conteneur_sans_visuel_ni_groupe(self):
        self.assertIsNone(parse_visual({}, "dossier"))


if __name__ == "__main__":
    unittest.main()
