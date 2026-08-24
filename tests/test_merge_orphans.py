"""
Rien ne se perd : les contenus qui n'ont plus de place vont en annexe.

Trois situations où la fusion ne peut pas reposer un texte là où il était —
l'élément a disparu du rapport, le bloc a été retiré du plan, la donnée du
script sur laquelle on avait écrit a été remaniée. Aucune ne doit se solder par
une suppression silencieuse.
"""

import copy
import unittest

from docx import Document

from src.merge import orphans
from tests.test_merge_cycle import PLAN, MergeHarness


class OrphansTest(MergeHarness):
    # ── Élément disparu du rapport ────────────────────────────────
    def test_mesure_retiree_du_rapport_laisse_sa_redaction_en_annexe(self):
        self.generate(marge="SUM(T[a])", ca="SUM(T[b])")
        self.rewrite("[À compléter]", "Tout ce que je sais de cette mesure")

        self.generate(ca="SUM(T[b])")

        self.assertIn("Tout ce que je sais de cette mesure", self.annexe())

    def test_provenance_indiquee(self):
        self.generate(marge="SUM(T[a])", ca="SUM(T[b])")
        self.rewrite("[À compléter]", "Ma rédaction")

        self.generate(ca="SUM(T[b])")

        self.assertTrue(
            any("Retiré du rapport" in text and "measure:" in text for text in self.annexe())
        )

    def test_renommage_ambigu_recueilli(self):
        """Deux mesures de même formule : le rapprochement serait un pari."""
        self.generate(marge="SUM(T[a])", copie="SUM(T[a])")
        self.rewrite("[À compléter]", "Ma rédaction sur la marge")

        self.generate(marge_nette="SUM(T[a])", copie_nette="SUM(T[a])")

        self.assertIn("Ma rédaction sur la marge", self.annexe())

    def test_amorce_jamais_rediged_non_archivee(self):
        """Archiver un « [À compléter] » resté vide n'apprendrait rien."""
        self.generate(marge="SUM(T[a])", ca="SUM(T[b])")

        self.generate(ca="SUM(T[b])")

        self.assertNotIn("[À compléter]", self.annexe())

    def test_aucune_annexe_quand_rien_ne_se_perd(self):
        self.generate(marge="SUM(T[a])")
        self.rewrite("[À compléter]", "Ma rédaction")

        self.generate(marge="SUM(T[a])")

        self.assertEqual(self.annexe(), [])

    # ── Bloc retiré du plan ───────────────────────────────────────
    def test_texte_ecrit_dans_un_bloc_retire_du_plan(self):
        self.generate(marge="SUM(T[a])")
        self.write_under_table("Ce tableau se lit de gauche à droite")

        plan = copy.deepcopy(PLAN)
        section = plan["sections"][0]["blocks"][0]["section"]["blocks"][0]["section"]
        section["blocks"] = [b for b in section["blocks"] if b["id"] != "champs"]
        self.generate({"sections": plan["sections"]}, marge="SUM(T[a])")

        # Le bloc existe encore dans le plan au moment de la fusion : le texte
        # revient à sa place, il n'a pas besoin de l'annexe.
        self.assertIn("Ce tableau se lit de gauche à droite", self.before_annexe())

    # ── Reconduction de l'annexe ──────────────────────────────────
    def test_annexe_reconduite_a_la_generation_suivante(self):
        self.generate(marge="SUM(T[a])", ca="SUM(T[b])")
        self.rewrite("[À compléter]", "Ma rédaction")
        self.generate(ca="SUM(T[b])")

        self.generate(ca="SUM(T[b])")

        self.assertIn("Ma rédaction", self.annexe())

    def test_annexe_sans_titre_en_double(self):
        self.generate(marge="SUM(T[a])", ca="SUM(T[b])")
        self.rewrite("[À compléter]", "Ma rédaction")
        self.generate(ca="SUM(T[b])")
        self.generate(ca="SUM(T[b])")

        self.assertEqual(self.annexe().count("Contenu non replacé"), 1)

    def test_annexe_stable_sur_plusieurs_generations(self):
        self.generate(marge="SUM(T[a])", ca="SUM(T[b])")
        self.rewrite("[À compléter]", "Ma rédaction")
        self.generate(ca="SUM(T[b])")
        self.generate(ca="SUM(T[b])")
        first = self.annexe()

        self.generate(ca="SUM(T[b])")

        self.assertEqual(self.annexe(), first)

    def test_annexe_videe_a_la_main_ne_revient_pas(self):
        self.generate(marge="SUM(T[a])", ca="SUM(T[b])")
        self.rewrite("[À compléter]", "Ma rédaction")
        self.generate(ca="SUM(T[b])")
        self._empty_annexe()

        self.generate(ca="SUM(T[b])")

        self.assertEqual(self.annexe(), [])

    # ── Réglage ───────────────────────────────────────────────────
    def test_annexe_desactivable(self):
        self.generate({"merge": {"orphans": {"enabled": False}}}, marge="SUM(T[a])", ca="SUM(T[b])")
        self.rewrite("[À compléter]", "Ma rédaction")

        self.generate({"merge": {"orphans": {"enabled": False}}}, ca="SUM(T[b])")

        self.assertEqual(self.annexe(), [])

    def test_titre_configurable(self):
        options = {"merge": {"orphans": {"title": "À reclasser"}}}
        self.generate(options, marge="SUM(T[a])", ca="SUM(T[b])")
        self.rewrite("[À compléter]", "Ma rédaction")

        self.generate(options, ca="SUM(T[b])")

        self.assertIn("À reclasser", self.annexe())

    # ── Utilitaire ────────────────────────────────────────────────
    def _empty_annexe(self) -> None:
        """Supprime l'annexe, comme le ferait l'utilisateur une fois reclassée."""
        document = Document(self.path)
        body = document.element.body
        removing = False
        for node in list(body):
            text = node.xpath("string(.)") if node.tag.endswith("}p") else ""
            if text.startswith(f"pbi::elem|{orphans.ELEMENT_ID}|"):
                removing = True
            if removing:
                body.remove(node)
        document.save(self.path)


if __name__ == "__main__":
    unittest.main()
