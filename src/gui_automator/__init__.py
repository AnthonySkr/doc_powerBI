"""
Automatisation de Power BI Desktop : des métadonnées aux images.

Il ne fait que piloter l'interface graphique et ranger des PNG : il ne lit pas
le `.pbip` — les places des visuels lui viennent déjà lues — et n'écrit aucun
document. L'étape est facultative ; sans elle, le document garde ses
emplacements réservés.

    capturer.py   le point d'entrée : une séance de capture, de bout en bout
    geometry.py   du repère du rapport à celui de l'écran — du calcul pur
    plan.py       ce qu'il y a à capturer, déduit du rapport, sans rien ouvrir
    library.py    où vivent les images, et sous quel nom
    canvas.py     où le canevas est rendu dans l'image — du calcul sur pixels
    png.py        écrire une image, sans bibliothèque d'images
    finder.py     laquelle des fenêtres du bureau est le rapport (Windows)
    recorder.py   le contrat que remplit un preneur de captures
    fake.py       un preneur qui n'ouvre rien : des rectangles unis
    desktop.py    le vrai : Power BI Desktop, via pywinauto et mss (Windows)

Seuls `desktop.py` et `finder.py` ont besoin de Windows et de Power BI. Tout
le reste — y compris une séance complète, avec `fake` — tourne partout, et
c'est là que se vérifie l'essentiel : le cadrage, et le choix de la fenêtre.
"""

from src.gui_automator.capturer import (
    CaptureLog,
    CaptureOptions,
    calibrate,
    capture,
    describe_plan,
    run_session,
    shot_plan,
)
from src.gui_automator.geometry import Rect, Size
from src.gui_automator.library import CaptureLibrary
from src.gui_automator.plan import PagePlan, Shot
from src.gui_automator.recorder import CaptureError, Recorder

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
