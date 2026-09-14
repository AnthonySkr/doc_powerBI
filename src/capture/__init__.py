"""
Captures d'écran des visuels d'un rapport Power BI.

Le document réserve la place des captures ; ce paquet les prend. Les deux ne se
connaissent que par un dossier de fichiers (voir `library`), ce qui laisse
libre de remplacer une image par une meilleure, prise autrement ou retouchée.

Le paquet est découpé pour que chaque morceau s'éprouve seul :

    geometry.py   du repère du rapport à celui de l'écran — du calcul pur
    plan.py       ce qu'il y a à capturer, déduit du rapport, sans rien ouvrir
    library.py    où vivent les images, et sous quel nom
    recorder.py   le contrat que remplit un preneur de captures
    fake.py       un preneur qui n'ouvre rien : des rectangles unis
    desktop.py    le vrai : Power BI Desktop, via pywinauto et mss (Windows)
    session.py    le déroulé d'une séance, au-dessus de ces pièces

    python -m src.capture <rapport.pbip>    l'outil, à lancer à la main

Seul `desktop.py` a besoin de Windows et de Power BI. Tout le reste — y compris
une séance complète, avec `fake` — tourne partout, et c'est là que se vérifie
l'essentiel : le cadrage.
"""

from src.capture.geometry import Rect, Size
from src.capture.library import DEFAULT_DIRECTORY, CaptureLibrary
from src.capture.plan import PagePlan, Shot
from src.capture.recorder import CaptureError, Recorder
from src.capture.session import CaptureLog, run

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
