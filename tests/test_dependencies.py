"""Tests des dépendances entre mesures DAX."""

import unittest

from src.models.data_models import (
    DaxMeasure,
    PowerBIReport,
    ReportPage,
    Visual,
    VisualElement,
)
from src.parsers.dependencies import analyze_dependencies, measures_used_in_report


def measures(**expressions: str) -> dict[str, DaxMeasure]:
    return {
        name: DaxMeasure(name=name, expression=expression, table_name="Ventes")
        for name, expression in expressions.items()
    }


class DependencyTest(unittest.TestCase):
    def setUp(self):
        self.all = measures(
            CA="SUM(Ventes[Montant])",
            Cout="SUM(Ventes[MontantCout])",
            Resultat="[CA] - [Cout]",
            Marge="DIVIDE([Resultat], [CA])",
            Isolee="1",
        )
        analyze_dependencies(self.all)

    def test_dependances_transitives(self):
        self.assertEqual(self.all["Marge"].dependent_measures, {"Resultat", "CA", "Cout"})

    def test_pas_d_auto_dependance(self):
        self.assertNotIn("Marge", self.all["Marge"].dependent_measures)

    def test_colonnes_transitives(self):
        self.assertEqual(self.all["Marge"].used_columns, {"Montant", "MontantCout"})

    def test_relation_inverse(self):
        self.assertEqual(self.all["Resultat"].used_by_measures, {"Marge"})
        self.assertEqual(self.all["CA"].used_by_measures, {"Resultat", "Marge"})

    def test_mesure_isolee(self):
        self.assertEqual(self.all["Isolee"].dependent_measures, set())
        self.assertEqual(self.all["Isolee"].used_by_measures, set())

    def test_identifiant_homonyme_d_une_mesure_traite_comme_mesure(self):
        """`[X]` désigne la mesure X dès qu'elle existe, même si une colonne
        porte le même nom : c'est la règle de résolution de DAX."""
        all_measures = measures(Montant="SUM(Ventes[Montant])")
        analyze_dependencies(all_measures)
        self.assertEqual(all_measures["Montant"].used_columns, set())

    def test_reference_avec_nom_de_table(self):
        all_measures = measures(CA="1", Total="'Ventes'[CA] + 1")
        analyze_dependencies(all_measures)
        self.assertEqual(all_measures["Total"].dependent_measures, {"CA"})

    def test_cycle_sans_recursion_infinie(self):
        all_measures = measures(A="[B]", B="[A]")
        analyze_dependencies(all_measures)
        self.assertEqual(all_measures["A"].dependent_measures, {"B"})
        self.assertEqual(all_measures["B"].dependent_measures, {"A"})


class UsedInReportTest(unittest.TestCase):
    def _report(self, *properties: str) -> PowerBIReport:
        elements = [
            VisualElement(
                query_ref=f"Ventes.{prop}",
                display_name=prop,
                type_category="Mesure",
                role="Values",
                property_name=prop,
            )
            for prop in properties
        ]
        visual = Visual(id="v1", visual_type="card", title="Carte", elements=elements)
        return PowerBIReport(name="Demo", pages=[ReportPage("p1", "Page", visuals=[visual])])

    def test_mesures_du_visuel_et_leurs_dependances(self):
        all_measures = measures(CA="SUM(Ventes[Montant])", Marge="DIVIDE([CA], 100)")
        analyze_dependencies(all_measures)
        self.assertEqual(
            measures_used_in_report(self._report("Marge"), all_measures), {"Marge", "CA"}
        )

    def test_mesure_absente_du_modele_conservee(self):
        self.assertEqual(measures_used_in_report(self._report("Fantome"), {}), {"Fantome"})

    def test_rapport_sans_mesure(self):
        self.assertEqual(measures_used_in_report(PowerBIReport(name="Vide"), {}), set())
