"""
Génération de la documentation Word d'un rapport Power BI (`.pbip`).

Le chef d'orchestre : il enchaîne les trois modules, il ne travaille pas.

Un seul objet circule d'un bout à l'autre, le `PowerBiMetadata` : rien ne
transite par le disque entre deux étapes.
"""

import argparse
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.core import __version__, answers, console, prompts, questions
from src.core.config import DEFAULT_CONFIG_PATH, DocConfig, load_config
from src.core.models import PowerBiMetadata
from src.core.window import ConsoleWindow
from src.gui_automator import CaptureError, capturer
from src.pbi_extractor import ExtractError, PbipProject, extract, open_project
from src.report_generator import (
    DocumentError,
    document_path,
    output_directory,
    report_result,
    write_document,
)

# Ce que le lancement produit : le texte, les images, ou les deux.
TEXT = "texte"
CAPTURES = "captures"
PICTURES = "images"
FULL = "complet"

MODES = {
    TEXT: "Texte seul — la documentation, sans prendre de captures",
    CAPTURES: "Captures seules — les images du dossier des captures, sans document",
    PICTURES: "Mise à jour des images — nouvelles captures, remplacées dans le document",
    FULL: "Complet — texte et captures, pour initialiser ou tout mettre à jour",
}

# Ce qui doit être prêt avant de lancer, mode par mode. Une capture prise
# sans eux échoue, ou photographie autre chose que le rapport. Chaque entrée
# est une consigne seule, ou un couple (consigne, ce qui la précise).
_WORD_CLOSED = ("Le document Word fermé, s'il est ouvert", "sinon il ne peut pas être réécrit")
_CAPTURE_READY = (
    "Power BI Desktop ouvert sur ce rapport, en vue Rapport",
    ("Le pointillé autour de la page visible sur ses quatre côtés",),
    ("Ni souris ni clavier pendant les captures", "le script pilote Power BI"),
)
PREREQUISITES = {
    TEXT: (_WORD_CLOSED,),
    CAPTURES: _CAPTURE_READY,
    PICTURES: (_WORD_CLOSED, *_CAPTURE_READY),
    FULL: (_WORD_CLOSED, *_CAPTURE_READY),
}

# Lecture du rapport, puis ce que chaque mode y ajoute : questions, captures,
# document.
_STEPS = {TEXT: 3, CAPTURES: 2, PICTURES: 3, FULL: 4}


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
    mode: str = TEXT
    capture_options: capturer.CaptureOptions = field(default_factory=capturer.CaptureOptions)
    show_capture_plan: bool = False
    calibrate: bool = False


# ─────────────────────────────────────────────────────────────
#  Le déroulé
# ─────────────────────────────────────────────────────────────


def generate(options: Options) -> Path:
    """
    Déroule le mode demandé et retourne le dossier de sortie.

    Celui du document, ou celui des captures quand aucun document n'est écrit.
    """
    config = _config(options.config_path)
    project = _project(options.pbip_path)
    _announce(project, config)
    inspecting = options.calibrate or options.show_capture_plan
    if not inspecting:
        console.field("Mode", MODES[options.mode].split(" — ")[0])
        if options.interactive:
            _check_prerequisites(PREREQUISITES[options.mode])

    steps = Steps(_STEPS[options.mode])

    metadata = _extract(project, steps)
    if inspecting:
        _inspect_captures(metadata, config, options)
        return project.directory

    if options.mode == CAPTURES:
        _capture(metadata, config, options, steps, required=True)
        return capturer.captures_dir(metadata, config)

    if options.mode == PICTURES:
        return _update_pictures(metadata, config, options, steps)

    if options.mode == FULL:
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

    if options.mode == TEXT and _captures_wanted(options):
        _add_pictures(
            metadata,
            config,
            options,
            steps,
            lambda: _document(metadata, config, inputs, output_dir, None),
        )
    return output_dir


def _update_pictures(
    metadata: PowerBiMetadata, config: DocConfig, options: Options, steps: Steps
) -> Path:
    """
    Nouvelles captures, puis le document existant réécrit autour d'elles.

    Sans question : les réponses de la dernière génération sont reprises
    telles quelles. La régénération garde tout ce qui a été écrit dans le
    document, et chaque image non retouchée y cède la place à sa nouvelle
    capture. Sans document à mettre à jour, il n'y a rien à faire : mieux
    vaut le dire avant d'ouvrir Power BI.
    """
    inputs = _remembered(metadata, config)
    output_dir = metadata.project_dir / output_directory(metadata, config, inputs)
    existing = document_path(metadata, config, inputs, output_dir)
    if not existing.is_file():
        raise PipelineError(
            f"Aucun document à mettre à jour ({existing}) — "
            "lancez d'abord une documentation, avec ou sans captures."
        )
    console.field("Document", str(existing))

    _capture(metadata, config, options, steps, required=True)
    console.step("Document Word", *steps.next())
    _document(metadata, config, inputs, output_dir, None)
    return output_dir


def _captures_wanted(options: Options) -> bool:
    """
    Après le texte seul, proposer d'ajouter les captures dans la foulée.

    La question n'est posée qu'en interactif : Power BI doit être ouvert sur
    le rapport, ce que seul l'utilisateur présent peut garantir.
    """
    if not options.interactive:
        return False
    console.blank()
    console.info("Le document est écrit. Les captures peuvent y être ajoutées maintenant.")
    if not questions.confirm("Prendre les captures et les insérer dans le document ?", False):
        return False
    _check_prerequisites(PREREQUISITES[FULL])
    return True


def _check_prerequisites(items: tuple[str | tuple[str, ...], ...]) -> None:
    """
    Ce qui doit être prêt avant de continuer, et l'attente que ce le soit.

    Dit avant de lire le rapport plutôt qu'au moment de capturer : Power BI à
    ouvrir ou un document à fermer, c'est maintenant que l'utilisateur est
    devant le terminal pour le lire.
    """
    console.question("Avant de continuer")
    for number, entry in enumerate(items, start=1):
        item, *details = (entry,) if isinstance(entry, str) else entry
        console.option(number, item)
        for detail in filter(None, details):
            console.note(f"       {detail}")
    console.blank()
    console.ask("Entrée quand tout est prêt (Ctrl+C pour abandonner)")


def _add_pictures(
    metadata: PowerBiMetadata,
    config: DocConfig,
    options: Options,
    steps: Steps,
    rewrite_document: Callable[[], None],
) -> None:
    """Les captures, puis le document réécrit avec les mêmes réponses."""
    steps.total += 2
    try:
        _capture(metadata, config, options, steps, required=True)
    except PipelineError as e:
        console.warn(f"{e} — le document reste tel quel.")
        return
    console.step("Document Word", *steps.next())
    rewrite_document()


def _extract(project: PbipProject, steps: Steps) -> PowerBiMetadata:
    """Première étape : le `.pbip` devient un `PowerBiMetadata`."""
    console.step("Lecture du rapport", *steps.next())
    try:
        return extract(project)
    except ExtractError as e:
        raise PipelineError(str(e)) from e


def _capture(
    metadata: PowerBiMetadata,
    config: DocConfig,
    options: Options,
    steps: Steps,
    required: bool = False,
) -> None:
    """
    Photographier les visuels dans Power BI Desktop.

    Avec le document, une séance qui échoue n'emporte pas la génération : le
    document garde ses emplacements réservés. Quand les captures sont tout ce
    qui est demandé (`required`), l'échec arrête l'exécution.
    """
    console.step("Captures des visuels", *steps.next())
    try:
        capturer.capture(metadata, config, options.capture_options)
    except CaptureError as e:
        if required:
            raise PipelineError(f"Captures abandonnées : {e}") from e
        console.warn(f"Captures abandonnées ({e}) — le document réservera leur place.")


def _inspect_captures(metadata: PowerBiMetadata, config: DocConfig, options: Options) -> None:
    """`--capture-plan` et `--calibrate` : ils n'écrivent aucun document."""
    directory = capturer.captures_dir(metadata, config)
    try:
        plans = capturer.shot_plan(metadata, config, options.capture_options)
        if options.calibrate:
            capturer.calibrate(config, directory, plans)
        else:
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


def _remembered(metadata: PowerBiMetadata, config: DocConfig) -> dict[str, Any]:
    """Les réponses de la dernière génération, complétées des valeurs du plan."""
    context = prompts.base_context(metadata.report, config)
    path = answers.path(config, {"report": metadata.report}, metadata.project_dir)
    return prompts.default_inputs(config, context, answers.read(path))


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

    parser.add_argument(
        "-m",
        "--mode",
        choices=list(MODES),
        help="Ce que produit l'exécution — sans cette option, la question est posée : "
        + " ; ".join(f"{name} = {label.split(' — ')[0].lower()}" for name, label in MODES.items()),
    )

    captures = parser.add_argument_group("captures d'écran (facultatives)")
    captures.add_argument(
        "--captures",
        action="store_true",
        help="Documentation et captures : équivaut à `--mode complet`",
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
    captures.add_argument("--page", default="", help="Ne capturer que les pages nommées ainsi")
    captures.add_argument("--shot", default="", help="Ne capturer que les prises nommées ainsi")
    args = parser.parse_args(argv)

    pbip_path = (args.pbip or _ask_pbip()).strip().strip('"').strip("'")
    inspecting = args.capture_plan or args.calibrate
    return Options(
        pbip_path=pbip_path,
        config_path=args.config,
        interactive=not args.no_input,
        pause=not args.no_pause,
        mode=_mode(args.mode, args.captures or args.fake_captures, not args.no_input, inspecting),
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


def _mode(given: str | None, captures: bool, interactive: bool, inspecting: bool) -> str:
    """
    Le mode demandé par l'option, ou à défaut par l'utilisateur.

    `--captures` seul garde son sens d'avant : le document et ses captures.
    Sans rien, la question est posée — c'est le cas du double-clic sur
    l'exécutable ; sans question possible (`--no-input`), le texte seul.
    """
    if given:
        return given
    if captures:
        return FULL
    if not interactive or inspecting:
        return TEXT
    return _ask_mode()


def _ask_mode() -> str:
    """Le menu du lancement : quatre façons de documenter le rapport."""
    labels = list(MODES.values())
    chosen = questions.choice("Que faut-il produire ?", labels, labels[0])
    return next(name for name, label in MODES.items() if label == chosen)


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
    console.banner("Captures prises" if options.mode == CAPTURES else "Documentation générée")
    console.field("Dossier", str(output_dir))
    return window.close(0)


if __name__ == "__main__":
    sys.exit(main())
