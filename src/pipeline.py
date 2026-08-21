"""
Enchaînement complet : d'un fichier .pbip au document Word.

    .pbip  ──►  modèle sémantique + rapport  ──►  contexte  ──►  .docx

Les questions posées à l'utilisateur et la structure du document viennent de
`config_doc_pbi.yaml` : ce module ne décide de rien, il orchestre.
"""

import os
from typing import Any

from src import console
from src.cli import prompts
from src.cli.arguments import Options
from src.config import DocConfig, load_config, render
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


def run(options: Options) -> str:
    """Génère la documentation et retourne le dossier de sortie."""
    if not os.path.isfile(options.pbip_path):
        raise PipelineError(f"Fichier introuvable : '{options.pbip_path}'")

    try:
        config = load_config(options.config_path)
    except (FileNotFoundError, ValueError) as e:
        raise PipelineError(f"Configuration : {e}") from e

    project = PbipProject(options.pbip_path)
    console.banner(f"Rapport : {project.name}")
    console.info(f"Config : {config.path}")

    error = project.missing()
    if error:
        raise PipelineError(error)

    console.info(f"SemanticModel : {os.path.basename(project.semantic_model_dir)}")  # type: ignore
    console.info(f"Report        : {os.path.basename(project.report_dir)}")  # type: ignore
    console.blank()

    report = _collect(project)
    inputs = _ask_inputs(config, report, options.interactive)
    output_dir = project.output_dir(config.document.get("output_dir", "output"))

    _generate(config, report, inputs, output_dir, project.name, options.interactive)
    return output_dir


# ─────────────────────────────────────────────────────────────
#  Étapes
# ─────────────────────────────────────────────────────────────


def _collect(project: PbipProject) -> PowerBIReport:
    """Lit le modèle sémantique et le rapport, puis croise les deux."""
    console.step("Étape 1 — Chargement du modèle sémantique")
    all_measures, tables = load_semantic_model(project.semantic_model_dir)  # type: ignore
    console.blank()

    if all_measures:
        console.step("Étape 2 — Analyse des dépendances")
        dependencies.analyze_dependencies(all_measures)
        console.info(f"Dépendances calculées pour {len(all_measures)} mesures")
        console.blank()

    console.step("Étape 3 — Lecture du rapport")
    report = parse_report(project.report_dir, report_name=project.name)  # type: ignore
    report.all_measures = all_measures
    report.tables = tables
    report.measures_used_in_report = dependencies.measures_used_in_report(
        report, all_measures
    )

    console.info(f"Mesures dans les visuels : {len(report.measures_in_visuals)}")
    console.info(f"Mesures totales (+ deps) : {len(report.measures_used_in_report)}")
    console.blank()

    return report


def _ask_inputs(
    config: DocConfig, report: PowerBIReport, interactive: bool
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
        return prompts.ask_inputs(config, base_context)
    return prompts.default_inputs(config, base_context)


def _generate(
    config: DocConfig,
    report: PowerBIReport,
    inputs: dict[str, Any],
    output_dir: str,
    report_name: str,
    interactive: bool,
) -> None:
    console.step("Étape 4 — Génération du document")

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
    console.info(log.summary())
    for line in log.details():
        console.detail(line)
