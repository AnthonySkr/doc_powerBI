"""Tests des dépendances entre mesures DAX."""

import unittest

from src.models.data_models import (
    DaxMeasure,
    PowerBIReport,
    ReportPage,
    Visual,
    VisualElement,
    VisualFilter,
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


def measure_filter(name: str) -> VisualFilter:
    return VisualFilter(
        field_name=f"Ventes.{name}",
        filter_type="Comparison",
        values=["0"],
        operator="GreaterThan",
        measure_name=name,
    )


class UsedAsFilterTest(unittest.TestCase):
    """Filtrer sur une mesure, c'est l'utiliser — à tous les niveaux."""

    def _report(self, *, visual=None, page=None, report=None) -> PowerBIReport:
        card = Visual(
            id="v1",
            visual_type="card",
            title="Carte",
            filters=[measure_filter(visual)] if visual else [],
        )
        return PowerBIReport(
            name="Demo",
            pages=[
                ReportPage(
                    "p1",
                    "Page",
                    visuals=[card],
                    filters=[measure_filter(page)] if page else [],
                )
            ],
            filters=[measure_filter(report)] if report else [],
        )

    def test_filtre_de_visuel(self):
        self.assertEqual(measures_used_in_report(self._report(visual="Seuil"), {}), {"Seuil"})

    def test_filtre_de_page(self):
        self.assertEqual(measures_used_in_report(self._report(page="Seuil"), {}), {"Seuil"})

    def test_filtre_de_rapport(self):
        self.assertEqual(measures_used_in_report(self._report(report="Seuil"), {}), {"Seuil"})

    def test_dependances_du_filtre_suivies(self):
        all_measures = measures(CA="SUM(Ventes[Montant])", Seuil="[CA] * 0.1")
        analyze_dependencies(all_measures)
        self.assertEqual(
            measures_used_in_report(self._report(visual="Seuil"), all_measures), {"Seuil", "CA"}
        )

    def test_filtre_sur_colonne_n_est_pas_une_mesure(self):
        report = PowerBIReport(
            name="Demo",
            pages=[
                ReportPage(
                    "p1",
                    "Page",
                    filters=[
                        VisualFilter(
                            field_name="Calendrier.Annee", filter_type="Inclut", values=["2025"]
                        )
                    ],
                )
            ],
        )
        self.assertEqual(measures_used_in_report(report, {}), set())

    def test_etiquette_de_reference_compte_comme_usage(self):
        """Une mesure qui n'apparaît que dans une étiquette de carte est employée."""
        card = Visual(
            id="v1",
            visual_type="cardVisual",
            title="Carte",
            elements=[
                VisualElement(
                    query_ref="Ventes.Objectif",
                    display_name="Objectif",
                    type_category="Mesure",
                    role="ReferenceLabelValue",
                    property_name="Objectif",
                )
            ],
        )
        report = PowerBIReport(name="Demo", pages=[ReportPage("p1", "Page", visuals=[card])])
        self.assertEqual(measures_used_in_report(report, {}), {"Objectif"})
