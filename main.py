"""
Génération de la documentation Word d'un rapport Power BI (`.pbip`).

Le chef d'orchestre : il enchaîne les étapes.

    .pbip  ──►  pbi_extractor  ──►  report_generator  ──►  .docx

Un seul objet circule d'un bout à l'autre, le `PowerBiMetadata` : rien ne
transite par le disque entre deux étapes.

## Le déroulé

`main` tient la fenêtre et le code de sortie, `parse_args` lit la ligne de
commande, et `generate` enchaîne les trois étapes :

1. `_extract` — le `.pbip` devient un `PowerBiMetadata` ;
2. `_ask` — les questions du plan, et la mémoire des réponses ;
3. `_document` — les métadonnées deviennent un `.docx`.

Le reste sert ces trois-là : `_config` et `_project` ouvrent ce qu'on leur
donne, `_announce` le rappelle à l'écran, `_rewriter` propose la relecture des
textes du plan.
"""

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.core import __version__, answers, console, prompts
from src.core.config import DEFAULT_CONFIG_PATH, DocConfig, load_config
from src.core.models import PowerBiMetadata
from src.core.window import ConsoleWindow
from src.pbi_extractor import ExtractError, PbipProject, extract, open_project
from src.report_generator import (
    DocumentError,
    output_directory,
    report_result,
    write_document,
)

STEPS = 3
"""Lecture du rapport, questions, écriture du document."""


class PipelineError(Exception):
    """Erreur bloquante, à afficher à l'utilisateur avant de sortir."""


@dataclass(frozen=True)
class Options:
    """Ce que la ligne de commande demande."""

    pbip_path: str
    """Chemin du fichier `.pbip` à documenter."""

    config_path: str = DEFAULT_CONFIG_PATH
    """Chemin du plan YAML."""

    interactive: bool = True
    """Poser les questions du plan, plutôt que prendre ses défauts."""

    pause: bool = True
    """Attendre une touche avant de fermer la fenêtre."""


# ─────────────────────────────────────────────────────────────
#  Le déroulé
# ─────────────────────────────────────────────────────────────


def generate(options: Options) -> Path:
    """
    Enchaîne les trois étapes et retourne le dossier de sortie.

    Raises:
        PipelineError: plan illisible, projet introuvable, écriture impossible.
    """
    config = _config(options.config_path)
    project = _project(options.pbip_path)
    _announce(project, config)

    metadata = _extract(project)
    inputs = _ask(metadata, config, options.interactive)
    output_dir = project.output_dir(output_directory(metadata, config, inputs))

    console.step("Document Word", 3, STEPS)
    _document(metadata, config, inputs, output_dir, _rewriter(options, inputs))
    return output_dir


def _extract(project: PbipProject) -> PowerBiMetadata:
    """Première **étape** : le `.pbip` devient un `PowerBiMetadata`."""
    console.step("Lecture du rapport", 1, STEPS)
    try:
        return extract(project)
    except ExtractError as e:
        raise PipelineError(str(e)) from e


def _ask(
    metadata: PowerBiMetadata, config: DocConfig, interactive: bool
) -> dict[str, Any]:
    """
    Deuxième **étape** : les réponses aux questions du plan.

    Celles de la génération précédente sont reproposées, puis réécrites. Elles
    restent à côté du `.pbip`, et non dans le dossier de sortie.
    """
    console.step("Renseignements", 2, STEPS)
    context = prompts.base_context(metadata.report, config)
    path = answers.path(config, {"report": metadata.report}, metadata.project_dir)
    remembered = answers.read(path)

    ask = prompts.ask_inputs if interactive else prompts.default_inputs
    given = ask(config, context, remembered)

    answers.write(path, given)
    return given


def _document(
    metadata: PowerBiMetadata,
    config: DocConfig,
    inputs: dict[str, Any],
    output_dir: Path,
    rewrite: prompts.TextProvider | None,
) -> None:
    """Troisième **étape** : les métadonnées deviennent un `.docx`."""
    try:
        result = write_document(metadata, config, inputs, output_dir, rewrite)
    except DocumentError as e:
        raise PipelineError(str(e)) from e

    report_result(result)


def _rewriter(options: Options, inputs: dict[str, Any]) -> prompts.TextProvider | None:
    """Relecture des textes types du plan, si l'utilisateur l'a demandée."""
    return prompts.make_text_provider(
        options.interactive and bool(inputs.get("editer_textes", False))
    )


# ─────────────────────────────────────────────────────────────
#  Détails
# ─────────────────────────────────────────────────────────────


def _announce(project: PbipProject, config: DocConfig) -> None:
    """Rappelle à l'écran ce qui va être documenté, et avec quel plan."""
    console.blank()
    console.field("Rapport", project.name)
    console.field("Projet", str(project.directory))
    console.field("Modèle", project.semantic_model_dir.name)  # type: ignore[union-attr]
    console.field("Pages", project.report_dir.name)  # type: ignore[union-attr]
    console.field("Plan", str(config.path))


def _config(path: str) -> DocConfig:
    """Charge le plan, ou dit pourquoi il est inutilisable."""
    try:
        return load_config(path)
    except (FileNotFoundError, ValueError) as e:
        raise PipelineError(f"Configuration : {e}") from e


def _project(pbip_path: str) -> PbipProject:
    """Ouvre le projet `.pbip`, ou dit pourquoi il est inutilisable."""
    try:
        return open_project(pbip_path)
    except ExtractError as e:
        raise PipelineError(str(e)) from e


# ─────────────────────────────────────────────────────────────
#  Ligne de commande
# ─────────────────────────────────────────────────────────────


def parse_args(argv: list[str] | None = None) -> Options:
    """Lit la ligne de commande, et demande le `.pbip` s'il n'y figure pas."""
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
    args = parser.parse_args(argv)

    return Options(
        pbip_path=(args.pbip or _ask_pbip()).strip().strip('"').strip("'"),
        config_path=args.config,
        interactive=not args.no_input,
        pause=not args.no_pause,
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
