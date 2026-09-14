"""Tests de la localisation des fichiers livrés avec l'application."""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core import paths


class FindTest(unittest.TestCase):
    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.directory = Path(self._directory.name)

    def _file(self, name: str) -> Path:
        path = self.directory / name
        path.write_text("x", encoding="utf-8")
        return path

    def test_chemin_absolu_rendu_tel_quel(self):
        path = self._file("config.yaml")
        self.assertEqual(paths.find(path), path)

    def test_fichier_du_dossier_courant_prioritaire(self):
        path = self._file("config.yaml")
        with mock.patch.object(Path, "is_file", lambda p: str(p) == "config.yaml"):
            self.assertEqual(paths.find("config.yaml"), Path("config.yaml"))
        self.assertTrue(path.is_file())

    def test_fichier_a_cote_de_l_executable(self):
        self._file("plan-absent-du-depot.yaml")
        with mock.patch.object(paths, "app_dir", return_value=self.directory):
            self.assertEqual(
                paths.find("plan-absent-du-depot.yaml"),
                self.directory / "plan-absent-du-depot.yaml",
            )

    def test_copie_de_secours_embarquee(self):
        self._file("plan-absent-du-depot.yaml")
        with (
            mock.patch.object(paths, "app_dir", return_value=Path("/dossier/absent")),
            mock.patch.object(paths, "bundled_dir", return_value=self.directory),
        ):
            self.assertEqual(
                paths.find("plan-absent-du-depot.yaml"),
                self.directory / "plan-absent-du-depot.yaml",
            )

    def test_nom_inchange_si_introuvable(self):
        with mock.patch.object(paths, "app_dir", return_value=Path("/dossier/absent")):
            self.assertEqual(paths.find("absent.yaml"), Path("absent.yaml"))


class AppDirTest(unittest.TestCase):
    def test_racine_du_depot_en_developpement(self):
        self.assertTrue((paths.app_dir() / "pyproject.toml").is_file())

    def test_dossier_de_l_executable_une_fois_gele(self):
        with (
            mock.patch.object(sys, "frozen", True, create=True),
            mock.patch.object(sys, "executable", "/opt/appli/powerbi-doc.exe"),
        ):
            self.assertTrue(paths.is_frozen())

    def test_pas_de_dossier_embarque_hors_executable(self):
        self.assertIsNone(paths.bundled_dir())


class NearTest(unittest.TestCase):
    """Le fichier est cherché à côté de celui qui le désigne."""

    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.directory = Path(self._directory.name)

    def test_trouve_a_cote_du_fichier_qui_le_designe(self):
        path = self.directory / "template.docx"
        path.write_bytes(b"x")
        with mock.patch.object(paths, "app_dir", return_value=Path("/dossier/absent")):
            self.assertEqual(paths.find("template.docx", near=self.directory), path)

    def test_near_prioritaire_sur_l_executable(self):
        near = self.directory / "config"
        beside = self.directory / "exe"
        for folder in (near, beside):
            folder.mkdir()
            (folder / "template.docx").write_bytes(b"x")
        with mock.patch.object(paths, "app_dir", return_value=beside):
            self.assertEqual(paths.find("template.docx", near=near), near / "template.docx")


class CandidatesTest(unittest.TestCase):
    """La liste des emplacements consultés alimente les messages d'erreur."""

    def test_ordre_de_recherche(self):
        with (
            mock.patch.object(paths, "app_dir", return_value=Path("/appli")),
            mock.patch.object(paths, "bundled_dir", return_value=Path("/bundle")),
        ):
            self.assertEqual(
                paths.candidates("t.docx", near="/config"),
                [
                    Path("t.docx"),
                    Path("/config/t.docx"),
                    Path("/appli/t.docx"),
                    Path("/bundle/t.docx"),
                ],
            )

    def test_sans_doublon(self):
        with (
            mock.patch.object(paths, "app_dir", return_value=Path("/appli")),
            mock.patch.object(paths, "bundled_dir", return_value=Path("/appli")),
        ):
            self.assertEqual(len(paths.candidates("t.docx", near="/appli")), 2)

    def test_hors_executable(self):
        with (
            mock.patch.object(paths, "app_dir", return_value=Path("/appli")),
            mock.patch.object(paths, "bundled_dir", return_value=None),
        ):
            self.assertEqual(paths.candidates("t.docx"), [Path("t.docx"), Path("/appli/t.docx")])


if __name__ == "__main__":
    unittest.main()
