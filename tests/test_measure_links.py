"""Tests de la détection des mentions de mesures et des noms de signets."""

import unittest

from src.generators.measure_links import MeasureLinker, collect_measures
from src.generators.word_generator import _bookmark_name
from src.models.data_models import DaxMeasure, MeasureGroup


def linker(names: dict[str, str], **options) -> MeasureLinker:
    return MeasureLinker(targets=names, known_names=list(names), **options)


class MeasureLinkerTest(unittest.TestCase):
    def test_mention_simple(self):
        segments = linker({"Marge": "bm_marge"}).split("Total de la Marge du mois")
        self.assertEqual(
            segments,
            [("Total de la ", None), ("Marge", "bm_marge"), (" du mois", None)],
        )

    def test_nom_le_plus_long_gagne(self):
        segments = linker({"Marge": "bm_marge", "Marge %": "bm_taux"}).split("Formule : Marge %")
        self.assertEqual(segments[-1], ("Marge %", "bm_taux"))

    def test_pas_de_correspondance_partielle(self):
        segments = linker({"CA": "bm_ca"}).split("Le CAP et le CATALOGUE")
        self.assertEqual(segments, [("Le CAP et le CATALOGUE", None)])

    def test_mention_dans_du_code_dax(self):
        segments = linker({"Chiffre d'affaires": "bm_ca"}).split("DIVIDE([Chiffre d'affaires], 12)")
        self.assertIn(("Chiffre d'affaires", "bm_ca"), segments)

    def test_casse_ignoree_par_defaut(self):
        segments = linker({"Marge": "bm_marge"}).split("la MARGE nette")
        self.assertIn(("MARGE", "bm_marge"), segments)

    def test_casse_respectee_si_demande(self):
        segments = linker({"Marge": "bm_marge"}, case_sensitive=True).split("la MARGE nette")
        self.assertEqual(segments, [("la MARGE nette", None)])

    def test_toutes_les_mentions_sont_liees(self):
        segments = linker({"CA N-1": "bm"}).split("CA N-1 puis CA N-1")
        self.assertEqual([s for s in segments if s[1]], [("CA N-1", "bm"), ("CA N-1", "bm")])

    def test_premiere_mention_seulement(self):
        segments = linker({"CA N-1": "bm"}, first_occurrence_only=True).split("CA N-1 puis CA N-1")
        self.assertEqual([s for s in segments if s[1]], [("CA N-1", "bm")])

    def test_pas_de_lien_vers_soi_meme(self):
        segments = linker({"Marge": "bm_marge"}).split("Marge nette", skip_bookmark="bm_marge")
        self.assertEqual(segments, [("Marge nette", None)])

    def test_mesure_connue_mais_non_documentee(self):
        link = MeasureLinker(targets={}, known_names=["Marge"])
        segments = link.split("Basé sur Marge")
        self.assertEqual(segments, [("Basé sur Marge", None)])
        self.assertEqual(link.unlinked, {"Marge": 1})

    def test_nom_avec_caracteres_speciaux(self):
        segments = linker({"% Marge (N-1)": "bm"}).split("Indicateur % Marge (N-1) du mois")
        self.assertIn(("% Marge (N-1)", "bm"), segments)

    def test_texte_vide(self):
        self.assertEqual(linker({"Marge": "bm"}).split(""), [])


class CollectMeasuresTest(unittest.TestCase):
    def test_aplatit_les_groupes(self):
        ca = DaxMeasure(name="CA", expression="1", table_name="Ventes")
        jours = DaxMeasure(name="Nb jours", expression="2", table_name="Calendrier")
        groups = [
            MeasureGroup(name="Ventes", measures=[ca]),
            MeasureGroup(name="Cal", measures=[jours]),
        ]
        self.assertEqual([m.name for m in collect_measures(groups)], ["CA", "Nb jours"])

    def test_accepte_une_liste_de_mesures(self):
        ca = DaxMeasure(name="CA", expression="1", table_name="Ventes")
        self.assertEqual([m.name for m in collect_measures([ca])], ["CA"])


class BookmarkNameTest(unittest.TestCase):
    def test_noms_proches_restent_distincts(self):
        self.assertNotEqual(_bookmark_name("measure:Marge"), _bookmark_name("measure:Marge %"))

    def test_deterministe(self):
        self.assertEqual(_bookmark_name("measure:CA N-1"), _bookmark_name("measure:CA N-1"))

    def test_contraintes_word(self):
        name = _bookmark_name("measure:Évolution du chiffre d'affaires par région et par mois")
        self.assertLessEqual(len(name), 40)
        self.assertTrue(name[0].isalpha() or name[0] == "_")
        self.assertTrue(all(c.isalnum() or c == "_" for c in name))
        self.assertTrue(name.isascii())

    def test_nom_commencant_par_un_chiffre(self):
        self.assertFalse(_bookmark_name("2024").startswith("2"))


if __name__ == "__main__":
    unittest.main()
