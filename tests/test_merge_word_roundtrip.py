"""
Ce que Word change tout seul ne doit pas passer pour une retouche.

L'empreinte relevée à l'écriture est le seul témoin de ce que le script avait
posé, et elle ne survit pas à tout : en enregistrant, Word recoupe les runs,
perd une espace de bord, réécrit un lien interne sous forme de champ. Le
contenu affiché, lui, n'a pas bougé — personne n'a touché au document.

Sans garde-fou, la fusion prenait ces réécritures pour des données du script
remaniées à la main : le code DAX repartait en annexe sous « Contenu non
replacé », à chaque génération et sans que rien ne l'explique.
"""

import copy
import unittest

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from tests.test_merge_cycle import MergeHarness

_RUN = qn("w:r")
_TEXT = qn("w:t")
_HYPERLINK = qn("w:hyperlink")

# Le plan de référence n'écrit pas de liens : ceux-ci sont le cœur du sujet.
_LINKED = {
    "rendering": {
        "page_break_before_heading_1": False,
        "links": {"enabled": True, "auto": {"enabled": True, "in_code": True}},
    }
}


class WordRoundTripTest(MergeHarness):
    """Le document revient de Word remanié dans sa forme, pas dans son contenu."""

    # ── Gestes de Word ────────────────────────────────────────────
    def link_to_field(self) -> None:
        """
        Word réécrit un lien interne sous forme de champ `HYPERLINK`.

        Le libellé du lien devient le résultat du champ : un texte que Word
        n'écrit qu'une fois et ne recalcule jamais.
        """
        document = Document(self.path)
        for link in list(document.element.body.iter(_HYPERLINK)):
            parent = link.getparent()
            rank = list(parent).index(link)
            runs = [copy.deepcopy(run) for run in link if run.tag == _RUN]
            parent.remove(link)
            field = [
                _field_char("begin"),
                _instruction(f' HYPERLINK \\l "{link.get(qn("w:anchor"))}" '),
                _field_char("separate"),
                *runs,
                _field_char("end"),
            ]
            for offset, node in enumerate(field):
                parent.insert(rank + offset, node)
        document.save(self.path)

    def split_runs(self) -> None:
        """
        Word recoupe les runs — le correcteur orthographique en est friand — et
        laisse au passage tomber les espaces de bord des morceaux.
        """
        document = Document(self.path)
        for run in list(document.element.body.iter(_RUN)):
            texts = [node for node in run if node.tag == _TEXT]
            if len(texts) != 1 or not (texts[0].text or "").strip():
                continue
            whole = texts[0].text
            half = len(whole) // 2
            if not half:
                continue
            texts[0].text = whole[:half].rstrip()
            clone = copy.deepcopy(run)
            for node in list(clone):
                if node.tag == _TEXT:
                    clone.remove(node)
            text = OxmlElement("w:t")
            text.text = whole[half:].lstrip()
            clone.append(text)
            run.addnext(clone)
        document.save(self.path)

    def add_note_after(self, needle: str, text: str) -> None:
        """Écrit un paragraphe de plus juste après un contenu du script."""
        document, paragraph = self.find(needle)
        note = OxmlElement("w:p")
        run = OxmlElement("w:r")
        content = OxmlElement("w:t")
        content.text = text
        run.append(content)
        note.append(run)
        paragraph._p.addnext(note)
        document.save(self.path)

    # ── Un lien réécrit en champ ──────────────────────────────────
    def test_lien_reecrit_en_champ_ne_remplit_pas_l_annexe(self):
        self.generate(_LINKED, CA="SUM(Ventes[Montant])", Marge="[CA] - SUM(Ventes[Cout])")
        self.link_to_field()

        self.generate(_LINKED, CA="SUM(Ventes[Montant])", Marge="[CA] - SUM(Ventes[Cout])")

        self.assertEqual(self.annexe(), [])

    def test_lien_reecrit_en_champ_laisse_le_code_a_sa_place(self):
        self.generate(_LINKED, CA="SUM(Ventes[Montant])", Marge="[CA] - SUM(Ventes[Cout])")
        self.link_to_field()

        self.generate(_LINKED, CA="SUM(Ventes[Montant])", Marge="[CA] - SUM(Ventes[Cout])")

        codes = [text for text in self.before_annexe() if "SUM(Ventes[Cout])" in text]
        self.assertEqual(len(codes), 1)

    def test_note_ecrite_sous_un_code_dont_le_lien_a_ete_reecrit(self):
        """Le texte de l'utilisateur reste sous la donnée qu'il commente."""
        self.generate(_LINKED, Marge="[CA] - SUM(Ventes[Cout])", CA="SUM(Ventes[Montant])")
        self.add_note_after("[CA] - SUM(Ventes[Cout])", "Le coût vient de la comptabilité.")
        self.link_to_field()

        self.generate(_LINKED, Marge="[CA] - SUM(Ventes[Cout])", CA="SUM(Ventes[Montant])")

        body = self.before_annexe()
        self.assertIn("Le coût vient de la comptabilité.", body)
        self.assertLess(
            body.index("[CA] - SUM(Ventes[Cout])"),
            body.index("Le coût vient de la comptabilité."),
        )
        self.assertEqual(self.annexe(), [])

    # ── Des runs recoupés ─────────────────────────────────────────
    def test_runs_recoupes_ne_remplissent_pas_l_annexe(self):
        self.generate(CA="VAR total = SUM(Ventes[Montant])\nRETURN\n    total")
        self.split_runs()

        self.generate(CA="VAR total = SUM(Ventes[Montant])\nRETURN\n    total")

        self.assertEqual(self.annexe(), [])

    # ── Une vraie retouche reste une retouche ─────────────────────
    def test_code_reellement_remanie_part_toujours_en_annexe(self):
        """La tolérance ne va pas jusqu'à ignorer un texte qu'on a réécrit."""
        self.generate(_LINKED, CA="SUM(Ventes[Montant])")
        self.rewrite("SUM(Ventes[Montant])", "SUM(Ventes[Autre chose])")
        self.link_to_field()

        self.generate(_LINKED, CA="SUM(Ventes[Montant])")

        self.assertIn("SUM(Ventes[Autre chose])", self.annexe())


def _field_char(kind: str):
    run = OxmlElement("w:r")
    char = OxmlElement("w:fldChar")
    char.set(qn("w:fldCharType"), kind)
    run.append(char)
    return run


def _instruction(text: str):
    run = OxmlElement("w:r")
    instruction = OxmlElement("w:instrText")
    instruction.set(qn("xml:space"), "preserve")
    instruction.text = text
    run.append(instruction)
    return run


if __name__ == "__main__":
    unittest.main()
