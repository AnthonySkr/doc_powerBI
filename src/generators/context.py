"""
Contexte de données consommé par le plan YAML.

C'est ici que les données brutes issues des parseurs deviennent les collections
que le plan parcourt :

    report.pages / page.groups / page.ungrouped_visuals
    page.visuals / group.members / group.visuals / visual.references
    model.tables / model.tables_with_measures / table.measures
    inputs.<id> / styles.<clé>
"""

from typing import Any

from src.config import DocConfig
from src.generators import filters, references
from src.models.data_models import DaxMeasure, PowerBIReport, SemanticModel


def build_context(
    report: PowerBIReport,
    all_measures: dict[str, DaxMeasure],
    config: DocConfig,
    inputs: dict[str, Any],
) -> dict[str, Any]:
    """Assemble le contexte passé au générateur Word."""
    report.pages = filters.filter_pages(report.pages, config)
    for page in report.pages:
        filters.organize_page(page, config)

    options = references.visual_options(config)
    references.index_group_members(report, options)
    references.index_references(report, options)
    references.index_usages(report, all_measures, options)

    tables = filters.filter_tables(report.tables, config)
    groups = filters.group_measures(all_measures, report.measures_used_in_report, tables, config)

    return {
        "report": report,
        "model": SemanticModel(tables=tables, tables_with_measures=groups),
        "inputs": inputs,
        "styles": config.styles,
    }
