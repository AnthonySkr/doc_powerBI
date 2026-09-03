"""
Enchaînement complet : d'un fichier .pbip au document Word.

    .pbip  ──►  modèle sémantique + rapport  ──►  contexte  ──►  .docx

Les questions posées à l'utilisateur et la structure du document viennent de
`config_doc_pbi.yaml` : ce module ne décide de rien, il orchestre.
"""

import os
from typing import Any

from src import console
from src.cli import answers, prompts
from src.cli.arguments import Options
from src.config import DEFAULT_OUTPUT_DIR, DocConfig, load_config, render
from src.generators import filters
from src.generators.context import build_context
from src.generators.word import DocumentError, generate_word_documentation
from src.models.data_models import PowerBIReport
from src.parsers import dependencies
from src.parsers.pbip import PbipProject
from src.parsers.report import parse_report
from src.parsers.tmdl import load_semantic_model


class PipelineError(Exception):
    """Erreur bloquante, à afficher à l'utilisateur avant de sortir."""


# Étapes annoncées à l'utilisateur : modèle, rapport, questions, document.
TOTAL_STEPS = 4


def run(options: Options) -> str:
    """Génère la documentation et retourne le dossier de sortie."""
    if not os.path.isfile(options.pbip_path):
        raise PipelineError(f"Fichier introuvable : '{options.pbip_path}'")

    try:
        config = load_config(options.config_path)
    except (FileNotFoundError, ValueError) as e:
        raise PipelineError(f"Configuration : {e}") from e

    project = PbipProject(options.pbip_path)

    error = project.missing()
    if error:
        raise PipelineError(error)

    console.blank()
    console.field("Rapport", project.name)
    console.field("Projet", project.directory)
    console.field("Modèle", os.path.basename(project.semantic_model_dir))  # type: ignore
    console.field("Pages", os.path.basename(project.report_dir))  # type: ignore
    console.field("Plan", config.path)

    report = _collect(project)

    # Les réponses de la dernière génération sont reproposées : re-cocher à
    # l'identique une liste de visuels écartés n'est pas une chose à confier à
    # la mémoire de l'utilisateur. Elles vivent à côté du .pbip, et non dans le
    # dossier de sortie — que l'une d'elles désigne.
    answers_path = answers.path(config, {"report": report}, project.directory)
    remembered = answers.read(answers_path)

    inputs = _ask_inputs(config, report, options.interactive, remembered)
    answers.write(answers_path, inputs)

    output_dir = project.output_dir(_output_dir(config, report, inputs))
    _generate(config, report, inputs, output_dir, project.name, options.interactive)
    return output_dir


# ─────────────────────────────────────────────────────────────
#  Étapes
# ─────────────────────────────────────────────────────────────


def _output_dir(config: DocConfig, report: PowerBIReport, inputs: dict[str, Any]) -> str:
    """Dossier de sortie déclaré par le plan, une fois les réponses connues."""
    declared = render(config.document.get("output_dir"), {"report": report, "inputs": inputs})
    return declared or DEFAULT_OUTPUT_DIR


def _collect(project: PbipProject) -> PowerBIReport:
    """Lit le modèle sémantique et le rapport, puis croise les deux."""
    console.step("Modèle de données", 1, TOTAL_STEPS)
    all_measures, tables = load_semantic_model(project.semantic_model_dir)  # type: ignore
    if all_measures:
        dependencies.analyze_dependencies(all_measures)
        console.done(f"dépendances calculées pour {len(all_measures)} mesure(s)")

    console.step("Rapport", 2, TOTAL_STEPS)
    report = parse_report(project.report_dir, report_name=project.name)  # type: ignore
    report.all_measures = all_measures
    report.tables = tables
    report.measures_used_in_report = dependencies.measures_used_in_report(report, all_measures)

    console.done(f"{len(report.measures_in_visuals)} mesure(s) affichée(s) dans les visuels")
    console.done(
        f"{len(report.measures_used_in_report)} mesure(s) à documenter (dépendances comprises)"
    )

    return report


def _ask_inputs(
    config: DocConfig,
    report: PowerBIReport,
    interactive: bool,
    remembered: dict[str, Any] | None = None,
) -> dict[str, Any]:
    # `choices` : ce que le rapport contient réellement, pour les questions qui
    # font choisir dans son contenu plutôt que dans une liste figée du YAML.
    base_context = {
        "report": report,
        "inputs": {},
        "styles": config.styles,
        "choices": {"visuals": filters.documentable_titles(report, config)},
    }
    if interactive:
        return prompts.ask_inputs(config, base_context, remembered, step=(3, TOTAL_STEPS))
    return prompts.default_inputs(config, base_context, remembered)


def _generate(
    config: DocConfig,
    report: PowerBIReport,
    inputs: dict[str, Any],
    output_dir: str,
    report_name: str,
    interactive: bool,
) -> None:
    console.step("Document Word", TOTAL_STEPS, TOTAL_STEPS)

    context = build_context(report, report.all_measures, config, inputs)
    output_name = render(config.document.get("output_name"), context) or (
        f"documentation_{report_name}.docx"
    )

    text_provider = prompts.make_text_provider(
        interactive and bool(inputs.get("editer_textes", False))
    )

    try:
        log = generate_word_documentation(
            config, context, os.path.join(output_dir, output_name), text_provider
        )
    except DocumentError as e:
        raise PipelineError(str(e)) from e

    console.blank()
    console.done(log.summary())
    for line in log.details():
        console.detail(line)

    _report_undocumented_measures(report)


def _report_undocumented_measures(report: PowerBIReport) -> None:
    """
    Nomme les mesures du modèle que le document ne documente pas.

    `data.measures.scope: used_in_report` écarte les mesures qu'aucun visuel
    n'affiche et qu'aucun filtre n'emploie. Les compter ne suffit pas : sans
    leurs noms, impossible de dire si l'une manque à tort.
    """
    names = report.undocumented_measures
    if not names:
        return

    console.blank()
    console.info(f"{len(names)} mesure(s) du modèle non documentée(s) — non utilisée(s) :")
    for name in names:
        console.detail(f"· {name}")
