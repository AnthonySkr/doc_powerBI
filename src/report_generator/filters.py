"""
Mise en forme des données du modèle, telle que `data:` la déclare.

Les tables documentées, les regroupements de mesures et les étapes Power Query
retenues : ce qui n'intéresse que le document. La sélection des pages et des
visuels, partagée avec le questionnaire, vit dans `src.core.selection`.
"""

import re
from typing import Any

from src.core import console
from src.core.config import DocConfig
from src.core.models import (
    DaxMeasure,
    MeasureGroup,
    ModelTable,
    TransformationStep,
)
from src.core.selection import compact, lowercase

# Power BI nomme d'un GUID les étapes Power Query auxquelles l'utilisateur n'a
# pas donné de nom : elles n'apprennent rien au lecteur.
_GENERATED_STEP_NAME = re.compile(r"^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$", re.IGNORECASE)


def filter_tables(tables: list[ModelTable], config: DocConfig) -> list[ModelTable]:
    """Tables retenues par `data.tables`, source et étapes déjà filtrées."""
    options = config.data["tables"]
    excluded = lowercase(options.get("exclude_names"))

    kept = [
        table
        for table in tables
        if not (options.get("exclude_hidden") and table.is_hidden)
        and table.name.lower() not in excluded
    ]

    ignored_sources = {compact(value) for value in options.get("ignore_sources") or []}
    for table in kept:
        # Une source qui ne dit rien (`{1}`, la table de mesures créée à la
        # main) vaut mieux tue : le bloc « Paramètres » disparaît avec elle.
        if compact(table.source) in ignored_sources:
            table.source = ""
        table.transformation_steps = filter_steps(
            table.transformation_steps, options.get("steps") or {}
        )

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
    Sélectionne les mesures à documenter et les regroupe.

    Le regroupement suit `data.measures.group_by` : par table, ou par dossier
    d'affichage. Chaque mesure retenue est en outre rattachée à sa table, pour
    la partie « Table de données » du plan.
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
    Rattrape les mesures référencées qu'un filtre avait écartées.

    Une mesure masquée, ou la dépendance d'une mesure documentée, doit figurer
    au document : sans elle, le lien interne qui la mentionne serait mort.
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


def filter_steps(
    steps: list[TransformationStep], options: dict[str, Any]
) -> list[TransformationStep]:
    """
    Ne garde d'un script Power Query que les étapes qui apprennent quelque chose.

    Sont écartées celles auxquelles personne n'a donné de nom — Power BI les
    nomme d'un GUID — et celles au nom routinier : navigation, changement de
    type, renommage de colonnes. Des gestes de mise en forme, pas des règles.
    """
    excluded = lowercase(options.get("exclude_names"))
    prefixes = tuple(lowercase(options.get("exclude_prefixes")))

    return [
        step
        for step in steps
        if not (options.get("exclude_unnamed", True) and _GENERATED_STEP_NAME.match(step.name))
        and step.name.lower() not in excluded
        and not step.name.lower().startswith(prefixes)
    ]
