"""
Application des filtres et des tris déclarés dans `data:` (config_doc_pbi.yaml).

Chaque fonction prend la collection brute issue des parseurs et retourne la
collection telle que le plan doit la parcourir.
"""

import re
from typing import Any

from src import console
from src.config import DocConfig
from src.models.data_models import (
    DaxMeasure,
    MeasureGroup,
    ModelTable,
    PowerBIReport,
    ReportPage,
    TransformationStep,
    Visual,
    VisualGroup,
    VisualGroupMember,
)

# Sépare les sous-groupes traversés dans la légende d'un groupe.
_PATH_SEPARATOR = " › "

# Power BI nomme d'un GUID les étapes Power Query auxquelles l'utilisateur n'a
# pas donné de nom : elles n'apprennent rien au lecteur.
_GENERATED_STEP_NAME = re.compile(r"^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$", re.IGNORECASE)


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

    Un visuel écarté par `data.visuals` l'est partout : il ne figure ni dans le
    détail du groupe, ni dans sa légende.
    """
    options = config.data["visuals"]
    group_options = options.get("groups") or {}

    documented = filter_visuals(page.visuals, config)

    if not group_options.get("enabled", True) or not page.groups:
        page.groups = []
        page.visuals = documented
        page.ungrouped_visuals = documented
        return

    containers = {group.name: group for group in page.groups}
    excluded_titles = _lowercase(group_options.get("exclude_titles"))

    # Un groupe écarté l'est avec tout son contenu : il est présenté ailleurs
    # dans le document, ses visuels n'ont pas à l'être une seconde fois ici.
    documented = [
        visual
        for visual in documented
        if _excluded_root(visual.parent_group_name, containers, excluded_titles) is None
    ]

    # Chaque visuel documenté rejoint le groupe racine qui le contient, en
    # gardant trace des sous-groupes traversés au passage.
    contents: dict[str, list[tuple[Visual, str]]] = {group.name: [] for group in page.groups}
    for visual in documented:
        root, path = _root_and_path(visual.parent_group_name, containers)
        if root is not None:
            contents[root.name].append((visual, path))

    groups = []
    for group in _sorted_groups(page.groups, group_options.get("sort_by")):
        if _root_and_path(group.parent_group_name, containers)[0] is not None:
            continue  # sous-groupe : documenté avec son groupe racine
        if group.title.lower() in excluded_titles:
            continue

        group.subgroups = [g for g in page.groups if g.parent_group_name == group.name]
        group.members = _members(contents[group.name], group_options.get("member_sort_by"))
        group.visuals = _sorted_visuals(
            [visual for visual, _ in contents[group.name]], options.get("sort_by")
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


def _members(contents: list[tuple[Visual, str]], sort_by: Any) -> list[VisualGroupMember]:
    """Légende d'un groupe : les visuels documentés qu'il contient."""
    return [
        VisualGroupMember(
            number="",
            title=visual.title,
            visual_type=visual.visual_type,
            group_path=path,
        )
        for visual, path in _sorted_visuals(contents, sort_by, key=lambda item: item[0])
    ]


def _excluded_root(
    parent_name: str, containers: dict[str, VisualGroup], excluded_titles: set[str]
) -> VisualGroup | None:
    """Le groupe racine d'un visuel, s'il fait partie des groupes écartés."""
    root = _root_and_path(parent_name, containers)[0]
    return root if root is not None and root.title.lower() in excluded_titles else None


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

    ignored_sources = {_compact(value) for value in options.get("ignore_sources") or []}
    for table in kept:
        # Une source qui ne dit rien (`{1}`, la table de mesures créée à la
        # main) vaut mieux tue : le bloc « Paramètres » disparaît avec elle.
        if _compact(table.source) in ignored_sources:
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


def filter_steps(
    steps: list[TransformationStep], options: dict[str, Any]
) -> list[TransformationStep]:
    """
    Ne garde d'un script Power Query que les étapes qui apprennent quelque
    chose au lecteur.

    Sont écartées les étapes auxquelles personne n'a donné de nom (Power BI les
    nomme d'un GUID), et celles dont le nom est routinier — la navigation dans
    la source, un changement de type, un renommage de colonnes... Ce sont des
    gestes de mise en forme, pas des règles de traitement.
    """
    excluded = _lowercase(options.get("exclude_names"))
    prefixes = tuple(_lowercase(options.get("exclude_prefixes")))

    return [
        step
        for step in steps
        if not (options.get("exclude_unnamed", True) and _GENERATED_STEP_NAME.match(step.name))
        and step.name.lower() not in excluded
        and not step.name.lower().startswith(prefixes)
    ]


def documentable_titles(report: PowerBIReport, config: DocConfig) -> list[str]:
    """
    Titres des groupes et visuels que le document peut détailler.

    Ils sont proposés au lancement pour être écartés de la partie « Visuels ».
    Un bandeau d'en-tête porte le même titre sur toutes les pages : les titres
    sont donc dédoublonnés, et en écarter un l'écarte partout à la fois.
    """
    titles = {group.title for page in report.pages for group in page.groups}
    for page in report.pages:
        titles.update(visual.title for visual in filter_visuals(page.visuals, config))
    return sorted(titles, key=str.lower)


def _compact(value: Any) -> str:
    """Forme de comparaison d'une expression : sans espaces ni casse."""
    return "".join(str(value or "").split()).lower()


def _lowercase(values: Any) -> set[str]:
    """Ensemble de comparaison d'une option de configuration, en minuscules."""
    if isinstance(values, str):
        values = [values]
    return {str(value).lower() for value in values or []}
