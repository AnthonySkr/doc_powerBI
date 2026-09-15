"""
Tests du menu d'accueil, et de son articulation avec la ligne de commande.

Le menu ne doit s'interposer que lorsqu'on ne sait pas quoi documenter : un
`.pbip` glissé sur l'exécutable arrive en argument, et va droit à la
génération.
"""

import unittest
from unittest import mock

from src.cli import menu
from src.cli.arguments import parse_args


class MenuTest(unittest.TestCase):
    def _choose(self, answers: list[str]) -> tuple[str, mock.Mock]:
        with (
            mock.patch("builtins.input", side_effect=answers),
            mock.patch("builtins.print"),
            mock.patch.object(menu.guide, "show") as shown,
        ):
            return menu.choose(), shown

    def test_generer_demande_le_rapport(self):
        chosen, shown = self._choose(["1", "C:/Rapport.pbip"])
        self.assertEqual(chosen, "C:/Rapport.pbip")
        shown.assert_not_called()

    def test_entree_vide_genere(self):
        """La génération est le choix par défaut : Entrée suffit."""
        chosen, shown = self._choose(["", "C:/Rapport.pbip"])
        self.assertEqual(chosen, "C:/Rapport.pbip")
        shown.assert_not_called()

    def test_mode_emploi_puis_retour_au_menu(self):
        chosen, shown = self._choose(["2", "1", "C:/Rapport.pbip"])
        self.assertEqual(chosen, "C:/Rapport.pbip")
        shown.assert_called_once()

    def test_reponse_hors_menu_reposee(self):
        with (
            mock.patch("builtins.input", side_effect=["7", "1", "C:/Rapport.pbip"]),
            mock.patch("builtins.print"),
            mock.patch("src.console.warn") as warned,
        ):
            self.assertEqual(menu.choose(), "C:/Rapport.pbip")
        warned.assert_called_once()


class ArgumentsTest(unittest.TestCase):
    """Quand le menu s'ouvre, et quand il reste à l'écart."""

    def test_pbip_en_argument_court_circuite_le_menu(self):
        with mock.patch.object(menu, "choose") as opened:
            options = parse_args(["C:/Rapport.pbip"])
        opened.assert_not_called()
        self.assertEqual(options.pbip_path, "C:/Rapport.pbip")

    def test_guillemets_du_glisser_deposer_otes(self):
        options = parse_args(['"C:/Mon rapport.pbip"'])
        self.assertEqual(options.pbip_path, "C:/Mon rapport.pbip")

    def test_sans_argument_le_menu_s_ouvre(self):
        with mock.patch.object(menu, "choose", return_value="C:/Rapport.pbip") as opened:
            options = parse_args([])
        opened.assert_called_once()
        self.assertEqual(options.pbip_path, "C:/Rapport.pbip")

    def test_no_input_ne_pose_aucune_question(self):
        """`--no-input` demande le silence : pas même un menu."""
        with mock.patch.object(menu, "choose") as opened:
            options = parse_args(["--no-input"])
        opened.assert_not_called()
        self.assertEqual(options.pbip_path, "")

    def test_mode_emploi_ne_demande_pas_de_rapport(self):
        with mock.patch.object(menu, "choose") as opened:
            options = parse_args(["--mode-emploi"])
        opened.assert_not_called()
        self.assertTrue(options.readme)
        self.assertEqual(options.pbip_path, "")

    def test_readme_est_un_synonyme(self):
        self.assertTrue(parse_args(["--readme"]).readme)

    def test_generation_ordinaire_sans_mode_emploi(self):
        self.assertFalse(parse_args(["C:/Rapport.pbip"]).readme)


class EntreeCliTest(unittest.TestCase):
    """`--mode-emploi` affiche les consignes, et ne génère rien."""

    def test_mode_emploi_n_appelle_pas_le_pipeline(self):
        from src import cli

        with (
            mock.patch("src.cli.guide.show") as shown,
            mock.patch("src.cli.run") as generated,
            mock.patch("builtins.print"),
        ):
            self.assertEqual(cli.main(["--mode-emploi"]), 0)
        shown.assert_called_once()
        generated.assert_not_called()


if __name__ == "__main__":
    unittest.main()
