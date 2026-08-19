"""
Cycle complet : génération, remaniement libre par l'utilisateur, regénération.

Le contrat vérifié ici : le script réécrit ses données, et ne touche à rien
d'autre — titre reformulé, note ajoutée, capture collée, paragraphes en plus.
"""

import os
import struct
import tempfile
import unittest
import zlib
from copy import deepcopy

from docx import Document
from docx.oxml.ns import qn
from docx.shared import Cm
from docx.text.paragraph import Paragraph

from src import console
from src.config import DocConfig
from src.generators.word import generate_word_documentation
from src.models.data_models import DaxMeasure, MeasureGroup, SemanticModel

_DRAWING = qn("w:drawing")

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


def png(path: str) -> str:
    """Écrit une image PNG minimale mais valide."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    raw = b"".join(b"\x00" + bytes([200, 30, 60] * 4) for _ in range(4))
    with open(path, "wb") as f:
        f.write(
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", 4, 4, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw))
            + chunk(b"IEND", b"")
        )
    return path


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


class MergeCycleTest(unittest.TestCase):
    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.path = os.path.join(self._directory.name, "doc.docx")
        self.template = os.path.join(self._directory.name, "template.docx")
        Document().save(self.template)

    # ── Utilitaires ───────────────────────────────────────────────
    def generate(self, overrides: dict | None = None, **expressions: str):
        raw = {**PLAN, **(overrides or {})}
        raw["document"] = {**raw["document"], "template": self.template}
        with console.silenced():
            return generate_word_documentation(DocConfig(raw), context(**expressions), self.path)

    def texts(self) -> list[str]:
        return [p.text for p in Document(self.path).paragraphs if p.text.strip()]

    def find(self, needle: str):
        document = Document(self.path)
        return document, next(p for p in document.paragraphs if needle in p.text)

    def rewrite(self, needle: str, text: str) -> None:
        """Remplace le texte d'un paragraphe, comme le ferait l'utilisateur."""
        document, paragraph = self.find(needle)
        for run in list(paragraph.runs):
            run._element.getparent().remove(run._element)
        paragraph.add_run(text)
        document.save(self.path)

    def add_after(self, needle: str, text: str) -> None:
        """Insère un paragraphe supplémentaire après un autre."""
        document, paragraph = self.find(needle)
        node = deepcopy(paragraph._p)
        paragraph._p.addnext(node)
        added = Paragraph(node, paragraph._parent)
        for run in list(added.runs):
            run._element.getparent().remove(run._element)
        added.add_run(text)
        document.save(self.path)

    def paste_image(self, needle: str) -> None:
        document, paragraph = self.find(needle)
        for run in list(paragraph.runs):
            run._element.getparent().remove(run._element)
        image = png(os.path.join(self._directory.name, "capture.png"))
        paragraph.add_run().add_picture(image, width=Cm(2))
        document.save(self.path)

    def images(self) -> int:
        document = Document(self.path)
        drawings = document.element.body.findall(f".//{_DRAWING}")
        return sum(
            1
            for drawing in drawings
            for blip in drawing.iter(qn("a:blip"))
            if document.part.related_parts.get(blip.get(qn("r:embed"))) is not None
        )

    def highlight(self, needle: str):
        _, paragraph = self.find(needle)
        colors = {run.font.highlight_color for run in paragraph.runs if run.text.strip()} - {None}
        return next(iter(colors), None)

    # ── Le contrat ────────────────────────────────────────────────
    def test_premiere_generation(self):
        log = self.generate(CA="SUM(Ventes[Montant])")
        self.assertFalse(log.is_update)
        self.assertIn("measure:CA", log.written_ids)

    def test_titre_reformule_conserve(self):
        self.generate(CA="1")
        self.rewrite("CA", "CA — Chiffre d'affaires net")
        self.generate(CA="1")
        self.assertIn("CA — Chiffre d'affaires net", self.texts())

    def test_paragraphe_ajoute_conserve(self):
        self.generate(CA="1")
        self.add_after("[À compléter]", "Note ajoutée à la main.")
        self.generate(CA="1")
        self.assertIn("Note ajoutée à la main.", self.texts())

    def test_zone_a_completer_remplie_conservee(self):
        self.generate(CA="1")
        self.rewrite("[À compléter]", "Somme facturée sur la période.")
        self.generate(CA="1")
        self.assertIn("Somme facturée sur la période.", self.texts())
        self.assertNotIn("[À compléter]", self.texts())

    def test_capture_collee_conservee_avec_son_image(self):
        self.generate(CA="1")
        self.paste_image("[À compléter]")
        self.assertEqual(self.images(), 1)

        self.generate(CA="1")
        self.assertEqual(self.images(), 1)

    def test_donnees_du_script_mises_a_jour(self):
        self.generate(CA="SUM(Ventes[Montant])")
        self.rewrite("[À compléter]", "Explication.")

        self.generate(CA="SUM(Ventes[MontantHT])")

        self.assertIn("SUM(Ventes[MontantHT])", self.texts())
        self.assertNotIn("SUM(Ventes[Montant])", self.texts())
        self.assertIn("Explication.", self.texts())

    def test_texte_signale_quand_la_technique_change(self):
        self.generate(CA="1")
        self.rewrite("[À compléter]", "Explication.")

        self.generate(CA="2")
        self.assertIsNotNone(self.highlight("Explication."))

    def test_signalement_retire_a_la_generation_suivante(self):
        self.generate(CA="1")
        self.rewrite("[À compléter]", "Explication.")
        self.generate(CA="2")
        self.generate(CA="2")
        self.assertIsNone(self.highlight("Explication."))

    def test_titre_jamais_surligne(self):
        self.generate(CA="1")
        self.generate(CA="2")
        self.assertIsNone(self.highlight("CA"))

    def test_document_stable_sur_plusieurs_generations(self):
        self.generate(CA="1")
        self.rewrite("[À compléter]", "Explication.")
        self.generate(CA="1")
        reference = self.texts()

        for _ in range(3):
            self.generate(CA="1")
        self.assertEqual(self.texts(), reference)

    def test_nouvel_element_detecte(self):
        self.generate(CA="1")
        log = self.generate(CA="1", Marge="2")
        self.assertEqual(log.new, ["measure:Marge"])
        self.assertEqual(log.changed, [])

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
        self.rewrite("[À compléter]", "Explication.")

        log = self.generate({"merge": {"enabled": False}}, CA="1")

        self.assertFalse(log.is_update)
        self.assertNotIn("Explication.", self.texts())
        self.assertIn("[À compléter]", self.texts())


if __name__ == "__main__":
    unittest.main()
