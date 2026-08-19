"""
Localisation du template Word.

Régression : le template était cherché dans le dossier courant seulement.
Un exécutable ouvert par glisser-déposer hérite d'un dossier courant
quelconque — la configuration était trouvée, le template non.
"""

import os
import shutil
import tempfile
import unittest
from unittest import mock

from docx import Document

from src import paths
from src.config import DocConfig
from src.generators.word.generator import DocumentError, _template_path


class TemplateLookupTest(unittest.TestCase):
    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.directory = self._directory.name

        # Dossier courant sans rapport, comme après un glisser-déposer.
        self._cwd = os.getcwd()
        self.elsewhere = os.path.join(self.directory, "ailleurs")
        os.makedirs(self.elsewhere)
        os.chdir(self.elsewhere)
        self.addCleanup(os.chdir, self._cwd)

    def _template(self, folder: str) -> str:
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, "template.docx")
        Document().save(path)
        return path

    def _config(self, folder: str) -> DocConfig:
        return DocConfig(
            {"document": {"template": "template.docx"}}, os.path.join(folder, "c.yaml")
        )

    def _find(self, config: DocConfig, app_dir: str = "/dossier/absent") -> str:
        with (
            mock.patch.object(paths, "app_dir", return_value=app_dir),
            mock.patch.object(paths, "bundled_dir", return_value=""),
        ):
            return _template_path(config, {})

    def test_trouve_a_cote_de_la_configuration(self):
        folder = os.path.join(self.directory, "livraison")
        expected = self._template(folder)
        self.assertEqual(self._find(self._config(folder)), expected)

    def test_trouve_a_cote_de_l_executable(self):
        exe_dir = os.path.join(self.directory, "exe")
        expected = self._template(exe_dir)
        config = self._config(os.path.join(self.directory, "config"))
        self.assertEqual(self._find(config, app_dir=exe_dir), expected)

    def test_chemin_absolu_respecte(self):
        path = self._template(os.path.join(self.directory, "charte"))
        config = DocConfig({"document": {"template": path}}, "c.yaml")
        self.assertEqual(self._find(config), path)

    def test_message_cite_les_emplacements_consultes(self):
        config = self._config(os.path.join(self.directory, "vide"))
        with self.assertRaises(DocumentError) as raised:
            self._find(config)
        message = str(raised.exception)
        self.assertIn("Template introuvable", message)
        self.assertIn(os.path.join(self.directory, "vide"), message)

    def test_template_non_declare(self):
        with self.assertRaises(DocumentError) as raised:
            self._find(DocConfig({"document": {"template": ""}}, "c.yaml"))
        self.assertIn("Aucun template", str(raised.exception))

    def test_dossier_courant_encore_accepte(self):
        """Lancé depuis le dépôt, le chemin relatif continue de fonctionner."""
        shutil.copy(self._template(self.directory), os.path.join(self.elsewhere, "template.docx"))
        config = DocConfig({"document": {"template": "template.docx"}}, "")
        self.assertEqual(self._find(config), "template.docx")


if __name__ == "__main__":
    unittest.main()
