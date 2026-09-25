"""
Signets : ce que chacun montre, et où cliquer pour l'appliquer.

Le rapport éprouvé ici reprend celui qui a fait naître le module : trois
graphiques superposés qu'un navigateur de signets fait alterner, et deux
tableaux qu'échangent deux boutons.
"""

import json
import os
import shutil
import tempfile
import unittest

from src.core import console
from src.core.models import BookmarkControl, Visual
from src.gui_automator import plan as capture_plan
from src.gui_automator.capturer import run_session
from src.gui_automator.fake import FakeRecorder
from src.gui_automator.geometry import Rect
from src.gui_automator.library import CaptureLibrary
from src.pbi_extractor.report import parse_report
from src.pbi_extractor.report.bookmarks import _cell, load_bookmarks

PAGE = "389a7480ca3c71dcb0b1"
CHARTS = ["86d64bb9a10ab0805d2b", "7632a0a8c98bc05d800b", "681d9640999e002bd8ed"]


def literal(value: str) -> dict:
    return {"expr": {"Literal": {"Value": value}}}


def container(name: str, x, y, width, height, visual: dict, **extra) -> dict:
    return {
        "name": name,
        "position": {"x": x, "y": y, "width": width, "height": height},
        "visual": visual,
        **extra,
    }


def bookmark(
    name: str, title: str, hidden: dict[str, bool], targets: list[str], groups=None
) -> dict:
    """Un signet tel que Power BI l'écrit, réduit à ce qui compte ici."""
    containers = {}
    for visual, is_hidden in hidden.items():
        node = {"visualType": "lineChart", "objects": {}}
        if is_hidden:
            node["display"] = {"mode": "hidden"}
        containers[visual] = {"singleVisual": node}
    # Un visuel déclaré, mais hors des cibles : le signet ne le touche pas.
    containers["slicer"] = {"singleVisual": {"display": {"mode": "hidden"}}}
    return {
        "displayName": title,
        "name": name,
        "options": {"applyOnlyToTargetVisuals": True, "targetVisualNames": targets},
        "explorationState": {
            "activeSection": PAGE,
            "sections": {
                PAGE: {
                    "visualContainers": containers,
                    "visualContainerGroups": {
                        group: {"isHidden": is_hidden}
                        for group, is_hidden in (groups or {}).items()
                    },
                }
            },
        },
    }


class ReportWithBookmarks:
    """Un dossier `.Report/` écrit sur le disque, le temps d'un test."""

    def __init__(self):
        self.root = tempfile.mkdtemp()
        definition = os.path.join(self.root, "definition")
        self.visuals = os.path.join(definition, "pages", PAGE, "visuals")
        self.bookmarks = os.path.join(definition, "bookmarks")
        os.makedirs(self.visuals)
        os.makedirs(self.bookmarks)
        self.write(os.path.join(definition, "pages", PAGE, "page.json"), {"displayName": "Main"})

    def write(self, path: str, data: dict) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)

    def visual(self, data: dict) -> None:
        folder = os.path.join(self.visuals, data["name"])
        os.makedirs(folder)
        self.write(os.path.join(folder, "visual.json"), data)

    def bookmark(self, data: dict) -> None:
        self.write(os.path.join(self.bookmarks, f"{data['name']}.bookmark.json"), data)


def sample() -> ReportWithBookmarks:
    report = ReportWithBookmarks()
    chart = {"visualType": "lineChart"}
    report.visual(container(CHARTS[0], 500, 200, 600, 300, chart))
    report.visual(container(CHARTS[1], 500, 200, 600, 300, chart, isHidden=True))
    report.visual(container(CHARTS[2], 500, 200, 600, 300, chart, isHidden=True))
    report.visual(container("slicer", 0, 0, 200, 50, {"visualType": "slicer"}))

    # Le navigateur, dans un groupe, placé depuis le coin de celui-ci.
    report.visual(
        {
            "name": "menu",
            "position": {"x": 400, "y": 200, "width": 90, "height": 300},
            "visualGroup": {"displayName": "Menu"},
        }
    )
    navigator = {
        "visualType": "bookmarkNavigator",
        "objects": {
            "layout": [{"properties": {"orientation": literal("1D")}}],
            "bookmarks": [{"properties": {"bookmarkGroup": literal("'graphs'")}}],
        },
    }
    report.visual(container("nav", 0, 0, 90, 300, navigator, parentGroupName="menu"))

    # Deux tableaux, échangés par deux boutons à action signet.
    report.visual(container("t1", 0, 550, 800, 150, {"visualType": "tableEx"}))
    report.visual(container("t2", 0, 550, 800, 150, {"visualType": "tableEx"}, isHidden=True))
    # Une fenêtre de filtres, masquée à l'ouverture : un bouton l'ouvre, une
    # croix la referme.
    report.visual(
        {
            "name": "modal",
            "position": {"x": 300, "y": 100, "width": 600, "height": 500},
            "visualGroup": {"displayName": "Filtres"},
            "isHidden": True,
        }
    )
    report.visual(
        container("f1", 20, 20, 200, 50, {"visualType": "slicer"}, parentGroupName="modal")
    )
    # Et un visuel masqué que seul un signet sans retour affiche.
    report.visual(container("orphan", 900, 0, 100, 100, {"visualType": "card"}, isHidden=True))

    buttons = (
        ("b1", "secteur", 0, 510),
        ("b2", "axe", 100, 510),
        ("b3", "open", 1200, 0),
        ("b4", "close", 1200, 50),
        ("b5", "lone", 1200, 100),
    )
    for name, target, x, y in buttons:
        button = {
            "visualType": "actionButton",
            "visualContainerObjects": {
                "visualLink": [
                    {
                        "properties": {
                            "show": literal("true"),
                            "type": literal("'Bookmark'"),
                            "bookmark": literal(f"'{target}'"),
                        }
                    }
                ]
            },
        }
        report.visual(container(name, x, y, 100, 40, button))

    for index, (name, title) in enumerate(
        (("chiffrage", "Chiffrage Devis"), ("evolution", "Evolution"), ("pipeline", "Pipeline"))
    ):
        hidden = {chart: rank != index for rank, chart in enumerate(CHARTS)}
        report.bookmark(bookmark(name, title, hidden, CHARTS))
    report.bookmark(bookmark("secteur", "Secteur", {"t1": False, "t2": True}, ["t1", "t2"]))
    report.bookmark(bookmark("axe", "Axe", {"t1": True, "t2": False}, ["t1", "t2"]))
    report.bookmark(bookmark("open", "Filtres", {}, ["modal"], groups={"modal": False}))
    report.bookmark(bookmark("close", "Fermer", {}, ["modal"], groups={"modal": True}))
    report.bookmark(bookmark("lone", "Seul", {"orphan": False}, ["orphan"]))
    report.write(
        os.path.join(report.bookmarks, "bookmarks.json"),
        {
            "items": [
                {"name": "graphs", "children": ["chiffrage", "evolution", "pipeline"]},
                {"name": "secteur"},
                {"name": "axe"},
                {"name": "open"},
                {"name": "close"},
                {"name": "lone"},
            ]
        },
    )
    return report


class BookmarksTest(unittest.TestCase):
    def setUp(self):
        self.report = sample()
        self.addCleanup(shutil.rmtree, self.report.root, ignore_errors=True)
        with console.silenced():
            self.page = parse_report(self.report.root).pages[0]
        self.views = {view.name: view for view in self.page.views}

    def test_ordre_et_groupes_du_volet_signets(self):
        read = load_bookmarks(self.report.root)
        self.assertEqual(
            [(b.name, b.group) for b in read],
            [
                ("chiffrage", "graphs"),
                ("evolution", "graphs"),
                ("pipeline", "graphs"),
                ("secteur", ""),
                ("axe", ""),
                ("open", ""),
                ("close", ""),
                ("lone", ""),
            ],
        )

    def test_ce_qui_est_masque_a_l_ouverture(self):
        self.assertEqual(
            self.page.hidden_by_default, {CHARTS[1], CHARTS[2], "t2", "modal", "f1", "orphan"}
        )

    def test_un_signet_ne_touche_que_ses_cibles(self):
        """Le segment, déclaré masqué mais hors cible, reste visible."""
        self.assertEqual(
            self.views["evolution"].hidden, {CHARTS[0], CHARTS[2], "t2", "modal", "f1", "orphan"}
        )

    def test_la_case_du_navigateur_suit_le_rang_du_signet(self):
        """Navigateur vertical de 300 de haut, ramené à la page : trois cases de 100."""
        self.assertEqual(self.views["chiffrage"].trigger, (400, 200, 90, 100))
        self.assertEqual(self.views["pipeline"].trigger, (400, 400, 90, 100))

    def test_un_navigateur_en_grille_plus_large_que_haut_tient_sur_une_ligne(self):
        grid = BookmarkControl(
            Visual(
                id="n",
                visual_type="bookmarkNavigator",
                title="",
                pos_x=32,
                pos_y=680,
                width=216,
                height=68,
            ),
            orientation="2",
        )
        self.assertEqual(_cell(grid, 1, 2), (140, 680, 108, 68))

    def test_un_signet_sans_bouton_dit_ce_qu_on_a_trouve(self):
        """Le signet « lone » a un bouton ; « close » aussi : aucun n'a de note."""
        self.assertEqual([view.note for view in self.page.views if view.note], [])

    def test_un_bouton_a_action_signet_se_vise_en_entier(self):
        self.assertEqual(self.views["axe"].trigger, (100, 510, 100, 40))


class PlanWithBookmarksTest(unittest.TestCase):
    """
    La page d'abord, telle qu'elle s'ouvre ; puis chaque visuel masqué, sous
    un signet qui le montre et qu'on sait défaire.
    """

    def setUp(self):
        report = sample()
        self.addCleanup(shutil.rmtree, report.root, ignore_errors=True)
        with console.silenced():
            self.plan = capture_plan.build(parse_report(report.root).pages)[0]
        self.shots = {shot.name: shot for shot in self.plan.shots}

    def test_ce_qui_est_visible_a_l_ouverture_se_prend_sans_rien_toucher(self):
        for name in (CHARTS[0], "t1", "slicer", "_page"):
            self.assertEqual(self.shots[name].view, "", name)

    def test_chaque_visuel_masque_sous_le_signet_qui_le_montre(self):
        views = [self.shots[name].view for name in (CHARTS[1], CHARTS[2], "t2", "f1")]
        self.assertEqual(views, ["evolution", "pipeline", "axe", "open"])

    def test_chaque_signet_est_aussitot_defait(self):
        undo = {view.name: view.undo for view in self.plan.views}
        self.assertEqual(undo["evolution"], ("chiffrage",))
        self.assertEqual(undo["axe"], ("secteur",))
        self.assertEqual(undo["open"], ("close",))  # la croix referme la fenêtre

    def test_un_signet_qu_on_ne_saurait_defaire_n_est_pas_applique(self):
        self.assertTrue(self.shots["orphan"].hidden)
        self.assertIn("aucun signet ne le défait", self.shots["orphan"].note)
        self.assertEqual(self.plan.view("lone").undo, ())

    def test_la_seance_applique_et_defait_chaque_signet_un_a_un(self):
        with tempfile.TemporaryDirectory() as directory, console.silenced():
            recorder = FakeRecorder()
            log = run_session([self.plan], recorder, CaptureLibrary(directory))
        self.assertEqual(
            recorder.bookmarks,
            [
                *("Evolution", "Chiffrage Devis"),
                *("Pipeline", "Chiffrage Devis"),
                *("Axe", "Secteur"),
                *("Filtres", "Fermer"),
            ],
        )
        self.assertEqual([title for title, _ in log.skipped], ["card (orphan)"])

    def test_le_canevas_est_remesure_apres_chaque_signet(self):
        """
        Un signet qui ouvre le volet Filtres rétrécit le canevas : la prise qui
        suit se cadre sur le nouveau, pas sur celui d'avant le clic.
        """

        class Narrowing(FakeRecorder):
            def measure(self, page):  # noqa: ARG002
                return Rect(0, 0, 960, 540)  # la moitié de 1920 × 1080

        plan = capture_plan.only([self.plan], shot=CHARTS[1])
        with tempfile.TemporaryDirectory() as directory, console.silenced():
            recorder = Narrowing()
            run_session(plan, recorder, CaptureLibrary(directory))
        # Le graphique est en (500, 200), 600 × 300, sur un canevas de 1280 × 720.
        self.assertEqual(recorder.grabbed[-1], Rect(375, 150, 450, 225))

    def test_tous_les_signets_cliquables_sont_au_plan(self):
        """Le calibrage les entoure tous, même ceux qu'aucune prise ne demande."""
        clickable = {view.name for view in self.plan.views if not view.trigger.is_empty}
        self.assertEqual(
            clickable,
            {"chiffrage", "evolution", "pipeline", "secteur", "axe", "open", "close", "lone"},
        )

    def test_sans_signets_rien_n_est_clique(self):
        bare = capture_plan.without_bookmarks(self.plan)
        self.assertEqual(bare.views, [])
        self.assertTrue(all(shot.view == "" for shot in bare.shots))
        self.assertTrue({shot.name: shot for shot in bare.shots}["t2"].hidden)


if __name__ == "__main__":
    unittest.main()
