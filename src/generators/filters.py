"""
Application des filtres et des tris déclarés dans `data:` (config_doc_pbi.yaml).

Chaque fonction prend la collection brute issue des parseurs et retourne la
collection telle que le plan doit la parcourir.
"""

from typing import Any

from src import console
from src.config import DocConfig
from src.models.data_models import DaxMeasure, MeasureGroup, ModelTable, ReportPage, Visual


def filter_pages(pages: list[ReportPage], config: DocConfig) -> list[ReportPage]:
    options = config.data["pages"]
    excluded = _lowercase(options.get("exclude_names"))

    kept = [
        page
        for page in pages
        if not (options.get("exclude_hidden") and page.is_hidden)
        and page.display_name.lower() not in excluded
    ]

    if options.get("sort_by") == "name":
        kept.sort(key=lambda page: page.display_name.lower())
    else:
        kept.sort(key=lambda page: page.order)

    return kept


def filter_visuals(visuals: list[Visual], config: DocConfig) -> list[Visual]:
    options = config.data["visuals"]
    excluded_types = _lowercase(options.get("exclude_types"))
    excluded_titles = _lowercase(options.get("exclude_titles"))

    kept = [
        visual
        for visual in visuals
        if visual.visual_type.lower() not in excluded_types
        and visual.title.lower() not in excluded_titles
        and (not options.get("only_with_measures") or visual.has_measures)
    ]

    if options.get("sort_by") == "position":
        kept.sort(key=lambda visual: (visual.pos_y, visual.pos_x))
    else:
        kept.sort(key=lambda visual: visual.title.lower())

    return kept


def filter_tables(tables: list[ModelTable], config: DocConfig) -> list[ModelTable]:
    options = config.data["tables"]
    excluded = _lowercase(options.get("exclude_names"))

    kept = [
        table
        for table in tables
        if not (options.get("exclude_hidden") and table.is_hidden)
        and table.name.lower() not in excluded
    ]

    step_format = options.get("step_format") or "{name}"
    for table in kept:
        table.transformation_steps = [
            _format_step(step, step_format) for step in table.transformation_steps
        ]

    if options.get("sort_by", "name") == "name":
        kept.sort(key=lambda table: table.name.lower())

    return kept


def group_measures(
    all_measures: dict[str, DaxMeasure],
    used_in_report: set[str],
    tables: list[ModelTable],
    config: DocConfig,
) -> list[MeasureGroup]:
    """
    Sélectionne les mesures à documenter et les regroupe (par table ou par
    dossier d'affichage). Les mesures retenues sont aussi rattachées à leur
    table, pour la partie « Table de données » du plan.
    """
    options = config.data["measures"]

    selected = {
        name: measure
        for name, measure in all_measures.items()
        if (options.get("scope") == "all" or name in used_in_report)
        and (options.get("include_hidden") or not measure.is_hidden)
    }

    if options.get("include_referenced", True):
        _add_referenced(selected, all_measures, used_in_report)

    measures = list(selected.values())
    if options.get("sort_by", "name") == "name":
        measures.sort(key=lambda measure: measure.name.lower())

    by_name = {table.name: table for table in tables}
    for measure in measures:
        table = by_name.get(measure.table_name)
        if table is not None:
            table.measures.append(measure)

    key = "display_folder" if options.get("group_by") == "display_folder" else "table_name"
    grouped: dict[str, list[DaxMeasure]] = {}
    for measure in measures:
        grouped.setdefault(getattr(measure, key), []).append(measure)

    return [MeasureGroup(name=name, measures=grouped[name]) for name in sorted(grouped)]


def _add_referenced(
    selected: dict[str, DaxMeasure],
    all_measures: dict[str, DaxMeasure],
    used_in_report: set[str],
) -> None:
    """
    Complète la sélection avec toute mesure référencée mais écartée par les
    filtres (mesure masquée, dépendance d'une mesure documentée...).

    Sans cela, une mention pointerait vers une définition absente du document :
    le lien interne serait mort.
    """
    pending = [name for name in used_in_report if name not in selected]
    pending += [
        dependency
        for measure in selected.values()
        for dependency in measure.dependent_measures
        if dependency not in selected
    ]

    added = 0
    while pending:
        name = pending.pop()
        measure = all_measures.get(name)
        if name in selected or measure is None:
            continue
        selected[name] = measure
        added += 1
        pending.extend(dep for dep in measure.dependent_measures if dep not in selected)

    if added:
        console.info(f"{added} mesure(s) ajoutée(s) au document car référencée(s) ailleurs")


def _format_step(step: Any, step_format: str) -> str:
    """Met en forme une étape Power Query ({"name": ..., "expression": ...})."""
    if isinstance(step, dict):
        return step_format.format(
            name=step.get("name", ""), expression=step.get("expression", "")
        ).strip()
    return str(step)


def _lowercase(values: Any) -> set[str]:
    return {str(value).lower() for value in values or []}
