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
    def _main(self, will_close: bool, pause: bool = True, run_side_effect=None):
        with (
            mock.patch("src.cli.parse_args", return_value=options(pause=pause)),
            mock.patch("src.cli.run", side_effect=run_side_effect or (lambda o: "/sortie")),
            mock.patch("src.cli._console_will_close", return_value=will_close),
            mock.patch("builtins.input") as prompted,
            mock.patch("builtins.print"),
        ):
            cli.main([])
        return prompted

    def test_pause_si_la_fenetre_va_se_fermer(self):
        self.assertEqual(self._main(will_close=True).call_count, 1)

    def test_pas_de_pause_depuis_un_terminal(self):
        self._main(will_close=False).assert_not_called()

    def test_pause_aussi_en_cas_d_erreur(self):
        prompted = self._main(will_close=True, run_side_effect=PipelineError("échec"))
        self.assertEqual(prompted.call_count, 1)

    def test_pause_aussi_sur_erreur_imprevue(self):
        with mock.patch("traceback.print_exc"):
            prompted = self._main(will_close=True, run_side_effect=ValueError("bug"))
        self.assertEqual(prompted.call_count, 1)

    def test_desactivable_par_option(self):
        self._main(will_close=True, pause=False).assert_not_called()


class ConsoleDetectionTest(unittest.TestCase):
    def test_jamais_hors_windows(self):
        with mock.patch("os.name", "posix"):
            self.assertFalse(cli._console_will_close())

    def test_pas_de_pause_si_l_entree_est_redirigee(self):
        with (
            mock.patch("os.name", "nt"),
            mock.patch("sys.stdin", mock.Mock(isatty=lambda: False)),
        ):
            self.assertFalse(cli._console_will_close())

    def test_pas_de_pause_sans_entree(self):
        with mock.patch("os.name", "nt"), mock.patch("sys.stdin", None):
            self.assertFalse(cli._console_will_close())


if __name__ == "__main__":
    unittest.main()
