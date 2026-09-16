"""
Ce que le plan retient du rapport.

`data.pages` et `data.visuals` disent quelles pages et quels visuels sont
documentés, comment ils sont triés, et comment les groupes de Power BI se
réorganisent en parties du document.

Cette lecture est **partagée** : le document s'en sert pour savoir quoi écrire,
et le questionnaire de lancement pour proposer la liste des visuels qu'on peut
écarter. Ce qui relève de la seule mise en forme — tables, regroupements de
mesures, étapes Power Query — reste dans `src.report_generator.filters`.
"""

from typing import Any

from src.core.config import DocConfig
from src.core.models import (
    PowerBIReport,
    ReportPage,
    Visual,
    VisualGroup,
    VisualGroupMember,
)

# Sépare les sous-groupes traversés dans la légende d'un groupe.
_PATH_SEPARATOR = " › "


def compact(value: Any) -> str:
    """Forme de comparaison d'une expression : sans espaces ni casse."""
    return "".join(str(value or "").split()).lower()


def lowercase(values: Any) -> set[str]:
    """Ensemble de comparaison d'une option de configuration, en minuscules."""
    if isinstance(values, str):
        values = [values]
    return {str(value).lower() for value in values or []}


def filter_pages(pages: list[ReportPage], config: DocConfig) -> list[ReportPage]:
    """Pages retenues par `data.pages`, dans l'ordre voulu par le plan."""
    options = config.data["pages"]
    excluded = lowercase(options.get("exclude_names"))

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
    """Visuels retenus par `data.visuals`, dans l'ordre voulu par le plan."""
    options = config.data["visuals"]
    excluded_types = lowercase(options.get("exclude_types"))
    excluded_titles = lowercase(options.get("exclude_titles"))

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
    Répartit les visuels documentés de la page entre groupes et isolés.

    La page est renseignée sur place :

        `page.visuals`            tous les documentés, dans l'ordre du document
        `page.groups`             groupes racines documentés, garnis
        `page.ungrouped_visuals`  ceux qui n'appartiennent à aucun groupe

    Un sous-groupe n'ouvre pas de partie à lui : son contenu rejoint le groupe
    racine, qui garde trace du chemin dans `member.group_path`. Un visuel
    écarté par `data.visuals` l'est partout, légende comprise.
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
    excluded_titles = lowercase(group_options.get("exclude_titles"))

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
        if _deserves_part(group.visuals, group_options):
            groups.append(group)

    # Filet de sécurité : tout visuel documenté qui n'a rejoint aucune partie
    # de groupe reste documenté à la suite de la page. Aucun ne disparaît, quel
    # que soit l'état des `parentGroupName` du rapport.
    grouped_ids = {visual.id for group in groups for visual in group.visuals}

    page.groups = groups
    page.ungrouped_visuals = [v for v in documented if v.id not in grouped_ids]
    page.visuals = [v for group in groups for v in group.visuals] + page.ungrouped_visuals


def _deserves_part(visuals: list[Visual], options: dict[str, Any]) -> bool:
    """
    Un groupe mérite-t-il sa propre partie du document ?

    Avec un seul visuel documenté, son titre et sa légende d'une ligne ne font
    que redire ce que le visuel dit déjà. Sans aucun, il n'y a rien à dire.
    Dans les deux cas le visuel, s'il y en a un, est documenté à la suite de
    la page — `keep_single` et `keep_empty` rétablissent la partie.
    """
    if not visuals:
        return bool(options.get("keep_empty"))
    if len(visuals) == 1:
        return bool(options.get("keep_single"))
    return True


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

    Un `parentGroupName` inconnu ne rattache à rien : l'élément passe pour
    isolé plutôt que rangé dans un groupe absent de la page.
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


def documentable_titles(report: PowerBIReport, config: DocConfig) -> list[str]:
    """
    Titres des groupes et visuels que le document peut détailler.

    Ils sont proposés au lancement pour être écartés. Un bandeau d'en-tête
    porte le même titre sur toutes les pages : les titres sont dédoublonnés,
    et en écarter un l'écarte partout à la fois.
    """
    titles = {group.title for page in report.pages for group in page.groups}
    for page in report.pages:
        titles.update(visual.title for visual in filter_visuals(page.visuals, config))
    return sorted(titles, key=str.lower)
