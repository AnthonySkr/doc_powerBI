"""
Une mesure renommée dans Power BI garde sa documentation.

Un renommage change l'identifiant de l'élément : le document voyait une
suppression suivie d'un ajout, et la rédaction ne suivait pas. L'état technique,
lui, n'a pas bougé — c'est la même formule DAX. C'est par là qu'on les
rapproche, et seulement quand c'est sans ambiguïté.
"""

import unittest

from tests.test_merge_cycle import MergeHarness


class RenameTest(MergeHarness):
    def test_redaction_suit_la_mesure_renommee(self):
        self.generate(marge="SUM(T[a])")
        self.rewrite("[À compléter]", "Ma rédaction sur la marge")

        self.generate(marge_nette="SUM(T[a])")

        self.assertIn("Ma rédaction sur la marge", self.before_annexe())

    def test_renommage_signale_comme_tel(self):
        self.generate(marge="SUM(T[a])")

        log = self.generate(marge_nette="SUM(T[a])")

        self.assertEqual(log.renamed, [("measure:marge", "measure:marge_nette")])
        self.assertEqual(log.new, [])
        self.assertEqual(log.removed, [])

    def test_titre_reformule_suit_aussi(self):
        self.generate(marge="SUM(T[a])")
        self.rewrite("marge", "Marge commerciale — Europe")

        self.generate(marge_nette="SUM(T[a])")

        self.assertIn("Marge commerciale — Europe", self.texts())

    def test_donnees_du_script_mises_a_jour(self):
        """Le nom d'aujourd'hui est bien celui du rapport, pas celui d'hier."""
        self.generate(marge="SUM(T[a])")

        self.generate(marge_nette="SUM(T[b])")

        texts = self.before_annexe()
        self.assertIn("SUM(T[b])", texts)
        self.assertNotIn("SUM(T[a])", texts)

    def test_pas_de_rapprochement_si_la_formule_a_change(self):
        """Sans état technique commun, rien ne dit que c'est le même élément."""
        self.generate(marge="SUM(T[a])")
        self.rewrite("[À compléter]", "Ma rédaction")

        log = self.generate(marge_nette="SUM(T[zzz])")

        self.assertEqual(log.renamed, [])
        self.assertIn("Ma rédaction", self.annexe())

    def test_pas_de_rapprochement_si_deux_candidats(self):
        self.generate(marge="SUM(T[a])", copie="SUM(T[a])")

        log = self.generate(marge_nette="SUM(T[a])", copie_nette="SUM(T[a])")

        self.assertEqual(log.renamed, [])

    def test_ajout_simple_reste_un_ajout(self):
        self.generate(marge="SUM(T[a])")

        log = self.generate(marge="SUM(T[a])", nouvelle="SUM(T[b])")

        self.assertEqual(log.renamed, [])
        self.assertEqual(log.new, ["measure:nouvelle"])

    def test_document_stable_apres_un_renommage(self):
        self.generate(marge="SUM(T[a])")
        self.rewrite("[À compléter]", "Ma rédaction")
        self.generate(marge_nette="SUM(T[a])")
        first = self.layout()

        self.generate(marge_nette="SUM(T[a])")

        self.assertEqual(self.layout(), first)


if __name__ == "__main__":
    unittest.main()
