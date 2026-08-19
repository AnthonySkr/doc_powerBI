"""
Test de bout en bout du cycle : génération, rédaction, regénération.

Le plan et le template sont réduits au minimum : ce qui est vérifié ici est la
fusion (reprise des textes, détection des changements), pas la mise en page.
"""

import os
import tempfile
import unittest

from docx import Document

from src import console
from src.config import DocConfig
from src.generators.word import generate_word_documentation
from src.merge import markers
from src.models.data_models import DaxMeasure, MeasureGroup, SemanticModel

PLAN = {
    "document": {"template": "", "cover": {}, "properties": {}},
    "rendering": {"page_break_before_heading_1": False, "links": {"enabled": False}},
    "sections": [
        {
            "id": "mesures",
            "title": "Mesures",
            "level": 1,
            "blocks": [
                {
                    "type": "loop",
                    "over": "model.tables_with_measures",
                    "item": "groupe",
                    "section": {
                        "title": "{{ groupe.name }}",
                        "level": 2,
                        "blocks": [
                            {
                                "type": "loop",
                                "over": "groupe.measures",
                                "item": "measure",
                                "section": {
                                    "title": "{{ measure.name }}",
                                    "level": 3,
                                    "bookmark": "measure:{{ measure.name }}",
                                    "fingerprint": "{{ measure.expression }}",
                                    "blocks": [
                                        {
                                            "type": "property",
                                            "id": "code",
                                            "label": "Code DAX",
                                            "value": "{{ measure.expression }}",
                                        },
                                        {"type": "user_fill", "id": "commentaire"},
                                    ],
                                },
                            }
                        ],
                    },
                }
            ],
        }
    ],
}


def context(**expressions: str) -> dict:
    measures = [
        DaxMeasure(name=name, expression=expression, table_name="Ventes")
        for name, expression in expressions.items()
    ]
    return {
        "model": SemanticModel(
            tables_with_measures=[MeasureGroup(name="Ventes", measures=measures)]
        ),
        "report": None,
        "inputs": {},
        "styles": {},
    }


def write_comment(path: str, key: str, text: str) -> None:
    """Simule la rédaction de l'utilisateur dans Word."""
    doc = Document(path)
    slot = None
    for paragraph in doc.paragraphs:
        marker = markers.parse(paragraph.text)
        if marker and marker.kind == "slot":
            slot = marker.value
        elif marker and marker.kind == "endslot":
            slot = None
        elif slot == key and paragraph.text.strip():
            for run in list(paragraph.runs):
                run._element.getparent().remove(run._element)
            paragraph.add_run(text)
            break
    doc.save(path)


def comment(path: str, key: str) -> str:
    doc = Document(path)
    slot, texts = None, []
    for paragraph in doc.paragraphs:
        marker = markers.parse(paragraph.text)
        if marker and marker.kind == "slot":
            slot = marker.value
        elif marker and marker.kind == "endslot":
            slot = None
        elif slot == key and paragraph.text.strip():
            texts.append(paragraph.text.strip())
    return "\n".join(texts)


def highlight(path: str, key: str):
    doc = Document(path)
    slot = None
    for paragraph in doc.paragraphs:
        marker = markers.parse(paragraph.text)
        if marker and marker.kind == "slot":
            slot = marker.value
        elif marker and marker.kind == "endslot":
            slot = None
        elif slot == key:
            for run in paragraph.runs:
                if run.text.strip():
                    return run.font.highlight_color
    return None


class MergeCycleTest(unittest.TestCase):
    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.path = os.path.join(self._directory.name, "doc.docx")

        # Un template vierge suffit : le plan écrit à la suite.
        self.template = os.path.join(self._directory.name, "template.docx")
        Document().save(self.template)

    def generate(self, plan_overrides: dict | None = None, **expressions: str):
        raw = {**PLAN, **(plan_overrides or {})}
        raw["document"] = {**raw["document"], "template": self.template}
        with console.silenced():
            return generate_word_documentation(DocConfig(raw), context(**expressions), self.path)

    def test_premiere_generation(self):
        log = self.generate(CA="SUM(Ventes[Montant])")
        self.assertFalse(log.is_update)
        self.assertEqual(log.unchanged, ["measure:CA"])
        self.assertTrue(os.path.isfile(self.path))

    def test_texte_utilisateur_conserve(self):
        self.generate(CA="SUM(Ventes[Montant])")
        write_comment(self.path, "measure:CA#commentaire", "Somme facturée.")

        self.generate(CA="SUM(Ventes[Montant])")
        self.assertEqual(comment(self.path, "measure:CA#commentaire"), "Somme facturée.")

    def test_dax_mis_a_jour_et_texte_signale(self):
        self.generate(CA="SUM(Ventes[Montant])")
        write_comment(self.path, "measure:CA#commentaire", "Somme facturée.")

        log = self.generate(CA="SUM(Ventes[MontantHT])")

        self.assertEqual(log.changed, ["measure:CA"])
        self.assertEqual(comment(self.path, "measure:CA#commentaire"), "Somme facturée.")
        self.assertIn("MontantHT", "\n".join(p.text for p in Document(self.path).paragraphs))
        self.assertIsNotNone(highlight(self.path, "measure:CA#commentaire"))

    def test_texte_non_signale_si_rien_n_a_change(self):
        self.generate(CA="SUM(Ventes[Montant])")
        write_comment(self.path, "measure:CA#commentaire", "Somme facturée.")
        self.generate(CA="SUM(Ventes[Montant])")
        self.assertIsNone(highlight(self.path, "measure:CA#commentaire"))

    def test_nouvel_element_detecte(self):
        self.generate(CA="1")
        log = self.generate(CA="1", Marge="2")
        self.assertEqual(log.new, ["measure:Marge"])
        self.assertEqual(log.unchanged, ["measure:CA"])

    def test_element_retire_signale(self):
        self.generate(CA="1", Marge="2")
        log = self.generate(CA="1")
        self.assertEqual(log.removed, ["measure:Marge"])

    def test_version_precedente_archivee(self):
        self.generate(CA="1")
        self.generate(CA="2")
        versions = os.listdir(os.path.join(self._directory.name, ".versions"))
        self.assertEqual(len(versions), 1)

    def test_fusion_desactivable(self):
        self.generate(CA="1")
        write_comment(self.path, "measure:CA#commentaire", "Somme facturée.")

        log = self.generate({"merge": {"enabled": False}}, CA="1")

        self.assertFalse(log.is_update)
        self.assertNotIn("Somme facturée", comment(self.path, "measure:CA#commentaire"))


if __name__ == "__main__":
    unittest.main()
