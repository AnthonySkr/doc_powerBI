"""
Tests du point d'entrée : code de sortie, et pause avant fermeture.

Une fenêtre ouverte par un double-clic ou un glisser-déposer se referme dès la
fin du programme. La pause n'a de sens que dans ce cas.
"""

import unittest
from unittest import mock

from src import cli
from src.cli.arguments import Options
from src.pipeline import PipelineError


def options(**values) -> Options:
    return Options(
        pbip_path=values.get("pbip_path", "rapport.pbip"),
        config_path=values.get("config_path", "config.yaml"),
        interactive=values.get("interactive", False),
        pause=values.get("pause", True),
    )


class ExitCodeTest(unittest.TestCase):
    def _main(self, run_side_effect):
        with (
            mock.patch("src.cli.parse_args", return_value=options(pause=False)),
            mock.patch("src.cli.run", side_effect=run_side_effect),
            mock.patch("builtins.print"),
        ):
            return cli.main([])

    def test_succes(self):
        self.assertEqual(self._main(lambda o: "/sortie"), 0)

    def test_erreur_attendue(self):
        self.assertEqual(self._main(PipelineError("fichier introuvable")), 1)

    def test_interruption(self):
        self.assertEqual(self._main(KeyboardInterrupt()), 130)

    def test_erreur_imprevue_signalee_et_non_propagee(self):
        with mock.patch("traceback.print_exc") as printed:
            self.assertEqual(self._main(ValueError("bug")), 1)
        printed.assert_called_once()


class PauseTest(unittest.TestCase):
    """La pause n'a lieu que depuis l'exécutable distribué."""

    def _main(self, frozen: bool, pause: bool = True, run_side_effect=None):
        with (
            mock.patch("src.cli.parse_args", return_value=options(pause=pause)),
            mock.patch("src.cli.run", side_effect=run_side_effect or (lambda o: "/sortie")),
            mock.patch("src.paths.is_frozen", return_value=frozen),
            mock.patch("builtins.input") as prompted,
            mock.patch("builtins.print"),
        ):
            cli.main([])
        return prompted

    def test_pause_depuis_l_executable(self):
        self.assertEqual(self._main(frozen=True).call_count, 1)

    def test_pas_de_pause_en_developpement(self):
        self._main(frozen=False).assert_not_called()

    def test_pause_aussi_en_cas_d_erreur(self):
        prompted = self._main(frozen=True, run_side_effect=PipelineError("échec"))
        self.assertEqual(prompted.call_count, 1)

    def test_pause_aussi_sur_erreur_imprevue(self):
        with mock.patch("traceback.print_exc"):
            prompted = self._main(frozen=True, run_side_effect=ValueError("bug"))
        self.assertEqual(prompted.call_count, 1)

    def test_desactivable_par_option(self):
        self._main(frozen=True, pause=False).assert_not_called()

    def test_entree_absente_ne_bloque_pas(self):
        with (
            mock.patch("src.cli.parse_args", return_value=options()),
            mock.patch("src.cli.run", return_value="/sortie"),
            mock.patch("src.paths.is_frozen", return_value=True),
            mock.patch("builtins.input", side_effect=RuntimeError("lost sys.stdin")),
            mock.patch("builtins.print"),
        ):
            self.assertEqual(cli.main([]), 0)


if __name__ == "__main__":
    unittest.main()
