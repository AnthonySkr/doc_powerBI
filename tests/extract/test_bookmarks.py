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
from src.gui_automator import plan as capture_plan
from src.gui_automator.capturer import run_session
from src.gui_automator.fake import FakeRecorder
from src.gui_automator.library import CaptureLibrary
from src.pbi_extractor.report import parse_report
from src.pbi_extractor.report.bookmarks import load_bookmarks

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


def bookmark(name: str, title: str, hidden: dict[str, bool], targets: list[str]) -> dict:
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
            "sections": {PAGE: {"visualContainers": containers}},
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
    for name, target, x in (("b1", "secteur", 0), ("b2", "axe", 100)):
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
        report.visual(container(name, x, 510, 100, 40, button))

    for index, (name, title) in enumerate(
        (("chiffrage", "Chiffrage Devis"), ("evolution", "Evolution"), ("pipeline", "Pipeline"))
    ):
        hidden = {chart: rank != index for rank, chart in enumerate(CHARTS)}
        report.bookmark(bookmark(name, title, hidden, CHARTS))
    report.bookmark(bookmark("secteur", "Secteur", {"t1": False, "t2": True}, ["t1", "t2"]))
    report.bookmark(bookmark("axe", "Axe", {"t1": True, "t2": False}, ["t1", "t2"]))
    report.write(
        os.path.join(report.bookmarks, "bookmarks.json"),
        {
            "items": [
                {"name": "graphs", "children": ["chiffrage", "evolution", "pipeline"]},
                {"name": "secteur"},
                {"name": "axe"},
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
            ],
        )

    def test_ce_qui_est_masque_a_l_ouverture(self):
        self.assertEqual(self.page.hidden_by_default, {CHARTS[1], CHARTS[2], "t2"})

    def test_un_signet_ne_touche_que_ses_cibles(self):
        """Le segment, déclaré masqué mais hors cible, reste visible."""
        self.assertEqual(self.views["evolution"].hidden, {CHARTS[0], CHARTS[2], "t2"})

    def test_la_case_du_navigateur_suit_le_rang_du_signet(self):
        """Navigateur vertical de 300 de haut, ramené à la page : trois cases de 100."""
        self.assertEqual(self.views["chiffrage"].trigger, (400, 200, 90, 100))
        self.assertEqual(self.views["pipeline"].trigger, (400, 400, 90, 100))

    def test_un_bouton_a_action_signet_se_vise_en_entier(self):
        self.assertEqual(self.views["axe"].trigger, (100, 510, 100, 40))


class PlanWithBookmarksTest(unittest.TestCase):
    """Chaque visuel superposé est pris une fois, sous le signet qui le montre."""

    def setUp(self):
        report = sample()
        self.addCleanup(shutil.rmtree, report.root, ignore_errors=True)
        with console.silenced():
            self.plan = capture_plan.build(parse_report(report.root).pages)[0]
        self.shots = {shot.name: shot for shot in self.plan.shots}

    def test_chaque_graphique_sous_son_signet(self):
        views = [self.shots[chart].view for chart in CHARTS]
        self.assertEqual(views, ["chiffrage", "evolution", "pipeline"])
        self.assertEqual((self.shots["t1"].view, self.shots["t2"].view), ("secteur", "axe"))

    def test_ce_que_les_signets_ne_touchent_pas_se_prend_tel_quel(self):
        self.assertEqual(self.shots["slicer"].view, "")
        self.assertEqual(self.plan.shots[0].view, "")  # la page

    def test_la_page_est_rendue_telle_qu_elle_s_ouvre(self):
        """Chiffrage remet les graphiques, Secteur les tableaux : il faut les deux."""
        self.assertEqual(self.plan.restore, ["chiffrage", "secteur"])

    def test_la_seance_applique_chaque_signet_puis_rend_la_page(self):
        with tempfile.TemporaryDirectory() as directory, console.silenced():
            recorder = FakeRecorder()
            log = run_session([self.plan], recorder, CaptureLibrary(directory))
        self.assertEqual(
            recorder.bookmarks,
            [
                *("Chiffrage Devis", "Evolution", "Pipeline", "Secteur", "Axe"),
                *("Chiffrage Devis", "Secteur"),  # la page rendue telle qu'elle s'ouvre
            ],
        )
        self.assertEqual(log.skipped, [])


if __name__ == "__main__":
    unittest.main()
