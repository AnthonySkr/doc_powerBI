"""
Une séance de capture entière, sans Power BI ni écran.

C'est le test qui vaut pour la chaîne : l'enregistreur factice remplace le
pilotage de Power BI, et tout le reste — plan, cadrage, dossier, bilan — est le
code qui tournera pour de vrai. Ce qui n'est pas couvert ici se réduit à ce que
`desktop.py` fait : trouver la fenêtre, changer de page, photographier.
"""

import os
import shutil
import struct
import tempfile
import unittest

from src import console
from src.capture import plan as capture_plan
from src.capture.fake import FakeRecorder, solid_png
from src.capture.geometry import Rect
from src.capture.library import CaptureLibrary
from src.capture.recorder import CaptureError
from src.capture.session import run
from src.models.data_models import ReportPage, Visual


def visual(name: str, title: str, x=0.0, y=0.0, width=400.0, height=300.0) -> Visual:
    return Visual(
        id=name,
        visual_type="card",
        title=title,
        name=name,
        pos_x=x,
        pos_y=y,
        width=width,
        height=height,
    )


def page(*visuals: Visual, name="page_1", title="Ventes") -> ReportPage:
    built = ReportPage(name=name, display_name=title)
    built.visuals = list(visuals)
    built.ungrouped_visuals = list(visuals)
    return built


def _read(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def png_size(data: bytes) -> tuple[int, int]:
    """Dimensions lues dans l'en-tête IHDR."""
    return struct.unpack(">II", data[16:24])


class SessionTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.directory, ignore_errors=True)
        self.library = CaptureLibrary(self.directory)
        self.recorder = FakeRecorder(Rect(0, 0, 1280, 720))

    def _run(self, pages):
        with console.silenced():
            return run(capture_plan.build(pages), self.recorder, self.library)

    def test_une_image_par_prise(self):
        log = self._run([page(visual("v1", "CA"), visual("v2", "Marge"))])
        self.assertEqual(len(log.written), 2)
        self.assertEqual(log.skipped, [])

    def test_les_images_sont_rangees_par_page(self):
        self._run([page(visual("v1", "CA"))])
        self.assertEqual(self.library.existing(), [os.path.join("page_1", "v1.png")])

    def test_le_document_retrouve_une_capture_par_les_memes_identifiants(self):
        """Tout le contrat entre les deux moitiés du projet tient là-dedans."""
        self._run([page(visual("v1", "CA"))])
        self.assertTrue(self.library.find("page_1", "v1"))
        self.assertFalse(self.library.find("page_1", "v2"))

    def test_chaque_page_est_affichee_une_fois(self):
        self._run(
            [
                page(visual("v1", "CA"), name="p1"),
                page(visual("v2", "Marge"), name="p2"),
            ]
        )
        self.assertEqual(self.recorder.shown, ["p1", "p2"])

    def test_l_image_a_les_dimensions_du_cadrage(self):
        """Canevas 1280 × 720 rendu dans 1280 × 720 : échelle 1."""
        self._run([page(visual("v1", "CA", x=100, y=50, width=400, height=300))])
        image = _read(self.library.find("page_1", "v1"))
        self.assertEqual(png_size(image), (400, 300))

    def test_le_cadrage_suit_l_echelle_de_la_fenetre(self):
        self.recorder = FakeRecorder(Rect(0, 0, 2560, 1440))
        self._run([page(visual("v1", "CA", width=400, height=300))])
        image = _read(self.library.find("page_1", "v1"))
        self.assertEqual(png_size(image), (800, 600))


class ResilienceTest(unittest.TestCase):
    """Une prise ratée n'emporte pas la séance."""

    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.directory, ignore_errors=True)
        self.library = CaptureLibrary(self.directory)

    def _run(self, recorder, pages):
        with console.silenced():
            return run(capture_plan.build(pages), recorder, self.library)

    def test_un_visuel_sans_place_est_ecarte_et_nomme(self):
        log = self._run(
            FakeRecorder(),
            [page(visual("v1", "CA", width=0, height=0), visual("v2", "Marge"))],
        )
        self.assertEqual(len(log.written), 1)
        self.assertEqual(log.skipped[0][0], "CA")
        self.assertIn("place non déclarée", log.details()[0])

    def test_une_capture_qui_echoue_laisse_passer_les_suivantes(self):
        class Fragile(FakeRecorder):
            def grab(self, area):
                if not self.grabbed:
                    self.grabbed.append(area)
                    raise CaptureError("région hors écran")
                return super().grab(area)

        log = self._run(Fragile(), [page(visual("v1", "CA"), visual("v2", "Marge"))])
        self.assertEqual(len(log.written), 1)
        self.assertEqual(log.skipped, [("CA", "région hors écran")])

    def test_une_page_non_rendue_ecarte_ses_prises_sans_lever(self):
        log = self._run(FakeRecorder(Rect(0, 0, 0, 0)), [page(visual("v1", "CA"))])
        self.assertEqual(log.written, [])
        self.assertIn("canevas non rendu", log.details()[0])

    def test_l_enregistreur_est_referme_meme_apres_une_erreur(self):
        class Broken(FakeRecorder):
            stopped = False

            def show_page(self, page):  # noqa: ARG002
                raise RuntimeError("plantage du pilote")

            def stop(self):
                type(self).stopped = True

        recorder = Broken()
        with self.assertRaises(RuntimeError), console.silenced():
            run(capture_plan.build([page(visual("v1", "CA"))]), recorder, self.library)
        self.assertTrue(Broken.stopped)

    def test_le_bilan_se_lit(self):
        log = self._run(FakeRecorder(), [page(visual("v1", "CA", width=0))])
        self.assertIn("écartée", log.summary())


class SolidPngTest(unittest.TestCase):
    """Le PNG factice est un vrai PNG : Word devra pouvoir l'ouvrir."""

    def test_signature_et_dimensions(self):
        image = solid_png(120, 80, (255, 0, 0))
        self.assertEqual(image[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(png_size(image), (120, 80))

    def test_une_dimension_nulle_donne_quand_meme_une_image(self):
        self.assertEqual(png_size(solid_png(0, 0, (0, 0, 0))), (1, 1))

    def test_le_fichier_se_termine_par_iend(self):
        self.assertTrue(solid_png(4, 4, (0, 0, 0)).endswith(b"IEND\xaeB`\x82"))


if __name__ == "__main__":
    unittest.main()
