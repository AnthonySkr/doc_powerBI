"""
Génération de la documentation Word d'un rapport Power BI (`.pbip`).

Le chef d'orchestre : il enchaîne les trois modules, il ne travaille pas.

Un seul objet circule d'un bout à l'autre, le `PowerBiMetadata` : rien ne
transite par le disque entre deux étapes.
"""

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.core import __version__, answers, console, prompts
from src.core.config import DEFAULT_CONFIG_PATH, DocConfig, load_config
from src.core.models import PowerBiMetadata
from src.core.window import ConsoleWindow
from src.gui_automator import CaptureError, capturer
from src.pbi_extractor import ExtractError, PbipProject, extract, open_project
from src.report_generator import (
    DocumentError,
    output_directory,
    report_result,
    write_document,
)

BASE_STEPS = 3


class PipelineError(Exception):
    """Erreur bloquante, à afficher à l'utilisateur avant de sortir."""


class Steps:
    """Le rang de l'étape en cours, sur le nombre d'étapes de l'exécution."""

    def __init__(self, total: int):
        self.total = total
        self.done = 0

    def next(self) -> tuple[int, int]:
        self.done += 1
        return self.done, self.total


@dataclass(frozen=True)
class Options:
    """Ce que la ligne de commande demande."""

    pbip_path: str
    config_path: str = DEFAULT_CONFIG_PATH
    interactive: bool = True
    pause: bool = True
    captures: bool = False
    capture_options: capturer.CaptureOptions = field(
        default_factory=capturer.CaptureOptions
    )
    show_capture_plan: bool = False
    calibrate: bool = False


# ─────────────────────────────────────────────────────────────
#  Le déroulé
# ─────────────────────────────────────────────────────────────


def generate(options: Options) -> Path:
    """Génère la documentation et retourne le dossier de sortie."""
    config = _config(options.config_path)
    project = _project(options.pbip_path)
    _announce(project, config)

    steps = Steps(BASE_STEPS + (1 if options.captures else 0))

    metadata = _extract(project, steps)
    if options.calibrate or options.show_capture_plan:
        _inspect_captures(metadata, config, options)
        return project.directory

    if options.captures:
        _capture(metadata, config, options, steps)

    inputs = _ask(metadata, config, options.interactive, steps)
    output_dir = project.output_dir(output_directory(metadata, config, inputs))

    # Les textes types du plan ne sont proposés à la réécriture que si
    # l'utilisateur l'a demandé, et seulement en interactif.
    rewrite = prompts.make_text_provider(
        options.interactive and bool(inputs.get("editer_textes", False))
    )

    console.step("Document Word", *steps.next())
    _document(metadata, config, inputs, output_dir, rewrite)
    return output_dir


def _extract(project: PbipProject, steps: Steps) -> PowerBiMetadata:
    """Première étape : le `.pbip` devient un `PowerBiMetadata`."""
    console.step("Lecture du rapport", *steps.next())
    try:
        return extract(project)
    except ExtractError as e:
        raise PipelineError(str(e)) from e


def _capture(
    metadata: PowerBiMetadata, config: DocConfig, options: Options, steps: Steps
) -> None:
    """
    Étape facultative : photographier les visuels dans Power BI Desktop.

    Une séance qui échoue n'emporte pas la génération : le document garde ses
    emplacements réservés.
    """
    console.step("Captures des visuels", *steps.next())
    try:
        capturer.capture(metadata, config, options.capture_options)
    except CaptureError as e:
        console.warn(f"Captures abandonnées ({e}) — le document réservera leur place.")


def _inspect_captures(
    metadata: PowerBiMetadata, config: DocConfig, options: Options
) -> None:
    """`--capture-plan` et `--calibrate` : ils n'écrivent aucun document."""
    directory = capturer.captures_dir(metadata, config)
    try:
        if options.calibrate:
            capturer.calibrate(config, directory)
        else:
            plans = capturer.shot_plan(metadata, config, options.capture_options)
            capturer.describe_plan(plans, capturer.CaptureLibrary(directory))
    except CaptureError as e:
        raise PipelineError(str(e)) from e


def _ask(
    metadata: PowerBiMetadata, config: DocConfig, interactive: bool, steps: Steps
) -> dict[str, Any]:
    """
    Les questions du plan, entre la lecture et l'écriture.

    Les réponses de la dernière génération sont reproposées : re-cocher à
    l'identique une liste de visuels écartés n'est pas une chose à confier à la
    mémoire de l'utilisateur. Elles vivent à côté du `.pbip`, et non dans le
    dossier de sortie — que l'une d'elles désigne.
    """
    context = prompts.base_context(metadata.report, config)
    path = answers.path(config, {"report": metadata.report}, metadata.project_dir)
    remembered = answers.read(path)

    if interactive:
        given = prompts.ask_inputs(config, context, remembered, step=steps.next())
    else:
        steps.next()
        given = prompts.default_inputs(config, context, remembered)

    answers.write(path, given)
    return given


def _document(
    metadata: PowerBiMetadata,
    config: DocConfig,
    inputs: dict[str, Any],
    output_dir: Path,
    rewrite: prompts.TextProvider | None,
) -> None:
    """Dernière étape : les métadonnées deviennent un `.docx`."""
    try:
        result = write_document(metadata, config, inputs, output_dir, rewrite)
    except DocumentError as e:
        raise PipelineError(str(e)) from e

    report_result(result)


# ─────────────────────────────────────────────────────────────
#  Détails
# ─────────────────────────────────────────────────────────────


def _announce(project: PbipProject, config: DocConfig) -> None:
    console.blank()
    console.field("Rapport", project.name)
    console.field("Projet", str(project.directory))
    console.field("Modèle", project.semantic_model_dir.name)  # type: ignore[union-attr]
    console.field("Pages", project.report_dir.name)  # type: ignore[union-attr]
    console.field("Plan", str(config.path))


def _config(path: str) -> DocConfig:
    try:
        return load_config(path)
    except (FileNotFoundError, ValueError) as e:
        raise PipelineError(f"Configuration : {e}") from e


def _project(pbip_path: str) -> PbipProject:
    try:
        return open_project(pbip_path)
    except ExtractError as e:
        raise PipelineError(str(e)) from e


# ─────────────────────────────────────────────────────────────
#  Ligne de commande
# ─────────────────────────────────────────────────────────────


def parse_args(argv: list[str] | None = None) -> Options:
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="Génère la documentation Word d'un rapport Power BI (.pbip).",
    )
    parser.add_argument("pbip", nargs="?", help="Chemin vers le fichier .pbip")
    parser.add_argument(
        "-c",
        "--config",
        default=DEFAULT_CONFIG_PATH,
        help=f"Fichier de configuration YAML (défaut : {DEFAULT_CONFIG_PATH})",
    )
    parser.add_argument(
        "-y",
        "--no-input",
        action="store_true",
        help="Ne pose aucune question : utilise les valeurs par défaut du YAML",
    )
    parser.add_argument(
        "--no-pause",
        action="store_true",
        help="Ne pas attendre de touche à la fin (exécution automatisée)",
    )

    captures = parser.add_argument_group("captures d'écran (facultatives)")
    captures.add_argument(
        "--captures",
        action="store_true",
        help="Photographier les visuels dans Power BI Desktop avant d'écrire",
    )
    captures.add_argument(
        "--fake-captures",
        action="store_true",
        help="Produire des images unies sans ouvrir Power BI (éprouve la chaîne)",
    )
    captures.add_argument(
        "--capture-plan",
        action="store_true",
        help="Afficher ce qui serait capturé, et s'arrêter là",
    )
    captures.add_argument(
        "--calibrate",
        action="store_true",
        help="Écrire la fenêtre et le canevas, pour régler le cadrage",
    )
    captures.add_argument(
        "--manual-pages",
        action="store_true",
        help="Changer de page à la main : le script attend avant chaque page",
    )
    captures.add_argument(
        "--all-visuals",
        action="store_true",
        help="Capturer tout le rapport, sans suivre ce que le plan retient",
    )
    captures.add_argument(
        "--page", default="", help="Ne capturer que les pages nommées ainsi"
    )
    captures.add_argument(
        "--shot", default="", help="Ne capturer que les prises nommées ainsi"
    )
    args = parser.parse_args(argv)

    return Options(
        pbip_path=(args.pbip or _ask_pbip()).strip().strip('"').strip("'"),
        config_path=args.config,
        interactive=not args.no_input,
        pause=not args.no_pause,
        captures=args.captures or args.fake_captures,
        capture_options=capturer.CaptureOptions(
            fake=args.fake_captures,
            manual_pages=args.manual_pages,
            every_visual=args.all_visuals,
            page=args.page,
            shot=args.shot,
        ),
        show_capture_plan=args.capture_plan,
        calibrate=args.calibrate,
    )


def _ask_pbip() -> str:
    """Demande le fichier à documenter, faute d'être lancé avec."""
    console.question("Quel rapport documenter ?")
    console.note("Déposez le fichier .pbip dans cette fenêtre, ou collez son chemin.")
    return console.ask("Fichier .pbip")


def main(argv: list[str] | None = None) -> int:
    """Point d'entrée du script. Retourne le code de sortie."""
    window = ConsoleWindow()
    window.install_crash_handler()

    console.title("Documentation Power BI", f"v{__version__}")

    options = parse_args(argv)
    window.pause = window.pause and options.pause

    try:
        output_dir = generate(options)
    except PipelineError as e:
        console.blank()
        console.banner("Génération abandonnée", ok=False)
        console.error(str(e))
        return window.close(1)
    except KeyboardInterrupt:
        console.blank()
        console.banner("Génération interrompue", ok=False)
        return window.close(130)

    console.blank()
    console.banner("Documentation générée")
    console.field("Dossier", str(output_dir))
    return window.close(0)


if __name__ == "__main__":
    sys.exit(main())
