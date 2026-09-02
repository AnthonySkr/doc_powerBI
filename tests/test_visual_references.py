"""Tests du tableau des références d'un visuel, et du regroupement des hiérarchies."""

import unittest

from src.generators.references import _Counter, build_references
from src.models.data_models import Visual, VisualElement, VisualFilter

# Niveaux tels que Power BI les projette pour une hiérarchie de dates : un
# élément par niveau, dans l'ordre de forage.
DATE_LEVELS = ("Année", "Trimestre", "Mois", "Jour")


def level(name, role="Category", hierarchy="Date", table="Calendrier"):
    return VisualElement(
        query_ref=f"{table}.{hierarchy}.Variation.Date Hierarchy.{name}",
        display_name=f"{hierarchy} {name}",
        type_category="Hiérarchie",
        role=role,
        table_name=table,
        property_name=name,
        hierarchy_name=hierarchy,
    )


def measure(name="Chiffre d'affaires", role="Y"):
    return VisualElement(
        query_ref=f"Ventes.{name}",
        display_name=name,
        type_category="Mesure",
        role=role,
        table_name="Ventes",
        property_name=name,
    )


def column(name="Région", role="Legend"):
    return VisualElement(
        query_ref=f"Ventes.{name}",
        display_name=name,
        type_category="Colonne",
        role=role,
        table_name="Ventes",
        property_name=name,
    )


def references(elements, options=None, filters=None):
    visual = Visual(
        id="v1",
        visual_type="clusteredColumnChart",
        title="Évolution",
        elements=elements,
        filters=filters or [],
    )
    return build_references(visual, options or {}, _Counter(1))


class HierarchyGroupingTest(unittest.TestCase):
    def test_niveaux_de_dates_reunis_en_une_reference(self):
        result = references([level(name) for name in ("Année", "Trimestre", "Mois")])

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].kind, "hierarchie")
        self.assertEqual(result[0].value, "Date (Année > Trimestre > Mois)")
        self.assertEqual(result[0].number, "1")

    def test_ordre_de_forage_conserve(self):
        """Les niveaux gardent l'ordre des projections, pas l'ordre alphabétique."""
        result = references([level(name) for name in DATE_LEVELS])
        self.assertEqual(result[0].value, "Date (Année > Trimestre > Mois > Jour)")

    def test_un_seul_niveau_reste_tel_quel(self):
        result = references([level("Mois")])
        self.assertEqual(result[0].value, "Date Mois")

    def test_axes_differents_non_reunis(self):
        result = references([level("Année"), level("Mois", role="Legend")])
        self.assertEqual([ref.value for ref in result], ["Date Année", "Date Mois"])

    def test_hierarchies_differentes_non_reunies(self):
        result = references(
            [
                level("Année"),
                level("Mois"),
                level("Catégorie", hierarchy="Produit", table="Produits"),
                level("Sous-catégorie", hierarchy="Produit", table="Produits"),
            ]
        )
        self.assertEqual(
            sorted(ref.value for ref in result),
            ["Date (Année > Mois)", "Produit (Catégorie > Sous-catégorie)"],
        )

    def test_meme_hierarchie_sur_deux_tables_non_reunie(self):
        result = references([level("Année"), level("Année", table="Budget")])
        self.assertEqual(len(result), 2)

    def test_mesures_et_colonnes_intactes(self):
        result = references([measure(), column(), level("Année"), level("Mois")])

        self.assertEqual(
            [(ref.kind, ref.value) for ref in result],
            [
                ("mesure", "Chiffre d'affaires"),
                ("colonne", "Région"),
                ("hierarchie", "Date (Année > Mois)"),
            ],
        )

    def test_numerotation_continue_apres_regroupement(self):
        result = references(
            [measure(), level("Année"), level("Mois")],
            filters=[VisualFilter(field_name="Ventes.Actif", filter_type="Inclut", values=["Oui"])],
        )
        self.assertEqual([ref.number for ref in result], ["1", "2", "3"])

    def test_format_et_separateur_configurables(self):
        result = references(
            [level("Année"), level("Mois")],
            options={"hierarchies": {"format": "{hierarchy} [{levels}]", "separator": ", "}},
        )
        self.assertEqual(result[0].value, "Date [Année, Mois]")

    def test_regroupement_desactivable(self):
        result = references(
            [level("Année"), level("Mois")], options={"hierarchies": {"group": False}}
        )
        self.assertEqual([ref.value for ref in result], ["Date Année", "Date Mois"])

    def test_libelle_reprend_le_nom_compose(self):
        result = references(
            [level("Année"), level("Mois")],
            options={
                "labels": {"hierarchie": "{role} : {display}"},
                "roles": {"Category": "Axe X"},
            },
        )
        self.assertEqual(result[0].label, "Axe X : Date (Année > Mois)")

    def test_hierarchie_sans_nom_non_reunie(self):
        """Sans hiérarchie identifiée, chaque niveau garde sa ligne."""
        orphan = level("Année")
        orphan.hierarchy_name = ""
        other = level("Mois")
        other.hierarchy_name = ""
        self.assertEqual(len(references([orphan, other])), 2)


if __name__ == "__main__":
    unittest.main()
