"""
Tests du point d'entrée : code de sortie, et pause avant fermeture.

Une fenêtre ouverte par un double-clic ou un glisser-déposer se referme dès la
fin du programme. La pause n'a de sens que dans ce cas.

Une erreur imprévue n'est pas rattrapée en cours de route : elle remonte, et
c'est le gestionnaire posé sur `sys.excepthook` qui l'affiche puis retient la
fenêtre (voir `core.window`).
"""

import sys
import unittest
from unittest import mock

import main
from main import Options, PipelineError
from src.core.window import ConsoleWindow


def options(**values) -> Options:
    return Options(pbip_path=values.pop("pbip_path", "rapport.pbip"), **values)


class MainTestCase(unittest.TestCase):
    """`main` pose un gestionnaire global : il est remis en place après coup."""

    def setUp(self):
        excepthook = sys.excepthook
        self.addCleanup(setattr, sys, "excepthook", excepthook)


class ExitCodeTest(MainTestCase):
    def _main(self, generate_side_effect):
        with (
            mock.patch("main.parse_args", return_value=options(pause=False)),
            mock.patch("main.generate", side_effect=generate_side_effect),
            mock.patch("builtins.print"),
        ):
            return main.main([])

    def test_succes(self):
        self.assertEqual(self._main(lambda o: "/sortie"), 0)

    def test_erreur_attendue(self):
        self.assertEqual(self._main(PipelineError("fichier introuvable")), 1)

    def test_interruption(self):
        self.assertEqual(self._main(KeyboardInterrupt()), 130)

    def test_erreur_imprevue_non_avalee(self):
        with self.assertRaises(ValueError):
            self._main(ValueError("bug"))


class CrashHandlerTest(MainTestCase):
    """Le gestionnaire posé par `main` affiche l'erreur et retient la fenêtre."""

    def test_pose_par_main(self):
        with (
            mock.patch("main.parse_args", return_value=options(pause=False)),
            mock.patch("main.generate", return_value="/sortie"),
            mock.patch("builtins.print"),
        ):
            main.main([])
        self.assertNotEqual(sys.excepthook, sys.__excepthook__)

    def test_affiche_la_trace_et_attend(self):
        window = ConsoleWindow()
        window.pause = True
        error = ValueError("bug")
        with (
            mock.patch("traceback.print_exception") as printed,
            mock.patch("builtins.input") as prompted,
            mock.patch("builtins.print"),
        ):
            window.report_crash(type(error), error, None)
        printed.assert_called_once()
        self.assertEqual(prompted.call_count, 1)


class PauseTest(MainTestCase):
    """La pause n'a lieu que depuis l'exécutable distribué."""

    def _main(self, frozen: bool, pause: bool = True, generate_side_effect=None):
        with (
            mock.patch("main.parse_args", return_value=options(pause=pause)),
            mock.patch("main.generate", side_effect=generate_side_effect or (lambda o: "/sortie")),
            mock.patch("src.core.paths.is_frozen", return_value=frozen),
            mock.patch("builtins.input") as prompted,
            mock.patch("builtins.print"),
        ):
            main.main([])
        return prompted

    def test_pause_depuis_l_executable(self):
        self.assertEqual(self._main(frozen=True).call_count, 1)

    def test_pas_de_pause_en_developpement(self):
        self._main(frozen=False).assert_not_called()

    def test_pause_aussi_en_cas_d_erreur(self):
        prompted = self._main(frozen=True, generate_side_effect=PipelineError("échec"))
        self.assertEqual(prompted.call_count, 1)

    def test_desactivable_par_option(self):
        self._main(frozen=True, pause=False).assert_not_called()

    def test_entree_absente_ne_bloque_pas(self):
        with (
            mock.patch("main.parse_args", return_value=options()),
            mock.patch("main.generate", return_value="/sortie"),
            mock.patch("src.core.paths.is_frozen", return_value=True),
            mock.patch("builtins.input", side_effect=OSError("lost sys.stdin")),
            mock.patch("builtins.print"),
        ):
            self.assertEqual(main.main([]), 0)


if __name__ == "__main__":
    unittest.main()
