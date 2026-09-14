"""
Automatisation de Power BI Desktop : des métadonnées aux images.

Ce module ne fait que piloter l'interface graphique et ranger des PNG. Il ne
lit pas le `.pbip` — les places des visuels lui viennent déjà lues — et
n'écrit aucun document.

    capturer.py   le point d'entrée : une séance de capture, de bout en bout
    geometry.py   du repère du rapport à celui de l'écran — du calcul pur
    plan.py       ce qu'il y a à capturer, déduit du rapport, sans rien ouvrir
    library.py    où vivent les images, et sous quel nom
    recorder.py   le contrat que remplit un preneur de captures
    fake.py       un preneur qui n'ouvre rien : des rectangles unis
    desktop.py    le vrai : Power BI Desktop, via pywinauto et mss (Windows)

Seul `desktop.py` a besoin de Windows et de Power BI. Tout le reste — y compris
une séance complète, avec `fake` — tourne partout, et c'est là que se vérifie
l'essentiel : le cadrage.

L'étape est **facultative** : sans elle, le document garde ses emplacements
réservés.
"""

from gui_automator.capturer import (
    CaptureLog,
    CaptureOptions,
    calibrate,
    capture,
    describe_plan,
    run_session,
    shot_plan,
)
from gui_automator.geometry import Rect, Size
from gui_automator.library import CaptureLibrary
from gui_automator.plan import PagePlan, Shot
from gui_automator.recorder import CaptureError, Recorder

__all__ = [
    "CaptureError",
    "CaptureLibrary",
    "CaptureLog",
    "CaptureOptions",
    "PagePlan",
    "Recorder",
    "Rect",
    "Shot",
    "Size",
    "calibrate",
    "capture",
    "describe_plan",
    "run_session",
    "shot_plan",
]
