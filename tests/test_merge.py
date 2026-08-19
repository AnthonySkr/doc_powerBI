"""Tests de la régénération incrémentale : marqueurs, relecture, bilan."""

import os
import tempfile
import unittest

from docx import Document
from docx.oxml.ns import qn

from src.merge import CHANGED, NEW, UNCHANGED, ChangeLog, markers
from src.merge import read_previous
from src.merge.previous import PreviousDocument


class MarkerFormatTest(unittest.TestCase):
    def test_element_aller_retour(self):
        marker = markers.parse(markers.element("measure:Marge", "abc123"))
        self.assertEqual(
            (marker.kind, marker.value, marker.fingerprint), ("elem", "measure:Marge", "abc123")
        )

    def test_identifiant_contenant_des_deux_points(self):
        marker = markers.parse(markers.element("visual:p_ventes:v_ca", "d1"))
        self.assertEqual(marker.value, "visual:p_ventes:v_ca")

    def test_slot_et_fin(self):
        self.assertEqual(
            markers.parse(markers.slot("measure:Marge#notes")).value, "measure:Marge#notes"
        )
        self.assertEqual(markers.parse(markers.slot_end()).kind, "endslot")

    def test_texte_ordinaire_non_reconnu(self):
        self.assertIsNone(markers.parse("Chiffre d'affaires"))
        self.assertIsNone(markers.parse(""))
        self.assertIsNone(markers.parse("pbi::inconnu|x"))

    def test_empreinte_ignore_la_mise_en_forme(self):
        self.assertEqual(
            markers.fingerprint("DIVIDE([A],\n   [B])"), markers.fingerprint("DIVIDE([A], [B])")
        )

    def test_empreinte_distingue_deux_expressions(self):
        self.assertNotEqual(markers.fingerprint("[A] + 1"), markers.fingerprint("[A] + 2"))

    def test_cle_de_zone(self):
        self.assertEqual(markers.slot_key("measure:Marge", "notes"), "measure:Marge#notes")
        self.assertEqual(markers.slot_key("", "source_contenu"), "#source_contenu")


class HiddenMarkerTest(unittest.TestCase):
    def test_marqueur_ecrit_masque(self):
        doc = Document()
        markers.write(doc, markers.element("measure:CA", "d1"))
        run = doc.paragraphs[-1].runs[0]
        self.assertIsNotNone(run._r.rPr.find(qn("w:vanish")))


class ReadPreviousTest(unittest.TestCase):
    def _document(self, placeholder="[À compléter]"):
        doc = Document()
        markers.write(doc, markers.element("measure:Marge", "empreinte1"))
        doc.add_paragraph("Marge")
        markers.write(doc, markers.slot("measure:Marge#notes"))
        doc.add_paragraph("Rapport entre résultat et CA.")
        doc.add_paragraph("Hors taxes.")
        markers.write(doc, markers.slot_end())

        markers.write(doc, markers.element("measure:CA", "empreinte2"))
        markers.write(doc, markers.slot("measure:CA#notes"))
        doc.add_paragraph(placeholder)
        markers.write(doc, markers.slot_end())
        return doc

    def _read(self, doc, ignored=("[À compléter]",)):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "doc.docx")
            doc.save(path)
            return read_previous(path, ignored)

    def test_empreintes_relues(self):
        previous = self._read(self._document())
        self.assertEqual(
            previous.fingerprints, {"measure:Marge": "empreinte1", "measure:CA": "empreinte2"}
        )

    def test_texte_utilisateur_relu(self):
        previous = self._read(self._document())
        self.assertEqual(
            previous.text_for("measure:Marge#notes"),
            ["Rapport entre résultat et CA.", "Hors taxes."],
        )

    def test_zone_non_remplie_ignoree(self):
        self.assertEqual(self._read(self._document()).text_for("measure:CA#notes"), [])

    def test_zone_inconnue(self):
        self.assertEqual(self._read(self._document()).text_for("measure:Inexistante#notes"), [])

    def test_document_absent(self):
        self.assertFalse(read_previous("/introuvable.docx").exists)

    def test_document_sans_marqueur_ignore(self):
        doc = Document()
        doc.add_paragraph("Documentation rédigée à la main")
        self.assertFalse(self._read(doc).exists)


class StatusTest(unittest.TestCase):
    def setUp(self):
        self.previous = PreviousDocument(
            path="doc.docx", fingerprints={"measure:Marge": "d1", "measure:CA": "d2"}
        )

    def test_element_inchange(self):
        self.assertEqual(self.previous.status("measure:Marge", "d1"), UNCHANGED)

    def test_element_modifie(self):
        self.assertEqual(self.previous.status("measure:Marge", "d9"), CHANGED)

    def test_element_nouveau(self):
        self.assertEqual(self.previous.status("measure:Panier", "d3"), NEW)

    def test_premiere_generation_tout_inchange(self):
        self.assertEqual(PreviousDocument().status("measure:Marge", "d1"), UNCHANGED)

    def test_elements_retires(self):
        self.assertEqual(self.previous.removed({"measure:Marge"}), ["measure:CA"])


class ChangeLogTest(unittest.TestCase):
    def _log(self, **kwargs) -> ChangeLog:
        log = ChangeLog(is_update=True)
        for status, names in kwargs.items():
            for name in names:
                log.record(name, {"new": NEW, "changed": CHANGED, "unchanged": UNCHANGED}[status])
        return log

    def test_premiere_generation(self):
        log = ChangeLog(is_update=False)
        log.record("measure:CA", UNCHANGED)
        self.assertIn("Première génération", log.summary())

    def test_aucun_changement(self):
        log = self._log(unchanged=["measure:CA"])
        self.assertFalse(log.has_changes)
        self.assertIn("Aucun changement", log.summary())

    def test_resume_des_changements(self):
        log = self._log(new=["measure:Panier"], changed=["measure:Marge"])
        log.removed = ["visual:p1:v2"]
        summary = log.summary()
        self.assertIn("1 élément(s) ajouté(s)", summary)
        self.assertIn("1 élément(s) modifié(s)", summary)
        self.assertIn("1 élément(s) retiré(s)", summary)

    def test_identifiants_ecrits(self):
        log = self._log(new=["a"], changed=["b"], unchanged=["c"])
        self.assertEqual(log.written_ids, {"a", "b", "c"})

    def test_details(self):
        log = self._log(new=["measure:Panier"])
        log.restored = 3
        details = "\n".join(log.details())
        self.assertIn("measure:Panier", details)
        self.assertIn("3 zone(s)", details)


if __name__ == "__main__":
    unittest.main()
