"""
Une séance de capture, de bout en bout : le plan, l'enregistreur, les images.

Une prise qui échoue n'emporte pas les autres. Une capture rate pour des
raisons ordinaires — un visuel hors écran, une page qui n'a pas fini de se
dessiner —, et une séance de trente captures dont une échoue vaut mieux
qu'aucune : le compte rendu dit lesquelles manquent, on relance sur celles-là.
"""

from dataclasses import dataclass, field, replace
from pathlib import Path

from src.core import console, selection
from src.core.config import DEFAULT_CAPTURES_DIR, DocConfig
from src.core.models import PowerBiMetadata, ReportPage
from src.gui_automator import canvas, png
from src.gui_automator import plan as capture_plan
from src.gui_automator.desktop import DesktopOptions, DesktopRecorder
from src.gui_automator.fake import FakeRecorder
from src.gui_automator.geometry import Rect, fit, place
from src.gui_automator.library import CaptureLibrary
from src.gui_automator.plan import PagePlan, Shot, View
from src.gui_automator.recorder import CaptureError, Recorder

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

# Couleurs des repères du calibrage : le canevas en rouge, les visuels en vert,
# et en bleu la zone que les marges déclarées désignent. Trois teintes
# franches, absentes des habillages de Power BI.
_CANVAS_MARK = (0xE8, 0x11, 0x23)
_VISUAL_MARK = (0x10, 0x7C, 0x10)
_DECLARED_MARK = (0x00, 0x78, 0xD4)
# Et en orange, là où le script cliquera pour appliquer chaque signet.
_TRIGGER_MARK = (0xF7, 0x63, 0x0C)


@dataclass(frozen=True)
class CaptureOptions:
    """Ce que le lancement demande à la séance. Voir les options de `main.py`."""

    fake: bool = False
    manual_pages: bool = False
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
    if not config.capture.get("bookmarks", True):
        plans = [capture_plan.without_bookmarks(plan) for plan in plans]
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
    """
    Annonce ce qui va être capturé, page par page.

    Le nom du fichier est dit avec chaque prise : c'est par lui que l'image se
    retrouve dans le dossier, une fois le document ouvert à côté.
    """
    for page in plans:
        console.info(f"{page.title} — canevas {page.canvas.width:g} × {page.canvas.height:g}")
        for view in [None, *page.views]:
            shots = page.shots_for(view.name if view else "")
            if view is not None and shots:
                console.detail(f"signet « {view.title} » · {_trigger(view)}")
            for shot in shots:
                file = library.path(page.name, shot.name).name
                console.detail(f"{shot.kind:6} {shot.title} · {file} · {_placement(shot)}")
            for name in view.undo if view is not None and shots else ():
                undo = page.view(name)
                console.detail(f"puis signet « {undo.title} » · {_trigger(undo)}")

    console.blank()
    console.done(f"{capture_plan.count(plans)} prise(s) prévue(s)")
    existing = library.existing()
    if existing:
        console.done(f"{len(existing)} capture(s) déjà dans le dossier")


def _trigger(view: View) -> str:
    if view.trigger.is_empty:
        return "aucun bouton n'y mène — il sera demandé"
    center = _center(view.trigger)
    return f"clic en ({center.left:g}, {center.top:g})"


def _center(area: Rect) -> Rect:
    """Le point central d'une zone, en rectangle d'un pixel."""
    return Rect(round(area.left + area.width / 2), round(area.top + area.height / 2), 1, 1)


def _placement(shot: Shot) -> str:
    if shot.hidden:
        return f"{shot.note} — écarté"
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
            self._skip(page.shots, "page non affichée, ou canevas non rendu à l'écran")
            return

        for shot in page.shots_for(""):
            self.shot(shot, page, rendered)

        # Puis, un à un, les visuels masqués : leur signet, leurs prises, et
        # aussitôt ce qui le défait — la page revient comme à l'ouverture
        # avant le signet suivant.
        for index, view in enumerate(page.views):
            shots = page.shots_for(view.name)
            if not shots:
                continue
            shown = self._apply(view, page, rendered)
            if shown is None:
                self._skip(shots, f"signet « {view.title} » non appliqué")
                continue
            for shot in shots:
                self.shot(shot, page, shown)
            restored = self._undo(view, page, shown)
            if restored is None:
                later = page.views[index + 1 :]
                rest = [shot for other in later for shot in page.shots_for(other.name)]
                self._skip(rest, f"page non rendue après le signet « {view.title} »")
                return
            rendered = restored

    def _undo(self, view: View, page: PagePlan, rendered: Rect) -> Rect | None:
        """Défait le signet : la page comme à l'ouverture, pour la suite."""
        for name in view.undo:
            undo = page.view(name)
            if undo is None:
                continue
            rendered = self._apply(undo, page, rendered, undo=True)
            if rendered is None:
                return None
        return rendered

    def _apply(self, view: View, page: PagePlan, rendered: Rect, undo: bool = False) -> Rect | None:
        """
        Applique le signet, et retourne où le canevas est rendu ensuite.

        Mesuré à nouveau, et non repris d'avant : un signet peut ouvrir ou
        replier le volet Filtres, le canevas se redimensionne alors, et les
        prises cadrées sur l'ancien tomberaient à côté. `None` si le signet
        n'a pas été appliqué, ou si le canevas ne se retrouve plus.
        """
        trigger = view.trigger
        target = Rect(0, 0, 0, 0) if trigger.is_empty else place(trigger, page.canvas, rendered)
        if not self.recorder.apply_bookmark(view.title, target.rounded(), rendered, undo):
            return None
        measured = fit(page.canvas, self.recorder.measure(page, rendered))
        return None if measured.is_empty else measured

    def shot(self, shot: Shot, page: PagePlan, rendered: Rect) -> None:
        if shot.hidden:
            self._skip([shot], shot.note)
            return
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


def calibrate(config: DocConfig, directory: Path, plans: list[PagePlan] | None = None) -> None:
    """
    Écrit ce que le script voit de la fenêtre, et où il croit que tout se trouve.

    Trois images dans `_calibrage/` :

        fenetre.png   la fenêtre entière, telle qu'elle est à l'écran
        canevas.png   ce que le script retient comme canevas
        reperes.png   la fenêtre, le canevas et chaque visuel entourés

    C'est `reperes.png` qui répond à la question « pourquoi mes captures sont
    mal cadrées » : si les rectangles tombent à côté des visuels, le décalage
    se lit sur l'image, et il se lit *où*. Les repères sont ceux de la
    première page du plan — affichez-la avant de lancer le calibrage.
    """
    library = CaptureLibrary(directory)
    recorder = recorder_for(config, CaptureOptions())
    if not isinstance(recorder, DesktopRecorder):
        raise CaptureError("Le calibrage ne concerne que la capture réelle.")

    page = (plans or [None])[0]
    recorder.start()
    try:
        written = _calibration_images(recorder, library, page)
        verdict = _verdict(recorder, page)
    finally:
        recorder.stop()

    console.blank()
    for path in written:
        console.done(str(path.relative_to(library.directory)))
    console.field("Dossier", str(written[0].parent))
    for line in verdict:
        console.note(line)


def _calibration_images(
    recorder: DesktopRecorder, library: CaptureLibrary, page: PagePlan | None
) -> list[Path]:
    """Les trois images du calibrage, écrites dans le dossier des captures."""
    frame = recorder.window_frame()
    rendered = _rendered_canvas(recorder, page)
    console.info(f"Fenêtre : {frame.describe()}")
    console.info(f"Zone utile : {recorder.client_frame().describe()}")
    console.info(f"Marges déclarées : {recorder.viewport().describe()}")
    console.info(f"Canevas retenu : {rendered.describe()}")

    written = [
        library.write("_calibrage", "fenetre", recorder.grab(frame.rounded())),
        library.write("_calibrage", "canevas", recorder.grab(rendered.rounded())),
    ]
    marked = _marked_window(recorder, frame, rendered, page)
    if marked is not None:
        written.append(library.write("_calibrage", "reperes", marked))
    return written


def _rendered_canvas(recorder: DesktopRecorder, page: PagePlan | None) -> Rect:
    """Où le canevas est rendu : détecté si l'on sait quoi chercher."""
    if page is None:
        return recorder.viewport()
    return fit(page.canvas, recorder.canvas_area(page.canvas))


def _marked_window(
    recorder: DesktopRecorder, frame: Rect, rendered: Rect, page: PagePlan | None
) -> bytes | None:
    """
    La fenêtre, avec le canevas et les visuels entourés. Sans page, rien.

    Trois couleurs, et la troisième compte : les visuels en vert, le canevas
    retenu en rouge, et en bleu la zone que les marges déclarées désignent.
    Voir les deux dernières côte à côte, c'est voir d'un coup si le cadrage
    vient de l'image ou d'un réglage — et de combien ce réglage se trompe.
    """
    image = recorder.image(frame) if page is not None else None
    if image is None:
        return None

    def local(area: Rect) -> Rect:
        """Du repère de l'écran à celui de l'image de la fenêtre."""
        return area.moved(-frame.left, -frame.top)

    areas = [
        local(place(shot.area, page.canvas, rendered))
        for shot in page.shots
        if shot.is_placed and not shot.hidden and shot.kind != capture_plan.PAGE
    ]
    triggers = [
        local(place(view.trigger, page.canvas, rendered))
        for view in page.views
        if not view.trigger.is_empty
    ]
    drawn = canvas.outline(image, areas, _VISUAL_MARK)
    for marks, color, width in (
        (triggers, _TRIGGER_MARK, 3),
        ([local(recorder.viewport())], _DECLARED_MARK, 2),
        ([local(rendered)], _CANVAS_MARK, 3),
    ):
        drawn = canvas.outline(canvas.Image(image.width, image.height, drawn), marks, color, width)
    return png.encode(image.width, image.height, drawn)


def _verdict(recorder: DesktopRecorder, page: PagePlan | None) -> list[str]:
    """
    Ce qu'il faut retenir du calibrage, en quelques lignes.

    D'où vient le cadrage — de l'image ou des marges déclarées —, ce qu'il
    reste à vérifier à l'œil, et, si les marges ne servaient qu'à retomber
    dessus, celles qui conviendraient à cet écran-ci.
    """
    lines = ["`canevas.png` doit tenir le rapport entier, sans ruban ni volets."]
    if page is None:
        lines.append("Aucune page au plan : le canevas n'a pas été cherché, et le cadrage")
        lines.append("montré est celui des marges déclarées. Reprenez le calibrage sur un")
        lines.append("rapport dont au moins une page est documentée.")
        return lines

    lines.append(f"`reperes.png` entoure les visuels de « {page.title} » — ils doivent")
    lines.append("tomber dessus. Le cadre rouge est le canevas retenu, le bleu ce que")
    lines.append("`capture.window` désigne, et le vert chaque visuel à capturer.")
    if page.views:
        lines.append("En orange, le bouton de chaque signet : le clic vise son centre.")
        unreachable = [view.title for view in page.views if view.trigger.is_empty]
        if unreachable:
            lines.append(f"Sans bouton repéré sur la page : {', '.join(unreachable)}.")

    measured = recorder.measured_canvas(page.canvas)
    if measured is None:
        lines.append("Canevas non reconnu dans l'image : le cadrage vient des marges")
        lines.append("déclarées, à régler dans `capture.window` du plan jusqu'à ce que le")
        lines.append("cadre bleu tienne le rapport entier.")
        return lines

    lines.append("Canevas reconnu dans l'image : les marges déclarées ne servent plus.")
    lines.append("Pour qu'elles retombent dessus si la reconnaissance échouait un jour :")
    lines.append(_suggested_insets(recorder.client_frame(), measured))
    return lines


def _suggested_insets(client: Rect, measured: Rect) -> str:
    """Les marges qui, sur cet écran, désignent exactement le canevas mesuré."""
    return (
        f"inset_left: {round(measured.left - client.left)}, "
        f"inset_top: {round(measured.top - client.top)}, "
        f"inset_right: {round(client.right - measured.right)}, "
        f"inset_bottom: {round(client.bottom - measured.bottom)}"
    )
