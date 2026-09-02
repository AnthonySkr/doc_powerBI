"""
Mesures documentées, et mesures laissées de côté.

Le plan livré ne documente que les mesures que le rapport emploie. Ce qui est
écarté doit être nommé en fin d'exécution : une mesure absente du document
sans qu'on sache laquelle est un trou, pas un choix.
"""

import unittest

from src.config import DEFAULT_CONFIG_PATH, DocConfig, load_config
from src.generators.context import build_context
from src.models.data_models import (
    DaxMeasure,
    PowerBIReport,
    ReportPage,
    Visual,
    VisualElement,
    VisualFilter,
)
from src.parsers.dependencies import analyze_dependencies, measures_used_in_report


def measure(name: str, expression: str = "1") -> DaxMeasure:
    return DaxMeasure(name=name, expression=expression, table_name="Ventes")


def shown(name: str) -> VisualElement:
    return VisualElement(
        query_ref=f"Ventes.{name}",
        display_name=name,
        type_category="Mesure",
        role="Values",
        property_name=name,
    )


class UndocumentedMeasureTest(unittest.TestCase):
    def _context(self, all_measures: dict, report: PowerBIReport, config: DocConfig):
        analyze_dependencies(all_measures)
        report.all_measures = all_measures
        report.measures_used_in_report = measures_used_in_report(report, all_measures)
        return build_context(report, all_measures, config, {})

    def _report(self, *, elements=(), filters=()) -> PowerBIReport:
        visual = Visual(
            id="v1", visual_type="card", title="Carte", elements=list(elements), filters=[]
        )
        return PowerBIReport(
            name="Demo",
            pages=[ReportPage("p1", "Page", visuals=[visual], filters=list(filters))],
        )

    def _config(self) -> DocConfig:
        return load_config(DEFAULT_CONFIG_PATH).resolve_data({"inputs": {}})

    def _documented(self, context) -> list[str]:
        return sorted(
            m.name for group in context["model"].tables_with_measures for m in group.measures
        )

    def test_mesure_inutilisee_ecartee_et_nommee(self):
        all_measures = {"CA": measure("CA"), "Jamais": measure("Jamais")}
        context = self._context(all_measures, self._report(elements=[shown("CA")]), self._config())

        self.assertEqual(self._documented(context), ["CA"])
        self.assertEqual(context["report"].undocumented_measures, ["Jamais"])

    def test_mesure_servant_de_filtre_documentee(self):
        """Une mesure qui ne sert qu'à filtrer est employée : elle est documentée."""
        all_measures = {"CA": measure("CA"), "Seuil": measure("Seuil")}
        report = self._report(
            elements=[shown("CA")],
            filters=[
                VisualFilter(
                    field_name="Ventes.Seuil",
                    filter_type="Comparison",
                    values=["0"],
                    operator="GreaterThan",
                    measure_name="Seuil",
                )
            ],
        )
        context = self._context(all_measures, report, self._config())

        self.assertEqual(self._documented(context), ["CA", "Seuil"])
        self.assertEqual(context["report"].undocumented_measures, [])

    def test_dependance_d_une_mesure_affichee_documentee(self):
        all_measures = {"CA": measure("CA"), "Marge": measure("Marge", "DIVIDE([CA], 100)")}
        context = self._context(
            all_measures, self._report(elements=[shown("Marge")]), self._config()
        )

        self.assertEqual(self._documented(context), ["CA", "Marge"])
        self.assertEqual(context["report"].undocumented_measures, [])

    def test_liste_triee_sans_tenir_compte_de_la_casse(self):
        all_measures = {name: measure(name) for name in ("zeta", "Alpha", "beta")}
        context = self._context(all_measures, self._report(), self._config())
        self.assertEqual(context["report"].undocumented_measures, ["Alpha", "beta", "zeta"])

    def test_scope_all_ne_laisse_rien_de_cote(self):
        all_measures = {"CA": measure("CA"), "Jamais": measure("Jamais")}
        config = DocConfig({"data": {"measures": {"scope": "all"}}})
        context = self._context(all_measures, self._report(elements=[shown("CA")]), config)

        self.assertEqual(self._documented(context), ["CA", "Jamais"])
        self.assertEqual(context["report"].undocumented_measures, [])


if __name__ == "__main__":
    unittest.main()
