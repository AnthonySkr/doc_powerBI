"""
Les quatre modes du lancement : texte, captures, images, complet.

Éprouvés de bout en bout avec les captures factices : rien n'ouvre Power BI,
mais chaque mode écrit — ou n'écrit pas — exactement ce qu'il annonce.
"""

import os
import shutil
import tempfile
import unittest
from unittest import mock

from docx import Document
from docx.oxml.ns import qn

import main
from main import CAPTURES, FULL, PICTURES, TEXT, Options, PipelineError, generate
from src.core import console
from src.core.config import DEFAULT_CAPTURES_DIR, DEFAULT_CONFIG_PATH
from src.gui_automator.capturer import CaptureOptions

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "rapport_test")
DOCUMENT = "documentation_Rapport.docx"


class ModesTest(unittest.TestCase):
    def setUp(self):
        # Forme longue : sous Windows, le dossier temporaire peut venir en nom
        # court (`ASKRZY~1`), que la lecture du projet déplie.
        temp = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, temp, ignore_errors=True)
        self.project = os.path.join(temp, "rapport_test")
        shutil.copytree(FIXTURE, self.project)
        self.captures = os.path.join(self.project, DEFAULT_CAPTURES_DIR)

    def _run(self, mode: str):
        options = Options(
            pbip_path=os.path.join(self.project, "Rapport.pbip"),
            config_path=DEFAULT_CONFIG_PATH,
            interactive=False,
            pause=False,
            mode=mode,
            capture_options=CaptureOptions(fake=True),
        )
        with console.silenced():
            return generate(options)

    def _pictures(self, output_dir) -> int:
        document = Document(os.path.join(output_dir, DOCUMENT))
        return len(list(document.element.body.iter(qn("wp:inline"))))

    def _documents(self) -> list[str]:
        return [name for _, _, files in os.walk(self.project) for name in files if name == DOCUMENT]

    def test_texte_seul_ne_prend_aucune_capture(self):
        output = self._run(TEXT)
        self.assertFalse(os.path.isdir(self.captures))
        self.assertEqual(self._pictures(output), 0)

    def test_captures_seules_n_ecrivent_aucun_document(self):
        output = self._run(CAPTURES)
        self.assertEqual(str(output), self.captures)
        self.assertTrue(os.listdir(self.captures))
        self.assertEqual(self._documents(), [])

    def test_complet_insere_les_captures(self):
        self.assertGreater(self._pictures(self._run(FULL)), 0)

    def test_mise_a_jour_des_images_sans_document(self):
        with self.assertRaises(PipelineError):
            self._run(PICTURES)
        self.assertFalse(os.path.isdir(self.captures), "Power BI sollicité pour rien")

    def test_mise_a_jour_des_images_apres_le_texte(self):
        self.assertEqual(self._pictures(self._run(TEXT)), 0)
        output = self._run(PICTURES)
        self.assertGreater(self._pictures(output), 0)
        self.assertEqual(len(self._documents()), 1)

    def test_captures_ajoutees_apres_le_texte(self):
        with mock.patch("main._captures_wanted", return_value=True):
            output = self._run(TEXT)
        self.assertGreater(self._pictures(output), 0)


class ModeChoiceTest(unittest.TestCase):
    """Le mode vient de l'option, ou à défaut de la question du lancement."""

    def _mode(self, *argv: str) -> str:
        with mock.patch("main._ask_mode", return_value=PICTURES):
            return main.parse_args(["rapport.pbip", *argv]).mode

    def test_option_explicite(self):
        self.assertEqual(self._mode("--mode", CAPTURES), CAPTURES)

    def test_captures_vaut_complet(self):
        self.assertEqual(self._mode("--captures"), FULL)
        self.assertEqual(self._mode("--fake-captures"), FULL)

    def test_question_posee_par_defaut(self):
        self.assertEqual(self._mode(), PICTURES)

    def test_sans_question_le_texte_seul(self):
        self.assertEqual(self._mode("--no-input"), TEXT)

    def test_le_menu_rend_un_mode(self):
        with mock.patch("src.core.console.ask", return_value="2"), console.silenced():
            self.assertEqual(main._ask_mode(), CAPTURES)


if __name__ == "__main__":
    unittest.main()
