"""
Le chef d'orchestre : il enchaîne les applications, il ne travaille pas.

    .pbip  ──►  extract  ──►  [ capture ]  ──►  document  ──►  .docx
                    1-rapport.json    2-captures.json

Chaque application est utilisable seule (`python -m src.apps.<nom>`) et ne
communique avec la suivante que par un fichier d'échange : elle le lit,
l'enrichit, en écrit un nouveau, et supprime celui qu'elle a consommé. Ce
module fait la même chose qu'un enchaînement de commandes, en y ajoutant ce qui
n'appartient à aucune application :

    où vivent les fichiers d'échange, et quand ils disparaissent
    quelles étapes sont jouées — la capture reste facultative
    le moment où l'utilisateur est interrogé, entre lecture et écriture
"""

import os
from dataclasses import dataclass
from typing import Any

from src.apps.document.render import DocumentError, output_directory, report_result, write_document
from src.apps.extract import ExtractError, PbipProject, collect, open_project
from src.cli import editing, prompts
from src.cli.arguments import Options
from src.shared import answers, console
from src.shared.config import DocConfig, load_config
from src.shared.exchange import DEFAULT_DIRECTORY, Exchange, discard, write
from src.shared.inputs import base_context, default_inputs

__all__ = ["PipelineError", "run"]

# Étapes annoncées à l'utilisateur : extraction, questions, document.
TOTAL_STEPS = 3

# Ce que chaque application laisse derrière elle, dans l'ordre de la chaîne.
EXTRACT_FILE = "1-rapport.json"
CAPTURE_FILE = "2-captures.json"


class PipelineError(Exception):
    """Erreur bloquante, à afficher à l'utilisateur avant de sortir."""


@dataclass
class Stage:
    """Une étape franchie : ce qu'elle a produit, et où elle l'a laissé."""

    exchange: Exchange
    path: str


def run(options: Options) -> str:
    """Génère la documentation et retourne le dossier de sortie."""
    config = _config(options.config_path)
    project = _project(options.pbip_path)
    _announce(project, config)

    stage = _extract(project)
    inputs = _ask(stage.exchange, config, project.directory, options.interactive)
    output_dir = project.output_dir(output_directory(stage.exchange, config, inputs))
    _document(stage, config, inputs, output_dir, options)
    return output_dir


# ─────────────────────────────────────────────────────────────
#  Les étapes, dans l'ordre
# ─────────────────────────────────────────────────────────────


def _extract(project: PbipProject) -> Stage:
    """Première application : le `.pbip` devient un fichier d'échange."""
    console.step("Lecture du rapport", 1, TOTAL_STEPS)
    exchange = collect(project)

    path = os.path.join(project.directory, DEFAULT_DIRECTORY, EXTRACT_FILE)
    write(exchange, path)
    console.done(f"rapport extrait dans {os.path.basename(path)}")
    return Stage(exchange, path)


def _ask(
    exchange: Exchange, config: DocConfig, project_dir: str, interactive: bool
) -> dict[str, Any]:
    """
    Les questions du plan, entre la lecture et l'écriture.

    Les réponses de la dernière génération sont reproposées : re-cocher à
    l'identique une liste de visuels écartés n'est pas une chose à confier à la
    mémoire de l'utilisateur. Elles vivent à côté du .pbip, et non dans le
    dossier de sortie — que l'une d'elles désigne.
    """
    context = base_context(exchange.report, config)
    path = answers.path(config, {"report": exchange.report}, project_dir)
    remembered = answers.read(path)

    if interactive:
        given = prompts.ask_inputs(config, context, remembered, step=(2, TOTAL_STEPS))
    else:
        given = default_inputs(config, context, remembered)

    answers.write(path, given)
    return given


def _document(
    stage: Stage, config: DocConfig, inputs: dict[str, Any], output_dir: str, options: Options
) -> None:
    """Dernière application : le fichier d'échange devient un .docx."""
    console.step("Document Word", TOTAL_STEPS, TOTAL_STEPS)

    # Les textes types du plan ne sont proposés à la réécriture que si
    # l'utilisateur l'a demandé, et seulement en interactif.
    rewrite = editing.make_text_provider(
        options.interactive and bool(inputs.get("editer_textes", False))
    )

    try:
        result = write_document(stage.exchange, config, inputs, output_dir, rewrite)
    except DocumentError as e:
        raise PipelineError(str(e)) from e

    report_result(result)
    # Le tapis roulant s'arrête ici : ce qui a servi disparaît, pour qu'un
    # fichier périmé ne passe jamais pour le dernier état du rapport.
    discard(stage.path)


# ─────────────────────────────────────────────────────────────
#  Détails
# ─────────────────────────────────────────────────────────────


def _announce(project: PbipProject, config: DocConfig) -> None:
    console.blank()
    console.field("Rapport", project.name)
    console.field("Projet", project.directory)
    console.field("Modèle", os.path.basename(project.semantic_model_dir))  # type: ignore[arg-type]
    console.field("Pages", os.path.basename(project.report_dir))  # type: ignore[arg-type]
    console.field("Plan", config.path)


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
