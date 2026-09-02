"""Tests de la lecture du rapport PBIR : projections, filtres, titres."""

import json
import os
import tempfile
import unittest

from src import console
from src.models.data_models import VisualGroup
from src.parsers.report import parse_report
from src.parsers.report.fields import (
    field_name,
    parse_elements,
    parse_filters,
    parse_reference_labels,
)
from src.parsers.report.pages import UNTITLED_GROUP, _title, parse_group, parse_visual


def measure_field(entity="Ventes", prop="Chiffre d'affaires"):
    return {"Measure": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}


def column_field(entity="Calendrier", prop="Mois"):
    return {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}


def hierarchy_field(hierarchy="Dates", level="Mois", entity="Calendrier", source="Date"):
    """Hiérarchie de dates : engendrée par une colonne (`PropertyVariationSource`)."""
    return {
        "HierarchyLevel": {
            "Level": level,
            "Expression": {
                "Hierarchy": {
                    "Hierarchy": hierarchy,
                    "Expression": {
                        "PropertyVariationSource": {
                            "Property": source,
                            "Expression": {"SourceRef": {"Entity": entity}},
                        }
                    },
                }
            },
        }
    }


def model_hierarchy_field(hierarchy="Hiérarchie Produit", level="Catégorie", entity="Produits"):
    """Hiérarchie déclarée dans le modèle : rattachée directement à sa table."""
    return {
        "HierarchyLevel": {
            "Level": level,
            "Expression": {
                "Hierarchy": {
                    "Hierarchy": hierarchy,
                    "Expression": {"SourceRef": {"Entity": entity}},
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
        # Une hiérarchie de dates est nommée d'après sa colonne d'origine,
        # comme Power BI l'affiche — pas d'après la hiérarchie technique.
        self.assertEqual(element.hierarchy_name, "Date")

    def test_hierarchie_du_modele(self):
        element = self._elements(
            {"queryRef": "Produits.Hiérarchie Produit.Catégorie", "field": model_hierarchy_field()}
        )[0]
        self.assertEqual(element.table_name, "Produits")
        self.assertEqual(element.hierarchy_name, "Hiérarchie Produit")

    def test_colonne_sans_hierarchie(self):
        element = self._elements({"queryRef": "Calendrier.Mois", "field": column_field()})[0]
        self.assertEqual(element.hierarchy_name, "")

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


def reference_label(**properties) -> dict:
    """Objet d'étiquette de référence tel que le porte une carte."""
    return {"objects": {"referenceLabels": [{"properties": properties}]}}


class ReferenceLabelTest(unittest.TestCase):
    """Étiquettes de référence d'une carte : hors requête, donc lues à part."""

    def test_valeur_de_l_etiquette(self):
        element = parse_reference_labels(
            reference_label(valueSource={"expr": measure_field(prop="Objectif")})
        )[0]
        self.assertEqual(element.type_category, "Mesure")
        self.assertEqual(element.model_name, "Objectif")
        self.assertEqual(element.table_name, "Ventes")
        self.assertEqual(element.role, "ReferenceLabelValue")

    def test_detail_de_l_etiquette(self):
        element = parse_reference_labels(
            reference_label(detailSource={"expr": measure_field(prop="Écart")})
        )[0]
        self.assertEqual(element.role, "ReferenceLabelDetail")
        self.assertEqual(element.model_name, "Écart")

    def test_valeur_et_detail_ensemble(self):
        elements = parse_reference_labels(
            reference_label(
                titleText={"expr": {"Literal": {"Value": "'Objectif'"}}},
                valueSource={"expr": measure_field(prop="Objectif")},
                detailSource={"expr": measure_field(prop="Écart")},
            )
        )
        self.assertEqual(
            [(e.role, e.model_name) for e in elements],
            [("ReferenceLabelValue", "Objectif"), ("ReferenceLabelDetail", "Écart")],
        )

    def test_nom_de_propriete_indifferent(self):
        """Power BI a renommé ces propriétés d'une version à l'autre."""
        elements = parse_reference_labels(
            reference_label(valueText={"expr": measure_field(prop="Objectif")})
        )
        self.assertEqual([e.model_name for e in elements], ["Objectif"])

    def test_colonne_en_etiquette(self):
        element = parse_reference_labels(
            reference_label(valueSource={"expr": column_field(prop="Mois")})
        )[0]
        self.assertEqual(element.type_category, "Colonne")
        self.assertEqual(element.table_name, "Calendrier")

    def test_objet_declare_au_singulier(self):
        elements = parse_reference_labels(
            {"objects": {"referenceLabel": [{"properties": {"v": {"expr": measure_field()}}}]}}
        )
        self.assertEqual(len(elements), 1)

    def test_titre_litteral_ignore(self):
        """Un titre saisi à la main n'est pas un champ."""
        self.assertEqual(
            parse_reference_labels(
                reference_label(titleText={"expr": {"Literal": {"Value": "'Objectif'"}}})
            ),
            [],
        )

    def test_autres_objets_ignores(self):
        """La mise en forme conditionnelle référence des mesures : pas des champs affichés."""
        objects = {"objects": {"dataColors": [{"properties": {"fill": {"expr": measure_field()}}}]}}
        self.assertEqual(parse_reference_labels(objects), [])

    def test_visuel_sans_objets(self):
        self.assertEqual(parse_reference_labels({}), [])


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


class ReportFilterTest(unittest.TestCase):
    """Filtres posés sur le rapport entier (« Filtres sur toutes les pages »)."""

    def _report(self, relative: str) -> list:
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, relative)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "filterConfig": {
                            "filters": [
                                {
                                    "field": measure_field(prop="Seuil"),
                                    "filter": {
                                        "Where": [
                                            {
                                                "Condition": {
                                                    "Comparison": {
                                                        "ComparisonKind": "GreaterThan",
                                                        "Right": {"Literal": {"Value": "0"}},
                                                    }
                                                }
                                            }
                                        ]
                                    },
                                }
                            ]
                        }
                    },
                    f,
                )
            with console.silenced():
                return parse_report(directory).filters

    def test_filtre_lu_depuis_definition(self):
        filters = self._report(os.path.join("definition", "report.json"))
        self.assertEqual([item.measure_name for item in filters], ["Seuil"])

    def test_filtre_lu_depuis_la_racine(self):
        """Les projets PBIR antérieurs posent le fichier à la racine du .Report."""
        filters = self._report("report.json")
        self.assertEqual([item.measure_name for item in filters], ["Seuil"])

    def test_rapport_sans_fichier_de_filtres(self):
        with tempfile.TemporaryDirectory() as directory, console.silenced():
            self.assertEqual(parse_report(directory).filters, [])
