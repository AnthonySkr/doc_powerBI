"""Tests de la localisation des fichiers livrés avec l'application."""

import os
import sys
import tempfile
import unittest
from unittest import mock

from src import paths


class FindTest(unittest.TestCase):
    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.directory = self._directory.name

    def _file(self, name: str) -> str:
        path = os.path.join(self.directory, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write("x")
        return path

    def test_chemin_absolu_rendu_tel_quel(self):
        path = self._file("config.yaml")
        self.assertEqual(paths.find(path), path)

    def test_fichier_du_dossier_courant_prioritaire(self):
        path = self._file("config.yaml")
        with mock.patch("os.path.isfile", lambda p: p == "config.yaml"):
            self.assertEqual(paths.find("config.yaml"), "config.yaml")
        self.assertTrue(os.path.isfile(path))

    def test_fichier_a_cote_de_l_executable(self):
        self._file("config.yaml")
        with mock.patch.object(paths, "app_dir", return_value=self.directory):
            self.assertEqual(paths.find("config.yaml"), os.path.join(self.directory, "config.yaml"))

    def test_copie_de_secours_embarquee(self):
        self._file("config.yaml")
        with (
            mock.patch.object(paths, "app_dir", return_value="/dossier/absent"),
            mock.patch.object(paths, "bundled_dir", return_value=self.directory),
        ):
            self.assertEqual(paths.find("config.yaml"), os.path.join(self.directory, "config.yaml"))

    def test_nom_inchange_si_introuvable(self):
        with mock.patch.object(paths, "app_dir", return_value="/dossier/absent"):
            self.assertEqual(paths.find("absent.yaml"), "absent.yaml")


class AppDirTest(unittest.TestCase):
    def test_racine_du_depot_en_developpement(self):
        self.assertTrue(os.path.isfile(os.path.join(paths.app_dir(), "pyproject.toml")))

    def test_dossier_de_l_executable_une_fois_gele(self):
        with (
            mock.patch.object(sys, "frozen", True, create=True),
            mock.patch.object(sys, "executable", "/opt/appli/powerbi-doc.exe"),
        ):
            self.assertTrue(paths.is_frozen())

    def test_pas_de_dossier_embarque_hors_executable(self):
        self.assertEqual(paths.bundled_dir(), "")


if __name__ == "__main__":
    unittest.main()


class NearTest(unittest.TestCase):
    """Le fichier est cherché à côté de celui qui le désigne."""

    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.directory = self._directory.name

    def test_trouve_a_cote_du_fichier_qui_le_designe(self):
        path = os.path.join(self.directory, "template.docx")
        with open(path, "wb") as f:
            f.write(b"x")
        with mock.patch.object(paths, "app_dir", return_value="/dossier/absent"):
            self.assertEqual(paths.find("template.docx", near=self.directory), path)

    def test_near_prioritaire_sur_l_executable(self):
        near = os.path.join(self.directory, "config")
        beside = os.path.join(self.directory, "exe")
        for folder in (near, beside):
            os.makedirs(folder)
            with open(os.path.join(folder, "template.docx"), "wb") as f:
                f.write(b"x")
        with mock.patch.object(paths, "app_dir", return_value=beside):
            self.assertEqual(
                paths.find("template.docx", near=near), os.path.join(near, "template.docx")
            )


class CandidatesTest(unittest.TestCase):
    """La liste des emplacements consultés alimente les messages d'erreur."""

    def test_ordre_de_recherche(self):
        with (
            mock.patch.object(paths, "app_dir", return_value="/appli"),
            mock.patch.object(paths, "bundled_dir", return_value="/bundle"),
        ):
            self.assertEqual(
                paths.candidates("t.docx", near="/config"),
                [
                    "t.docx",
                    os.path.join("/config", "t.docx"),
                    os.path.join("/appli", "t.docx"),
                    os.path.join("/bundle", "t.docx"),
                ],
            )

    def test_sans_doublon(self):
        with (
            mock.patch.object(paths, "app_dir", return_value="/appli"),
            mock.patch.object(paths, "bundled_dir", return_value="/appli"),
        ):
            self.assertEqual(len(paths.candidates("t.docx", near="/appli")), 2)

    def test_hors_executable(self):
        with mock.patch.object(paths, "app_dir", return_value="/appli"):
            self.assertEqual(
                paths.candidates("t.docx"), ["t.docx", os.path.join("/appli", "t.docx")]
            )
