"""
Résolution de la version : le tag du dépôt, puis le fichier de construction.

Les tags de version vivent sur `main` ; une branche de travail ne les voit pas.
C'est donc le dernier tag **du dépôt** qui est retenu, et non le dernier tag
atteignable — ce que `git describe` aurait donné.
"""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src.core import version as version_module
from src.core.version import UNKNOWN, VERSION_FILE, current, write_stamp


def git(directory: str, *arguments: str) -> None:
    """Lance une commande git dans le dépôt de test."""
    subprocess.run(
        ["git", *arguments],
        cwd=directory,
        check=True,
        capture_output=True,
        env={**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull},
    )


class Harness(unittest.TestCase):
    """Un dépôt jetable, dont `paths.app_dir` devient la racine."""

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = directory.name
        self.stamp_path = Path(self.directory) / VERSION_FILE

        # `paths.find` est détourné dès le départ, et pas seulement quand un
        # test dépose un fichier : sans cela, un `VERSION` laissé au pied du
        # dépôt par une construction ferait passer les cas sans repli.
        for target, value in (
            ("app_dir", Path(self.directory)),
            ("is_frozen", False),
            ("find", self.stamp_path),
        ):
            patch = mock.patch.object(version_module.paths, target, return_value=value)
            patch.start()
            self.addCleanup(patch.stop)

    def repository(self, *tags: str) -> None:
        """Crée un dépôt portant un commit et ces tags."""
        git(self.directory, "init", "--quiet")
        git(self.directory, "config", "user.email", "test@example.com")
        git(self.directory, "config", "user.name", "Test")
        git(self.directory, "commit", "--allow-empty", "--quiet", "-m", "initial")
        for tag in tags:
            git(self.directory, "tag", tag)

    def stamp(self, text: str) -> None:
        """Dépose un fichier `VERSION`, comme le ferait la construction."""
        self.stamp_path.write_text(text, encoding="utf-8")


class TagDuDepotTest(Harness):
    """Ce que la version retient parmi les tags posés."""

    def test_le_v_est_retire(self):
        self.repository("v0.6")
        self.assertEqual(current(), "0.6")

    def test_le_plus_haut_l_emporte(self):
        self.repository("v0.4", "v0.6", "v0.5")
        self.assertEqual(current(), "0.6")

    def test_les_numeros_sont_compares_comme_des_versions(self):
        """`v0.10` vient après `v0.9`, et non avant comme en ordre du texte."""
        self.repository("v0.9", "v0.10")
        self.assertEqual(current(), "0.10")

    def test_un_tag_de_trois_nombres_est_admis(self):
        self.repository("v0.3", "v0.3.1")
        self.assertEqual(current(), "0.3.1")

    def test_un_tag_qui_n_est_pas_une_version_est_ignore(self):
        self.repository("v0.6", "livraison-client")
        self.assertEqual(current(), "0.6")

    def test_un_tag_pose_hors_de_la_branche_compte_quand_meme(self):
        """Le cas réel : les versions sont posées sur `main`, on travaille ailleurs."""
        self.repository("v0.4")
        git(self.directory, "checkout", "--quiet", "-b", "develop")
        git(self.directory, "commit", "--allow-empty", "--quiet", "-m", "suite")
        git(self.directory, "checkout", "--quiet", "-")
        git(self.directory, "tag", "v0.6")
        git(self.directory, "checkout", "--quiet", "develop")

        self.assertEqual(current(), "0.6")


class ReplisTest(Harness):
    """Ce qui sert quand le dépôt ne répond pas."""

    def test_sans_tag_ni_fichier(self):
        self.repository()
        self.assertEqual(current(), UNKNOWN)

    def test_hors_depot(self):
        self.assertEqual(current(), UNKNOWN)

    def test_le_fichier_de_construction_prend_le_relais(self):
        self.stamp("0.7\n")
        self.assertEqual(current(), "0.7")

    def test_le_tag_passe_avant_le_fichier(self):
        self.repository("v0.6")
        self.stamp("0.1\n")
        self.assertEqual(current(), "0.6")


class ExecutableTest(Harness):
    """Un exécutable ne lit que sa version embarquée."""

    def setUp(self):
        super().setUp()
        patch = mock.patch.object(version_module.paths, "is_frozen", return_value=True)
        patch.start()
        self.addCleanup(patch.stop)

    def test_le_fichier_embarque_fait_foi(self):
        self.stamp("0.7\n")
        self.assertEqual(current(), "0.7")

    def test_le_depot_alentour_n_est_pas_consulte(self):
        """Un exe posé dans le dépôt de quelqu'un d'autre n'en prend pas la version."""
        self.repository("v9.9")
        self.assertEqual(current(), UNKNOWN)


class StampTest(Harness):
    """Le fichier écrit à la construction."""

    def test_ecrit_la_version_du_depot(self):
        self.repository("v0.6")
        path = write_stamp(self.directory)
        self.assertEqual(path.read_text(encoding="utf-8").strip(), "0.6")


if __name__ == "__main__":
    unittest.main()
