"""
Application des filtres et des tris déclarés dans `data:` (config_doc_pbi.yaml).

Chaque fonction prend la collection brute issue des parseurs et retourne la
collection telle que le plan doit la parcourir.
"""

from typing import Any

from src import console
from src.config import DocConfig
from src.models.data_models import (
    DaxMeasure,
    MeasureGroup,
    ModelTable,
    ReportPage,
    Visual,
    VisualGroup,
    VisualGroupMember,
)

# Sépare les sous-groupes traversés dans la légende d'un groupe.
_PATH_SEPARATOR = " › "


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

    return _sorted_visuals(kept, options.get("sort_by"))


def organize_page(page: ReportPage, config: DocConfig) -> None:
    """
    Répartit les visuels documentés de la page entre groupes Power BI et
    visuels isolés, et renseigne la légende de chaque groupe.

    À l'issue de l'appel :
      `page.visuals`            visuels documentés, dans l'ordre du document ;
      `page.groups`             groupes racines documentés, garnis ;
      `page.ungrouped_visuals`  visuels documentés hors de tout groupe.

    Les sous-groupes sont rattachés à leur groupe racine : un groupe imbriqué
    ne crée pas de partie supplémentaire, son contenu rejoint la légende et le
    détail du groupe racine en gardant trace du chemin (`member.group_path`).
    """
    options = config.data["visuals"]
    group_options = options.get("groups") or {}

    all_visuals = page.visuals
    documented = filter_visuals(all_visuals, config)

    if not group_options.get("enabled", True) or not page.groups:
        page.groups = []
        page.visuals = documented
        page.ungrouped_visuals = documented
        return

    containers = {group.name: group for group in page.groups}
    documented_ids = {visual.id for visual in documented}

    # Chaque visuel rejoint le groupe racine qui le contient, en gardant trace
    # des sous-groupes traversés au passage.
    contents: dict[str, list[tuple[Visual, str]]] = {group.name: [] for group in page.groups}
    for visual in all_visuals:
        root, path = _root_and_path(visual.parent_group_name, containers)
        if root is not None:
            contents[root.name].append((visual, path))

    groups = []
    for group in _sorted_groups(page.groups, group_options.get("sort_by")):
        if _root_and_path(group.parent_group_name, containers)[0] is not None:
            continue  # sous-groupe : documenté avec son groupe racine

        group.subgroups = [g for g in page.groups if g.parent_group_name == group.name]
        group.members = _members(
            contents[group.name], documented_ids, group_options.get("member_sort_by")
        )
        group.visuals = _sorted_visuals(
            [visual for visual, _ in contents[group.name] if visual.id in documented_ids],
            options.get("sort_by"),
        )
        # Un groupe sans aucun visuel documenté n'apporte que sa capture : il
        # n'est retenu que si la configuration le demande.
        if group.visuals or group_options.get("keep_empty"):
            groups.append(group)

    # Filet de sécurité : tout visuel documenté qui n'a rejoint aucune partie
    # de groupe reste documenté à la suite de la page. Aucun ne disparaît, quel
    # que soit l'état des `parentGroupName` du rapport.
    grouped_ids = {visual.id for group in groups for visual in group.visuals}

    page.groups = groups
    page.ungrouped_visuals = [v for v in documented if v.id not in grouped_ids]
    page.visuals = [v for group in groups for v in group.visuals] + page.ungrouped_visuals


def _members(
    contents: list[tuple[Visual, str]], documented_ids: set[str], sort_by: Any
) -> list[VisualGroupMember]:
    """Légende d'un groupe : tout son contenu, visuels écartés compris."""
    return [
        VisualGroupMember(
            number="",
            title=visual.title,
            visual_type=visual.visual_type,
            documented=visual.id in documented_ids,
            group_path=path,
        )
        for visual, path in _sorted_visuals(contents, sort_by, key=lambda item: item[0])
    ]


def _root_and_path(
    parent_name: str, containers: dict[str, VisualGroup]
) -> tuple[VisualGroup | None, str]:
    """
    Groupe racine contenant un élément, et chemin des sous-groupes traversés.

    Un `parentGroupName` inconnu ne rattache à rien : l'élément est traité
    comme isolé plutôt que rangé dans un groupe absent de la page.
    """
    chain: list[VisualGroup] = []
    seen: set[str] = set()
    current = containers.get(parent_name or "")

    while current is not None and current.name not in seen:
        seen.add(current.name)
        chain.append(current)
        current = containers.get(current.parent_group_name or "")

    if not chain:
        return None, ""
    return chain[-1], _PATH_SEPARATOR.join(group.title for group in reversed(chain[:-1]))


def _sorted_visuals(items: list, sort_by: Any, key=None) -> list:
    """Tri d'une liste de visuels : par position à l'écran, ou par titre."""
    visual = key or (lambda item: item)
    if sort_by == "position":
        return sorted(items, key=lambda item: (visual(item).pos_y, visual(item).pos_x))
    return sorted(items, key=lambda item: visual(item).title.lower())


def _sorted_groups(groups: list[VisualGroup], sort_by: Any) -> list[VisualGroup]:
    """Tri des groupes d'une page. Par défaut leur position à l'écran."""
    if sort_by == "title":
        return sorted(groups, key=lambda group: group.title.lower())
    return sorted(groups, key=lambda group: (group.pos_y, group.pos_x))


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
