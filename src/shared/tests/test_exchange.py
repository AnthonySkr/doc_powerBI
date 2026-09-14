"""
Le fichier que les applications se passent.

Ce qui se vérifie ici tient en une phrase : **ce qui entre ressort**. Une
application écrit, la suivante relit dans un autre processus — si un champ se
perd en route, c'est le document qui sera incomplet, sans que rien ne l'ait
signalé.
"""

import json
import os
import shutil
import tempfile
import unittest

from src.shared.exchange import (
    FORMAT_VERSION,
    Exchange,
    ExchangeError,
    consume,
    discard,
    read,
    write,
)
from src.shared.models import (
    CalculatedColumn,
    DaxMeasure,
    DocLink,
    ModelTable,
    PowerBIReport,
    ReportPage,
    TransformationStep,
    Visual,
    VisualElement,
    VisualFilter,
    VisualGroup,
)


def full_report() -> PowerBIReport:
    """Un rapport qui emploie tous les genres de champs du modèle."""
    measure = DaxMeasure(
        name="Marge",
        expression="[CA] - [Coût]",
        table_name="Ventes",
        display_folder="Rentabilité",
        description="Ce qui reste",
        dependent_measures={"CA", "Coût"},
        used_columns={"Ventes[Montant]"},
        used_by_measures={"Taux de marge"},
        usages=[DocLink(text="Synthèse — CA", target="visual:p1:v1")],
    )
    table = ModelTable(
        name="Ventes",
        source='Sql.Database("srv", "db")',
        transformation_steps=[TransformationStep("Source", "Sql.Database(…)", "Sql.Database(…)")],
        calculated_columns=[CalculatedColumn("Année", "YEAR([Date])")],
    )
    visual = Visual(
        id="v1",
        visual_type="clusteredColumnChart",
        title="Évolution du CA",
        name="v1",
        elements=[VisualElement("Ventes.Marge", "Marge", "Mesure", "Y", property_name="Marge")],
        filters=[VisualFilter("Pays", "Inclut", ["France", "Belgique"])],
        has_measures=True,
        pos_x=10.5,
        pos_y=20.25,
        width=600.0,
        height=400.0,
    )
    group = VisualGroup(id="g1", name="g1", title="Indicateurs", visuals=[visual])
    page = ReportPage(
        name="p1",
        display_name="Synthèse",
        canvas_width=1600.0,
        canvas_height=900.0,
        visuals=[visual],
        groups=[group],
        filters=[VisualFilter("Année", "Inclut", ["2025"], measure_name="")],
    )
    return PowerBIReport(
        name="Rapport",
        pages=[page],
        tables=[table],
        all_measures={"Marge": measure},
        measures_used_in_report={"Marge", "CA"},
        undocumented_measures=["Obsolète"],
    )


class RoundTripTest(unittest.TestCase):
    """Écrire puis relire doit rendre exactement ce qui a été écrit."""

    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.directory, ignore_errors=True)
        self.path = os.path.join(self.directory, "1-rapport.json")

    def _roundtrip(self, exchange: Exchange) -> Exchange:
        write(exchange, self.path)
        return read(self.path)

    def test_le_rapport_revient_identique(self):
        original = Exchange(report=full_report(), source="/projets/Rapport.pbip")
        self.assertEqual(self._roundtrip(original).report, original.report)

    def test_les_ensembles_redeviennent_des_ensembles(self):
        """Le JSON ne connaît que des listes : les `set` sont reconstruits."""
        back = self._roundtrip(Exchange(report=full_report()))
        measure = back.report.all_measures["Marge"]
        self.assertEqual(measure.dependent_measures, {"CA", "Coût"})
        self.assertIsInstance(measure.dependent_measures, set)
        self.assertIsInstance(back.report.measures_used_in_report, set)

    def test_les_objets_imbriques_retrouvent_leur_type(self):
        page = self._roundtrip(Exchange(report=full_report())).report.pages[0]
        self.assertIsInstance(page, ReportPage)
        self.assertIsInstance(page.visuals[0], Visual)
        self.assertIsInstance(page.visuals[0].elements[0], VisualElement)
        self.assertIsInstance(page.groups[0], VisualGroup)

    def test_les_proprietes_calculees_marchent_encore(self):
        """Ce ne sont pas des données : elles doivent se recalculer à l'arrivée."""
        report = self._roundtrip(Exchange(report=full_report())).report
        self.assertEqual(report.measures_in_visuals, {"Marge"})
        self.assertEqual(
            report.pages[0].visuals[0].signature, "Y:Marge Pays (Inclut: France, Belgique)"
        )

    def test_les_nombres_gardent_leur_precision(self):
        visual = self._roundtrip(Exchange(report=full_report())).report.pages[0].visuals[0]
        self.assertEqual((visual.pos_x, visual.pos_y), (10.5, 20.25))

    def test_les_captures_traversent(self):
        original = Exchange(report=full_report(), captures={"p1": {"v1": "captures/p1/v1.png"}})
        self.assertEqual(self._roundtrip(original).captures, original.captures)
        self.assertEqual(self._roundtrip(original).capture_of("p1", "v1"), "captures/p1/v1.png")

    def test_une_capture_absente_ne_leve_pas(self):
        self.assertEqual(Exchange(report=full_report()).capture_of("p9", "v9"), "")


class FileTest(unittest.TestCase):
    """Le fichier s'ouvre, se compare, et se supprime quand il a servi."""

    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.directory, ignore_errors=True)
        self.path = os.path.join(self.directory, "1-rapport.json")

    def test_deux_ecritures_donnent_le_meme_fichier(self):
        """Sans cela, `diff` ne dirait plus ce qui a bougé dans le rapport."""
        write(Exchange(report=full_report()), self.path)
        first = self._content()
        write(Exchange(report=full_report()), self.path)
        self.assertEqual(self._content(), first)

    def _content(self) -> str:
        with open(self.path, encoding="utf-8") as f:
            return f.read()

    def test_le_fichier_est_du_json_lisible(self):
        write(Exchange(report=full_report(), source="/projets/Rapport.pbip"), self.path)
        with open(self.path, encoding="utf-8") as f:
            raw = json.load(f)
        self.assertEqual(raw["source"], "/projets/Rapport.pbip")
        self.assertEqual(raw["report"]["name"], "Rapport")

    def test_les_dossiers_manquants_sont_crees(self):
        deep = os.path.join(self.directory, ".echange", "1-rapport.json")
        write(Exchange(report=full_report()), deep)
        self.assertTrue(os.path.isfile(deep))

    def test_consommer_lit_puis_supprime(self):
        write(Exchange(report=full_report()), self.path)
        self.assertEqual(consume(self.path).report.name, "Rapport")
        self.assertFalse(os.path.exists(self.path))

    def test_lire_ne_supprime_pas(self):
        write(Exchange(report=full_report()), self.path)
        read(self.path)
        self.assertTrue(os.path.isfile(self.path))

    def test_supprimer_deux_fois_ne_leve_pas(self):
        write(Exchange(report=full_report()), self.path)
        discard(self.path)
        discard(self.path)
        self.assertFalse(os.path.exists(self.path))


class RefusalTest(unittest.TestCase):
    """Ce qu'on ne sait pas interpréter est refusé, pas deviné."""

    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.directory, ignore_errors=True)
        self.path = os.path.join(self.directory, "echange.json")

    def _write_raw(self, payload) -> None:
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(payload, f)

    def test_fichier_absent(self):
        with self.assertRaises(ExchangeError) as raised:
            read(os.path.join(self.directory, "jamais-ecrit.json"))
        self.assertIn("introuvable", str(raised.exception))

    def test_json_casse(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("{ ceci n'est pas du JSON")
        with self.assertRaises(ExchangeError):
            read(self.path)

    def test_version_inattendue(self):
        self._write_raw({"version": FORMAT_VERSION + 1, "report": {"name": "R"}})
        with self.assertRaises(ExchangeError) as raised:
            read(self.path)
        self.assertIn("Relancez l'extraction", str(raised.exception))

    def test_un_champ_ajoute_depuis_ne_bloque_pas(self):
        """Un fichier d'une version antérieure garde les valeurs par défaut."""
        self._write_raw({"version": FORMAT_VERSION, "report": {"name": "Rapport"}})
        exchange = read(self.path)
        self.assertEqual(exchange.report.name, "Rapport")
        self.assertEqual(exchange.report.pages, [])

    def test_un_champ_inconnu_est_ignore(self):
        self._write_raw(
            {"version": FORMAT_VERSION, "report": {"name": "R"}, "inconnu": {"quoi": 1}}
        )
        self.assertEqual(read(self.path).report.name, "R")


if __name__ == "__main__":
    unittest.main()
