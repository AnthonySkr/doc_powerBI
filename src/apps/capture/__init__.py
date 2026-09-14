"""
Application « capture » : du fichier d'échange aux images des visuels.

    python -m src.apps.capture

Elle lit ce que l'extraction a écrit, photographie les visuels dans Power BI
Desktop, range les images à côté du `.pbip`, et réécrit le fichier d'échange
enrichi de leur inventaire. Le document n'aura plus qu'à suivre les chemins.

    geometry.py   du repère du rapport à celui de l'écran — du calcul pur
    plan.py       ce qu'il y a à capturer, déduit du rapport, sans rien ouvrir
    library.py    où vivent les images, et sous quel nom
    recorder.py   le contrat que remplit un preneur de captures
    fake.py       un preneur qui n'ouvre rien : des rectangles unis
    desktop.py    le vrai : Power BI Desktop, via pywinauto et mss (Windows)
    session.py    le déroulé d'une séance, au-dessus de ces pièces

Seul `desktop.py` a besoin de Windows et de Power BI. Tout le reste — y compris
une séance complète, avec `fake` — tourne partout, et c'est là que se vérifie
l'essentiel : le cadrage.

Cette application est **facultative** dans la chaîne : sans elle, le document
garde ses emplacements réservés, comme avant.
"""

from src.apps.capture.geometry import Rect, Size
from src.apps.capture.library import DEFAULT_DIRECTORY, CaptureLibrary
from src.apps.capture.plan import PagePlan, Shot
from src.apps.capture.recorder import CaptureError, Recorder
from src.apps.capture.session import CaptureLog, run

__all__ = [
    "DEFAULT_DIRECTORY",
    "CaptureError",
    "CaptureLibrary",
    "CaptureLog",
    "PagePlan",
    "Recorder",
    "Rect",
    "Shot",
    "Size",
    "run",
]
