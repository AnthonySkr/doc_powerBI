"""
Signets du rapport, et les affichages qu'ils produisent sur chaque page.

    Report/definition/bookmarks/bookmarks.json          ordre et groupes
                                <nom>.bookmark.json     un par signet

Le problème
───────────
Un navigateur de signets fait alterner, au même endroit, des visuels dont un
seul est visible à la fois : trois graphiques superposés, deux tableaux. Pour
le rapport, ce sont des visuels comme les autres, et le plan de capture les
cadrait tous… sur ce qui était affiché : le même graphique, trois fois.

Ce que fait ce module
─────────────────────
Il lit, pour chaque signet et chaque page, ce que le signet masque et ce qu'il
affiche (`display.mode: "hidden"` d'un visuel, `isHidden` d'un groupe) — en
s'en tenant aux visuels ciblés quand le signet ne s'applique qu'à eux. Il en
déduit, page par page, un **affichage** par signet qui change quelque chose,
et l'endroit où cliquer pour l'obtenir : la case du navigateur qui porte ce
signet, ou le bouton qui l'applique.

Le plan de capture n'a plus qu'à ranger chaque prise dans le premier affichage
où son visuel est visible (voir `gui_automator.plan`).
"""

import os
from dataclasses import dataclass, field

from src.core.models import BookmarkControl, PageView, ReportPage
from src.pbi_extractor.report.pages import read_json

__all__ = ["Bookmark", "attach_views", "load_bookmarks"]

type _Area = tuple[float, float, float, float]  # x, y, largeur, hauteur

# Orientations du navigateur de signets : les boutons s'y alignent en ligne,
# ou en colonne. La grille dépend d'un nombre de colonnes que le rapport
# n'écrit pas toujours : on n'y clique pas, on demande.
_HORIZONTAL = "0"
_VERTICAL = "1"


@dataclass
class Bookmark:
    """Un signet : son nom, son groupe, et ce qu'il masque ou montre par page."""

    name: str
    title: str
    group: str = ""
    # Page → nom de visuel ou de groupe → masqué (`True`) ou montré (`False`).
    states: dict[str, dict[str, bool]] = field(default_factory=dict)


def load_bookmarks(report_dir: str) -> list[Bookmark]:
    """Les signets du rapport, dans l'ordre du volet Signets. Aucun, s'il n'y en a pas."""
    folder = os.path.join(report_dir, "definition", "bookmarks")
    if not os.path.isdir(folder):
        return []

    read = {}
    for file in sorted(os.listdir(folder)):
        if file.endswith(".bookmark.json"):
            bookmark = _parse(read_json(os.path.join(folder, file)) or {})
            if bookmark is not None:
                read[bookmark.name] = bookmark

    ordered = []
    for name, group in _order(read_json(os.path.join(folder, "bookmarks.json")) or {}):
        if name in read:
            read[name].group = group
            ordered.append(read.pop(name))
    return ordered + list(read.values())


def _order(data: dict) -> list[tuple[str, str]]:
    """
    Ordre des signets dans `bookmarks.json`, avec le groupe de chacun.

    Un élément à enfants est un groupe : ses enfants sont les signets, dans
    l'ordre où le navigateur les aligne.
    """
    ordered = []
    for item in data.get("items") or []:
        name = _name(item)
        children = item.get("children") if isinstance(item, dict) else None
        if children:
            ordered += [(_name(child), name) for child in children]
        elif name:
            ordered.append((name, ""))
    return ordered


def _name(item) -> str:
    return item if isinstance(item, str) else str((item or {}).get("name") or "")


def _parse(data: dict) -> Bookmark | None:
    """Ce que le signet masque et montre, page par page."""
    name = data.get("name")
    if not name:
        return None

    options = data.get("options") or {}
    targets = set(options.get("targetVisualNames") or [])
    only_targets = bool(options.get("applyOnlyToTargetVisuals")) and bool(targets)

    states: dict[str, dict[str, bool]] = {}
    sections = (data.get("explorationState") or {}).get("sections") or {}
    for page, section in sections.items():
        declared = {}
        for visual, node in (section.get("visualContainers") or {}).items():
            display = (node.get("singleVisual") or {}).get("display") or {}
            declared[visual] = str(display.get("mode", "")).lower() == "hidden"
        for group, node in (section.get("visualContainerGroups") or {}).items():
            declared[group] = bool((node or {}).get("isHidden"))
        if only_targets:
            declared = {item: hidden for item, hidden in declared.items() if item in targets}
        if declared:
            states[page] = declared

    return Bookmark(name, str(data.get("displayName") or name), states=states)


def attach_views(page: ReportPage, bookmarks: list[Bookmark]) -> None:
    """
    Renseigne ce qui est masqué à l'ouverture de la page, et ses affichages.

    Un signet fait un affichage sur chaque page où il déclare quelque chose.
    Celui qui remet la page telle qu'elle s'ouvre en est un aussi : c'est lui
    qui permet de la rendre dans cet état, une fois les autres parcourus.
    """
    parents = {item.name: item.parent_group_name for item in (*page.groups, *page.visuals)}
    hidden_raw = {item.name for item in (*page.groups, *page.visuals) if item.is_hidden}
    page.hidden_by_default = _effective(hidden_raw, parents)

    page.views = []
    for bookmark in bookmarks:
        declared = bookmark.states.get(page.name)
        if not declared:
            continue
        raw = {item for item in hidden_raw if declared.get(item, True)}
        raw |= {item for item, hidden in declared.items() if hidden}
        trigger, selected = _trigger(bookmark, page.bookmark_controls, bookmarks)
        note = "" if trigger else _unreachable(bookmark, page.bookmark_controls, bookmarks)
        page.views.append(
            PageView(
                bookmark.name,
                bookmark.title,
                _effective(raw, parents),
                _effective(set(declared), parents),
                trigger,
                selected if selected != bookmark.name else "",
                note,
            )
        )


def _effective(hidden: set[str], parents: dict[str, str]) -> set[str]:
    """Ce qui est masqué, en comptant ce qu'un groupe masqué emporte avec lui."""
    return {name for name in parents if _hidden(name, hidden, parents)} | hidden


def _hidden(name: str, hidden: set[str], parents: dict[str, str]) -> bool:
    seen = set()
    while name and name not in seen:
        if name in hidden:
            return True
        seen.add(name)
        name = parents.get(name, "")
    return False


def _trigger(
    bookmark: Bookmark, controls: list[BookmarkControl], bookmarks: list[Bookmark]
) -> tuple[_Area | None, str]:
    """
    Où cliquer, sur la page, pour appliquer ce signet.

    Un bouton qui l'applique, d'abord : il n'y a qu'à viser son centre. Sinon,
    un navigateur qui l'aligne : ses boutons se partagent sa place à parts
    égales, dans l'ordre des signets de son groupe — la case du signet est
    celle de son rang.

    Avec la zone, le signet que ce navigateur a sélectionné à l'ouverture :
    c'est lui qui remet ce que le signet change.
    """
    for control in controls:
        if control.bookmark == bookmark.name:
            return _box(control), ""

    for control in controls:
        if not control.is_navigator:
            continue
        listed = [b.name for b in bookmarks if not control.group or b.group == control.group]
        if bookmark.name not in listed:
            continue
        cell = _cell(control, listed.index(bookmark.name), len(listed))
        if cell is not None:
            return cell, control.selected
    return None, ""


def _unreachable(
    bookmark: Bookmark, controls: list[BookmarkControl], bookmarks: list[Bookmark]
) -> str:
    """
    Ce qu'on a trouvé sur la page, quand rien n'y mène à ce signet.

    Le compte rendu le dit : c'est ce qui permet de comprendre, sans ouvrir
    le rapport, pourquoi un navigateur bien visible ne sert pas.
    """
    navigators = [control for control in controls if control.is_navigator]
    if not navigators and not controls:
        return "aucun navigateur ni bouton de signet sur la page"
    group = bookmark.group or "aucun"
    seen = ", ".join(
        f"{control.visual.name[:8]} (groupe {control.group or 'tous'})" for control in navigators
    )
    listed = sum(1 for b in bookmarks if b.group == bookmark.group)
    return (
        f"signet du groupe {group} ({listed} signet(s)) ; navigateurs de la page : "
        f"{seen or 'aucun'}"
    )


def _box(control: BookmarkControl) -> tuple[float, float, float, float]:
    visual = control.visual
    return (visual.pos_x, visual.pos_y, visual.width, visual.height)


def _cell(control: BookmarkControl, rank: int, count: int) -> _Area | None:
    """La case du navigateur qui porte le bouton de ce rang."""
    x, y, width, height = _box(control)
    orientation = control.orientation or _HORIZONTAL
    if orientation not in (_HORIZONTAL, _VERTICAL):
        # Une grille : le rapport n'en écrit pas les colonnes. Une grille plus
        # large que haute tient ses boutons sur une ligne, sinon en colonne —
        # ce qui vaut pour les navigateurs de deux ou trois boutons.
        orientation = _HORIZONTAL if width >= height else _VERTICAL
    if orientation == _HORIZONTAL:
        return (x + width * rank / count, y, width / count, height)
    if orientation == _VERTICAL:
        return (x, y + height * rank / count, width, height / count)
    return None
