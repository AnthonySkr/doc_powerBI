"""
Le choix de la fenêtre, sans Windows et sans Power BI.

`finder.choose` ne touche à rien : il reçoit la liste des fenêtres du bureau et
désigne celle du rapport. C'est donc ici que se vérifie ce qui a longtemps
manqué — qu'une fenêtre ne portant que le nom du rapport, comme les versions
récentes de Power BI Desktop l'intitulent, soit bien reconnue.
"""

import sys
import unittest
from unittest.mock import patch

from src.gui_automator import finder
from src.gui_automator.finder import WindowInfo
from src.gui_automator.recorder import CaptureError

REPORT = "Suivi des ventes 2024"


def window(title: str, process: str = "", width: int = 1920, height: int = 1040) -> WindowInfo:
    return WindowInfo(
        handle=abs(hash((title, process))) % 100_000,
        title=title,
        process=process,
        width=width,
        height=height,
    )


class ChooseTest(unittest.TestCase):
    def test_finds_window_titled_with_the_report_alone(self):
        """Le cas qui échouait : le titre ne dit pas « Power BI Desktop »."""
        desktop = [
            window("Boîte de réception - Outlook", "OUTLOOK.EXE"),
            window(REPORT, "PBIDesktop.exe"),
        ]

        found = finder.choose(desktop)

        self.assertIsNotNone(found)
        self.assertEqual(REPORT, found.title)

    def test_finds_the_microsoft_store_build(self):
        found = finder.choose([window(REPORT, "PBIDesktopStore.exe")])

        self.assertEqual(REPORT, found.title)

    def test_process_name_case_does_not_matter(self):
        found = finder.choose([window(REPORT, "pbidesktop.exe")])

        self.assertEqual(REPORT, found.title)

    def test_falls_back_to_the_historic_title(self):
        """Processus illisible (Power BI en administrateur) : reste le titre."""
        found = finder.choose([window(f"{REPORT} - Power BI Desktop")])

        self.assertEqual(f"{REPORT} - Power BI Desktop", found.title)

    def test_ignores_other_applications(self):
        desktop = [
            window("Documentation Power BI - Word", "WINWORD.EXE"),
            window("config.yaml - Visual Studio Code", "Code.exe"),
        ]

        self.assertIsNone(finder.choose(desktop))

    def test_no_window_at_all(self):
        self.assertIsNone(finder.choose([]))

    def test_prefers_the_report_over_the_start_screen(self):
        """Au démarrage, Power BI porte deux fenêtres : la plus grande gagne."""
        splash = window("Power BI Desktop", "PBIDesktop.exe", width=520, height=320)
        report = window(REPORT, "PBIDesktop.exe")

        self.assertEqual(report, finder.choose([splash, report]))

    def test_prefers_a_titled_window_over_an_untitled_one(self):
        blank = window("", "PBIDesktop.exe", width=4000, height=4000)
        report = window(REPORT, "PBIDesktop.exe")

        self.assertEqual(report, finder.choose([blank, report]))

    def test_the_declared_fragment_picks_one_report_among_several(self):
        other = window("Marges par région", "PBIDesktop.exe", width=2560, height=1440)
        wanted = window(REPORT, "PBIDesktop.exe")

        self.assertEqual(wanted, finder.choose([other, wanted], hint="ventes 2024"))

    def test_a_generic_fragment_does_not_disqualify_a_report(self):
        """L'ancien réglage par défaut ne doit écarter aucune fenêtre."""
        report = window(REPORT, "PBIDesktop.exe")

        self.assertEqual(report, finder.choose([report], hint="Power BI Desktop"))

    def test_the_fragment_alone_can_find_a_window(self):
        """Ni processus lisible, ni titre historique : le fragment décide."""
        renamed = window(REPORT)

        self.assertEqual(renamed, finder.choose([renamed], hint=REPORT))
        self.assertIsNone(finder.choose([renamed]))


class MessageTest(unittest.TestCase):
    """Ce que l'utilisateur lit quand rien n'est trouvé."""

    def setUp(self):
        self.desktop = [window("Boîte de réception - Outlook", "OUTLOOK.EXE")]

    def test_lists_the_windows_it_saw(self):
        with self.assertRaises(CaptureError) as caught:
            self._locate(self.desktop)

        message = str(caught.exception)
        self.assertIn("introuvable", message)
        self.assertIn("Outlook", message)

    def test_recalls_the_declared_fragment(self):
        with self.assertRaises(CaptureError) as caught:
            self._locate(self.desktop, hint=REPORT)

        self.assertIn(REPORT, str(caught.exception))

    def _locate(self, desktop: list[WindowInfo], hint: str = "") -> WindowInfo:
        """`locate`, mais sur un bureau donné plutôt que sur celui de Windows."""
        with patch.object(finder, "visible_windows", lambda: desktop):
            return finder.locate(hint)


class VisibleWindowsTest(unittest.TestCase):
    def test_nothing_outside_windows(self):
        """Hors de Windows, l'énumération ne lève pas : elle ne trouve rien."""
        if sys.platform == "win32":
            self.skipTest("test du repli hors de Windows")
        self.assertEqual([], finder.visible_windows())


if __name__ == "__main__":
    unittest.main()
