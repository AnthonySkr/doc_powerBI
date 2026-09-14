"""
L'application « capture », à lancer seule.

    python -m src.apps.capture --plan        ce qui serait capturé
    python -m src.apps.capture --fake        la chaîne, sans Power BI
    python -m src.apps.capture --calibrate   régler le cadrage
    python -m src.apps.capture               les vraies captures

Elle lit le fichier d'échange de l'extraction, remplit un dossier d'images, et
réécrit le fichier d'échange avec leur inventaire. Elle ne produit aucun
document : cette moitié-là se met au point en regardant des PNG, pas des .docx.

Par défaut, le fichier consommé est supprimé — c'est le tapis roulant de la
chaîne. `--keep` le laisse en place, pour relancer sans refaire l'extraction.
"""

import argparse
import os
import sys
from dataclasses import dataclass, replace

from src import __version__
from src.apps.capture import plan as capture_plan
from src.apps.capture.desktop import DesktopOptions, DesktopRecorder
from src.apps.capture.fake import FakeRecorder
from src.apps.capture.library import DEFAULT_DIRECTORY, CaptureLibrary
from src.apps.capture.recorder import CaptureError, Recorder
from src.apps.capture.session import run
from src.shared import console, selection
from src.shared.config import DEFAULT_CONFIG_PATH, DocConfig, load_config
from src.shared.exchange import Exchange, ExchangeError, discard, read, write
from src.shared.models import PowerBIReport

# Rang de cette application dans la chaîne : ce qu'elle lit, ce qu'elle écrit.
INPUT_NAME = "1-rapport.json"
OUTPUT_NAME = "2-captures.json"


@dataclass
class Options:
    """Ce que la ligne de commande demande."""

    input_path: str
    output_path: str
    config_path: str
    captures_dir: str
    page: str
    shot: str
    show_plan: bool
    fake: bool
    calibrate: bool
    manual_pages: bool
    every_visual: bool
    keep_input: bool


def main(argv: list[str] | None = None) -> int:
    """Point d'entrée de l'application. Retourne le code de sortie."""
    options = _parse_args(argv)
    console.title("Captures Power BI", f"v{__version__}")

    try:
        exchange = read(options.input_path)
    except ExchangeError as e:
        console.error(str(e))
        return 1

    config = _plan_config(options.config_path)
    library = CaptureLibrary(_captures_dir(options, exchange, config))

    console.blank()
    console.field("Rapport", exchange.report.name)
    console.field("Captures", library.directory)

    recorder = _recorder(options, config)
    if options.calibrate:
        return _guarded(lambda: _calibrating(recorder, library))

    plans = _shot_plan(exchange.report, config, options)
    if not capture_plan.count(plans):
        console.warn("Aucune prise à effectuer — rien à capturer dans ce rapport.")
        return 1

    _describe(plans, library)
    if options.show_plan:
        return 0

    return _guarded(lambda: _capture(plans, library, recorder, exchange, options))


def _guarded(step) -> int:
    """Exécute une étape, une erreur d'exécution valant abandon."""
    try:
        return step()
    except CaptureError as e:
        console.blank()
        console.banner("Capture abandonnée", ok=False)
        console.error(str(e))
        return 1


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


def _captures_dir(options: Options, exchange: Exchange, config: DocConfig) -> str:
    """Dossier des images : celui demandé, sinon celui du plan, à côté du .pbip."""
    if options.captures_dir:
        return options.captures_dir
    declared = str(config.capture.get("directory") or DEFAULT_DIRECTORY)
    return os.path.join(os.path.dirname(exchange.source), declared)


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
    pages = selection.filter_pages(report.pages, config)
    for page in pages:
        selection.organize_page(page, config)
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
        desktop = replace(desktop, manual_pages=True)
    return DesktopRecorder(desktop)


def _capture(
    plans: list, library: CaptureLibrary, recorder: Recorder, exchange: Exchange, options: Options
) -> int:
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

    _hand_over(exchange, library, plans, options)
    console.banner("Captures enregistrées")
    console.field("Dossier", library.directory)
    console.field("Fichier", options.output_path)
    return 0


def _hand_over(exchange: Exchange, library: CaptureLibrary, plans: list, options: Options) -> None:
    """
    Écrit le fichier d'échange pour l'application suivante.

    L'inventaire est relevé sur le disque plutôt que sur le bilan de la séance :
    une image déposée à la main dans le dossier compte autant qu'une capture du
    script, et c'est exactement ce qu'on veut.
    """
    project_dir = os.path.dirname(exchange.source)
    for page in plans:
        for shot in page.shots:
            found = library.find(page.name, shot.name)
            if found:
                exchange.captures.setdefault(page.name, {})[shot.name] = os.path.relpath(
                    found, project_dir
                )

    exchange.produced_by = "capture"
    write(exchange, options.output_path)
    # Le tapis roulant avance : ce qui a été consommé disparaît.
    if not options.keep_input:
        discard(options.input_path)


def _calibrating(recorder: Recorder, library: CaptureLibrary) -> int:
    if not isinstance(recorder, DesktopRecorder):
        console.error("Le calibrage ne concerne que la capture réelle (retirez `--fake`).")
        return 1
    return _calibrate(recorder, library)


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
        prog="python -m src.apps.capture",
        description="Photographie les visuels d'un rapport Power BI déjà extrait.",
    )
    parser.add_argument(
        "-i", "--input", default=INPUT_NAME, help=f"Fichier d'échange lu (défaut : {INPUT_NAME})"
    )
    parser.add_argument(
        "-o", "--output", default="", help=f"Fichier d'échange écrit (défaut : {OUTPUT_NAME})"
    )
    parser.add_argument(
        "-c", "--config", default=DEFAULT_CONFIG_PATH, help="Plan du document (YAML)"
    )
    parser.add_argument(
        "-d", "--captures", default="", help="Dossier des images (défaut : celui du plan)"
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
    parser.add_argument(
        "--keep", action="store_true", help="Ne pas supprimer le fichier d'échange consommé"
    )
    args = parser.parse_args(argv)

    output = args.output or os.path.join(os.path.dirname(args.input), OUTPUT_NAME)
    return Options(
        input_path=args.input,
        output_path=output,
        config_path=args.config,
        captures_dir=args.captures,
        page=args.page,
        shot=args.shot,
        show_plan=args.plan,
        fake=args.fake,
        calibrate=args.calibrate,
        manual_pages=args.manual_pages,
        every_visual=args.all,
        keep_input=args.keep,
    )


if __name__ == "__main__":
    sys.exit(main())
