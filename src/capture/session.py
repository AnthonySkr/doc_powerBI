"""
Le déroulé d'une séance de capture.

Page par page, prise par prise : montrer la page, calculer où chaque élément
atterrit à l'écran, capturer, ranger. Rien de plus — et rien qui dépende de
Power BI : l'enregistreur est reçu tout fait (voir `recorder.Recorder`).

Une prise qui échoue n'emporte pas les autres. Une capture rate pour des
raisons ordinaires — un visuel hors écran, une page qui n'a pas fini de se
dessiner —, et une séance de trente captures dont une échoue vaut mieux
qu'aucune : le compte rendu dit lesquelles manquent, on relance sur celles-là.
"""

from dataclasses import dataclass, field

from src import console
from src.capture.geometry import Rect, fit, place
from src.capture.library import CaptureLibrary
from src.capture.plan import PagePlan, Shot
from src.capture.recorder import CaptureError, Recorder

__all__ = ["CaptureLog", "run"]


@dataclass
class CaptureLog:
    """Ce que la séance a produit, et ce qu'elle n'a pas pu produire."""

    written: list[str] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)

    def summary(self) -> str:
        taken = f"{len(self.written)} capture(s) prise(s)"
        return f"{taken}, {len(self.skipped)} écartée(s)" if self.skipped else taken

    def details(self) -> list[str]:
        return [f"{name} — {reason}" for name, reason in self.skipped]


def run(plans: list[PagePlan], recorder: Recorder, library: CaptureLibrary) -> CaptureLog:
    """Déroule le plan de capture et retourne son bilan."""
    session = _Session(recorder, library)

    recorder.start()
    try:
        for page in plans:
            session.page(page)
    finally:
        # Power BI reste ouvert si l'utilisateur l'avait ouvert lui-même ;
        # l'enregistreur sait ce qu'il a lancé, et ne ferme que cela.
        recorder.stop()

    return session.log


class _Session:
    """L'enregistreur, le dossier et le bilan, le temps d'une séance."""

    def __init__(self, recorder: Recorder, library: CaptureLibrary):
        self.recorder = recorder
        self.library = library
        self.log = CaptureLog()

    def page(self, page: PagePlan) -> None:
        console.detail(f"{page.title} ({len(page.shots)} prise(s))")

        rendered = fit(page.canvas, self.recorder.show_page(page))
        if rendered.is_empty:
            self._skip(page.shots, "canevas non rendu à l'écran")
            return

        for shot in page.shots:
            self.shot(shot, page, rendered)

    def shot(self, shot: Shot, page: PagePlan, rendered: Rect) -> None:
        if not shot.is_placed:
            self._skip([shot], "place non déclarée par le rapport")
            return

        area = place(shot.area, page.canvas, rendered).rounded()
        if area.is_empty:
            self._skip([shot], "hors du canevas rendu")
            return

        try:
            image = self.recorder.grab(area)
        except CaptureError as e:
            self._skip([shot], str(e))
            return

        self.log.written.append(self.library.write(page.name, shot.name, image))

    def _skip(self, shots: list[Shot], reason: str) -> None:
        self.log.skipped += [(shot.title, reason) for shot in shots]
