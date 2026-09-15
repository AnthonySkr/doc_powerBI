"""
Une séance de capture, de bout en bout.

C'est le point d'entrée du module : choisir l'enregistreur, déduire le plan de
prises du rapport déjà lu, photographier page par page, ranger les images et
relever leur inventaire dans le `PowerBiMetadata`.

Page par page, prise par prise : montrer la page, calculer où chaque élément
atterrit à l'écran, capturer, ranger. Rien qui dépende de Power BI dans le
déroulé lui-même — l'enregistreur est reçu tout fait (voir `recorder.Recorder`),
ce qui permet d'éprouver la séance entière avec `fake`, sans Windows.

Une prise qui échoue n'emporte pas les autres. Une capture rate pour des
raisons ordinaires — un visuel hors écran, une page qui n'a pas fini de se
dessiner —, et une séance de trente captures dont une échoue vaut mieux
qu'aucune : le compte rendu dit lesquelles manquent, on relance sur celles-là.
"""

from dataclasses import dataclass, field, replace
from pathlib import Path

from core import console, selection
from core.config import DEFAULT_CAPTURES_DIR, DocConfig
from core.models import PowerBiMetadata, ReportPage
from gui_automator import plan as capture_plan
from gui_automator.desktop import DesktopOptions, DesktopRecorder
from gui_automator.fake import FakeRecorder
from gui_automator.geometry import Rect, fit, place
from gui_automator.library import CaptureLibrary
from gui_automator.plan import PagePlan, Shot
from gui_automator.recorder import CaptureError, Recorder

__all__ = [
    "CaptureLog",
    "CaptureOptions",
    "calibrate",
    "capture",
    "captures_dir",
    "describe_plan",
    "recorder_for",
    "run_session",
    "shot_plan",
]


@dataclass(frozen=True)
class CaptureOptions:
    """Ce que le lancement demande à la séance de capture."""

    # Des rectangles unis, sans ouvrir Power BI : éprouve la chaîne entière.
    fake: bool = False
    # Changer de page à la main : plus lent, mais jamais pris en défaut.
    manual_pages: bool = False
    # Capturer tout le rapport, sans suivre ce que le plan retient.
    every_visual: bool = False
    # Ne capturer que les pages / prises dont le nom contient ce fragment.
    page: str = ""
    shot: str = ""


@dataclass
class CaptureLog:
    """Ce que la séance a produit, et ce qu'elle n'a pas pu produire."""

    written: list[Path] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)

    def summary(self) -> str:
        taken = f"{len(self.written)} capture(s) prise(s)"
        return f"{taken}, {len(self.skipped)} écartée(s)" if self.skipped else taken

    def details(self) -> list[str]:
        return [f"{name} — {reason}" for name, reason in self.skipped]


# ─────────────────────────────────────────────────────────────
#  Préparer
# ─────────────────────────────────────────────────────────────


def captures_dir(metadata: PowerBiMetadata, config: DocConfig) -> Path:
    """Dossier des images déclaré par le plan, à côté du projet."""
    declared = str(config.capture.get("directory") or DEFAULT_CAPTURES_DIR)
    return metadata.project_dir / declared


def shot_plan(
    metadata: PowerBiMetadata, config: DocConfig, options: CaptureOptions
) -> list[PagePlan]:
    """
    Plan de capture, restreint à ce que le lancement demande.

    Par défaut, seules les pages et les prises que le document retient :
    capturer ce que le plan écarte donnerait des images qui n'apparaîtraient
    nulle part.
    """
    report = metadata.report
    pages = report.pages if options.every_visual else _documented(report.pages, config)
    plans = capture_plan.build(pages)
    return capture_plan.only(plans, page=options.page, shot=options.shot)


def _documented(pages: list[ReportPage], config: DocConfig) -> list[ReportPage]:
    """Pages et visuels que le document retient, groupes organisés."""
    kept = selection.filter_pages(pages, config)
    for page in kept:
        selection.organize_page(page, config)
    return kept


def recorder_for(config: DocConfig, options: CaptureOptions) -> Recorder:
    """L'enregistreur que le lancement demande : le vrai, ou celui qui simule."""
    if options.fake:
        console.warn("Captures factices : rectangles unis, Power BI n'est pas ouvert")
        return FakeRecorder()

    desktop = DesktopOptions.from_plan(config.capture)
    if options.manual_pages:
        desktop = replace(desktop, manual_pages=True)
    return DesktopRecorder(desktop)


def describe_plan(plans: list[PagePlan], library: CaptureLibrary) -> None:
    """Annonce ce qui va être capturé, page par page."""
    for page in plans:
        console.info(f"{page.title} — canevas {page.canvas.width:g} × {page.canvas.height:g}")
        for shot in page.shots:
            console.detail(f"{shot.kind:6} {shot.title} · {_placement(shot)}")

    console.blank()
    console.done(f"{capture_plan.count(plans)} prise(s) prévue(s)")
    existing = library.existing()
    if existing:
        console.done(f"{len(existing)} capture(s) déjà dans le dossier")


def _placement(shot: Shot) -> str:
    if not shot.is_placed:
        return "place non déclarée — écartée"
    area = shot.area
    return f"{area.width:g} × {area.height:g} en ({area.left:g}, {area.top:g})"


# ─────────────────────────────────────────────────────────────
#  Capturer
# ─────────────────────────────────────────────────────────────


def capture(
    metadata: PowerBiMetadata,
    config: DocConfig,
    options: CaptureOptions | None = None,
    directory: Path | None = None,
) -> CaptureLog:
    """
    Photographie les visuels du rapport et enrichit `metadata.captures`.

    Retourne le bilan de la séance. Lève `CaptureError` si rien n'a pu être
    mis en route — Power BI fermé, outils absents.
    """
    options = options or CaptureOptions()
    library = CaptureLibrary(directory or captures_dir(metadata, config))
    plans = shot_plan(metadata, config, options)

    console.field("Captures", str(library.directory))
    describe_plan(plans, library)
    if not capture_plan.count(plans):
        console.warn("Aucune prise à effectuer — rien à capturer dans ce rapport.")
        return CaptureLog()

    log = run_session(plans, recorder_for(config, options), library)
    console.blank()
    console.done(log.summary())
    for line in log.details():
        console.detail(line)

    _inventory(metadata, library, plans)
    return log


def _inventory(metadata: PowerBiMetadata, library: CaptureLibrary, plans: list[PagePlan]) -> None:
    """
    Relève les images présentes sur le disque, pour que le document les trouve.

    L'inventaire est pris sur le dossier plutôt que sur le bilan de la séance :
    une image déposée à la main compte autant qu'une capture du script, et
    c'est exactement ce qu'on veut.
    """
    for page in plans:
        for shot in page.shots:
            found = library.find(page.name, shot.name)
            if found:
                relative = found.relative_to(metadata.project_dir)
                metadata.captures.setdefault(page.name, {})[shot.name] = str(relative)


def run_session(plans: list[PagePlan], recorder: Recorder, library: CaptureLibrary) -> CaptureLog:
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


# ─────────────────────────────────────────────────────────────
#  Régler le cadrage
# ─────────────────────────────────────────────────────────────


def calibrate(config: DocConfig, directory: Path) -> None:
    """
    Écrit la fenêtre entière et ce que l'outil croit être le canevas.

    Régler les marges à l'aveugle est impossible : elles dépendent de la
    version de Power BI, de la taille de l'écran et des volets ouverts. Les
    deux images se regardent côte à côte, et disent quoi corriger.
    """
    library = CaptureLibrary(directory)
    recorder = recorder_for(config, CaptureOptions())
    if not isinstance(recorder, DesktopRecorder):
        raise CaptureError("Le calibrage ne concerne que la capture réelle.")

    recorder.start()
    try:
        frame = recorder.window_frame()
        canvas = recorder.viewport()
        console.info(f"Fenêtre : {_box(frame)}")
        console.info(f"Canevas : {_box(canvas)}")
        written = [
            library.write("_calibrage", "fenetre", recorder.grab(frame.rounded())),
            library.write("_calibrage", "canevas", recorder.grab(canvas.rounded())),
        ]
    finally:
        recorder.stop()

    console.blank()
    for path in written:
        console.done(str(path.relative_to(library.directory)))
    console.field("Dossier", str(written[0].parent))
    console.note("`canevas.png` doit tenir le rapport entier, sans ruban ni volets.")
    console.note("Ajustez `capture.window` du plan, puis relancez.")


def _box(area: Rect) -> str:
    return f"{area.width:g} × {area.height:g} en ({area.left:g}, {area.top:g})"
