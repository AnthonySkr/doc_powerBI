"""
L'outil de capture, à lancer seul.

    python -m src.capture rapport.pbip --plan        ce qui serait capturé
    python -m src.capture rapport.pbip --fake        la chaîne, sans Power BI
    python -m src.capture rapport.pbip --calibrate   régler le cadrage
    python -m src.capture rapport.pbip               les vraies captures

Il ne produit aucun document : il remplit un dossier d'images. C'est
volontaire — les deux moitiés du projet se testent séparément, et celle-ci se
met au point en regardant des PNG, pas des .docx.
"""

import argparse
import os
import sys
from dataclasses import dataclass

from src import __version__, console
from src.capture import plan as capture_plan
from src.capture.desktop import DesktopOptions, DesktopRecorder
from src.capture.fake import FakeRecorder
from src.capture.library import DEFAULT_DIRECTORY, CaptureLibrary
from src.capture.recorder import CaptureError, Recorder
from src.capture.session import run
from src.config import DEFAULT_CONFIG_PATH, DocConfig, load_config
from src.generators import filters
from src.models.data_models import PowerBIReport
from src.parsers.pbip import PbipProject
from src.parsers.report import parse_report


@dataclass
class Options:
    """Ce que la ligne de commande demande."""

    pbip_path: str
    config_path: str
    output_dir: str
    page: str
    shot: str
    show_plan: bool
    fake: bool
    calibrate: bool
    manual_pages: bool
    every_visual: bool


def main(argv: list[str] | None = None) -> int:
    """Point d'entrée de l'outil. Retourne le code de sortie."""
    options = _parse_args(argv)
    console.title("Captures Power BI", f"v{__version__}")

    config = _plan_config(options.config_path)
    try:
        report, library = _prepare(options, config)
    except CaptureError as e:
        console.error(str(e))
        return 1

    recorder = _recorder(options, config)
    if options.calibrate:
        return _run(lambda: _calibrating(recorder, library))

    plans = _shot_plan(report, config, options)
    if not capture_plan.count(plans):
        console.warn("Aucune prise à effectuer — rien à capturer dans ce rapport.")
        return 1

    _describe(plans, library)
    if options.show_plan:
        return 0

    return _run(lambda: _capture(plans, library, recorder))


def _run(step) -> int:
    """Exécute une étape de capture, une erreur d'exécution valant abandon."""
    try:
        return step()
    except CaptureError as e:
        console.blank()
        console.banner("Capture abandonnée", ok=False)
        console.error(str(e))
        return 1


def _calibrating(recorder: Recorder, library: CaptureLibrary) -> int:
    if not isinstance(recorder, DesktopRecorder):
        console.error("Le calibrage ne concerne que la capture réelle (retirez `--fake`).")
        return 1
    return _calibrate(recorder, library)


# ─────────────────────────────────────────────────────────────
#  Préparation
# ─────────────────────────────────────────────────────────────


def _plan_config(path: str) -> DocConfig:
    """
    Plan du document, dont vient la section `capture:`.

    Un plan illisible n'empêche pas de capturer : les valeurs par défaut
    suffisent, et tout le rapport est alors pris.
    """
    try:
        return load_config(path)
    except (FileNotFoundError, ValueError) as e:
        console.warn(f"Plan illisible ({e}) — réglages par défaut, rapport entier")
        return DocConfig()


def _prepare(options: Options, config: DocConfig) -> tuple[PowerBIReport, CaptureLibrary]:
    """Lit le rapport et choisit le dossier des captures."""
    if not os.path.isfile(options.pbip_path):
        raise CaptureError(f"Fichier introuvable : '{options.pbip_path}'")

    project = PbipProject(options.pbip_path)
    missing = project.missing()
    if missing:
        raise CaptureError(missing)

    report = parse_report(project.report_dir, report_name=project.name)  # type: ignore[arg-type]
    declared = str(config.capture.get("directory") or DEFAULT_DIRECTORY)
    directory = options.output_dir or os.path.join(project.directory, declared)

    console.blank()
    console.field("Rapport", project.name)
    console.field("Captures", directory)
    return report, CaptureLibrary(directory)


def _shot_plan(
    report: PowerBIReport, config: DocConfig, options: Options
) -> list[capture_plan.PagePlan]:
    """
    Plan de capture, restreint à ce que la ligne de commande demande.

    Par défaut, seules les pages et les prises que le document retient :
    capturer ce que le plan écarte donnerait des images qui n'apparaîtraient
    nulle part.
    """
    pages = report.pages if options.every_visual else _documented(report, config)
    plans = capture_plan.build(pages)
    return capture_plan.only(plans, page=options.page, shot=options.shot)


def _documented(report: PowerBIReport, config: DocConfig) -> list:
    """Pages et visuels que le document retient, groupes organisés."""
    pages = filters.filter_pages(report.pages, config)
    for page in pages:
        filters.organize_page(page, config)
    return pages


def _describe(plans: list[capture_plan.PagePlan], library: CaptureLibrary) -> None:
    """Annonce ce qui va être capturé, page par page."""
    console.step("Plan de capture", 1, 2)
    for page in plans:
        console.info(f"{page.title} — canevas {page.canvas.width:g} × {page.canvas.height:g}")
        for shot in page.shots:
            console.detail(f"{shot.kind:6} {shot.title} · {_placement(shot)}")

    console.blank()
    console.done(f"{capture_plan.count(plans)} prise(s) prévue(s)")
    existing = library.existing()
    if existing:
        console.done(f"{len(existing)} capture(s) déjà dans le dossier")


def _placement(shot: capture_plan.Shot) -> str:
    if not shot.is_placed:
        return "place non déclarée — écartée"
    area = shot.area
    return f"{area.width:g} × {area.height:g} en ({area.left:g}, {area.top:g})"


# ─────────────────────────────────────────────────────────────
#  Capture
# ─────────────────────────────────────────────────────────────


def _recorder(options: Options, config: DocConfig) -> Recorder:
    if options.fake:
        console.warn("Captures factices : rectangles unis, Power BI n'est pas ouvert")
        return FakeRecorder()

    desktop = DesktopOptions.from_plan(config.capture)
    if options.manual_pages:
        desktop = DesktopOptions(
            window_title=desktop.window_title,
            insets=desktop.insets,
            settle_seconds=desktop.settle_seconds,
            manual_pages=True,
        )
    return DesktopRecorder(desktop)


def _capture(plans: list, library: CaptureLibrary, recorder: Recorder) -> int:
    console.step("Captures", 2, 2)

    log = run(plans, recorder, library)
    console.blank()
    console.done(log.summary())
    for line in log.details():
        console.detail(line)

    console.blank()
    if not log.written:
        console.banner("Aucune capture produite", ok=False)
        return 1

    console.banner("Captures enregistrées")
    console.field("Dossier", library.directory)
    return 0


def _calibrate(recorder: DesktopRecorder, library: CaptureLibrary) -> int:
    """
    Écrit la fenêtre entière et ce que l'outil croit être le canevas.

    Régler les marges à l'aveugle est impossible : elles dépendent de la
    version de Power BI, de la taille de l'écran et des volets ouverts. Les
    deux images se regardent côte à côte, et disent quoi corriger.
    """
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
        console.done(os.path.relpath(path, library.directory))
    console.banner("Calibrage écrit")
    console.field("Dossier", os.path.dirname(written[0]))
    console.note("`canevas.png` doit tenir le rapport entier, sans ruban ni volets.")
    console.note("Ajustez `capture.window` du plan, puis relancez.")
    return 0


def _box(area) -> str:
    return f"{area.width:g} × {area.height:g} en ({area.left:g}, {area.top:g})"


# ─────────────────────────────────────────────────────────────
#  Ligne de commande
# ─────────────────────────────────────────────────────────────


def _parse_args(argv: list[str] | None) -> Options:
    parser = argparse.ArgumentParser(
        prog="python -m src.capture",
        description="Capture les visuels d'un rapport Power BI (.pbip) en images.",
    )
    parser.add_argument("pbip", help="Chemin vers le fichier .pbip")
    parser.add_argument(
        "-c", "--config", default=DEFAULT_CONFIG_PATH, help="Plan du document (YAML)"
    )
    parser.add_argument(
        "-o", "--output", default="", help="Dossier des captures (défaut : celui du plan)"
    )
    parser.add_argument("--page", default="", help="Ne capturer que les pages dont le nom contient")
    parser.add_argument(
        "--shot", default="", help="Ne capturer que les prises dont le nom contient"
    )
    parser.add_argument(
        "--plan", action="store_true", help="Afficher le plan de capture et s'arrêter là"
    )
    parser.add_argument(
        "--fake",
        action="store_true",
        help="Produire des images unies sans ouvrir Power BI (éprouve la chaîne)",
    )
    parser.add_argument(
        "--calibrate", action="store_true", help="Écrire la fenêtre et le canevas, pour les régler"
    )
    parser.add_argument(
        "--manual-pages",
        action="store_true",
        help="Changer de page à la main : le script attend avant chaque page",
    )
    parser.add_argument(
        "--all", action="store_true", help="Capturer tout le rapport, sans suivre le plan"
    )
    args = parser.parse_args(argv)

    return Options(
        pbip_path=args.pbip.strip().strip('"').strip("'"),
        config_path=args.config,
        output_dir=args.output,
        page=args.page,
        shot=args.shot,
        show_plan=args.plan,
        fake=args.fake,
        calibrate=args.calibrate,
        manual_pages=args.manual_pages,
        every_visual=args.all,
    )


if __name__ == "__main__":
    sys.exit(main())
