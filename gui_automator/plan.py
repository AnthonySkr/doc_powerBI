"""
Ce qu'il y a à capturer, déduit du rapport déjà lu.

Le plan de capture se calcule **sans ouvrir Power BI** : les positions des
visuels viennent du rapport `.pbip`, que `pbi_extractor.report` a déjà lu. On
sait donc à l'avance combien de captures seront prises, de quoi, et à quel
endroit du canevas — de quoi vérifier le cadrage avant de lancer quoi que ce
soit (`python -m gui_automator --plan`).

Deux sortes de prises :

    un visuel   sa place, telle que le rapport la déclare
    un groupe   l'étendue de ses visuels documentés, que Power BI ne
                déclare pas — elle se déduit de leurs places

Le plan ne décide pas *ce qui* est documenté : il reçoit les pages telles que
`generators.filters` les a organisées, et les suit.
"""

from dataclasses import dataclass, field

from core.models import ReportPage, Visual, VisualGroup
from gui_automator.geometry import Rect, Size, union

__all__ = ["GROUP", "VISUAL", "PagePlan", "Shot", "build", "count", "only"]

# Ce qu'une prise cadre : un visuel seul, ou un groupe entier.
VISUAL = "visual"
GROUP = "group"


@dataclass(frozen=True)
class Shot:
    """Une capture à prendre : ce qu'elle cadre, et où c'est dans le canevas."""

    kind: str  # VISUAL | GROUP
    name: str  # identifiant technique, stable d'une génération à l'autre
    title: str  # titre lisible, pour le compte rendu
    area: Rect  # place dans le canevas de la page

    @property
    def is_placed(self) -> bool:
        """
        Vrai si le rapport dit assez de la place de cet élément pour le cadrer.

        Un `visual.json` sans dimensions — retouché à la main, ou produit par
        un outil tiers — ne permet aucun recadrage : la prise est décrite, mais
        écartée à la capture plutôt que de livrer une image vide.
        """
        return not self.area.is_empty


@dataclass(frozen=True)
class PagePlan:
    """Les prises d'une page, dans le canevas qui leur donne leur échelle."""

    name: str  # dossier de la page — sert de nom de fichier
    title: str  # `displayName`, pour le compte rendu
    canvas: Size
    shots: list[Shot] = field(default_factory=list)


def build(pages: list[ReportPage]) -> list[PagePlan]:
    """Plan de capture des pages données, dans leur ordre."""
    return [_page_plan(page) for page in pages]


def count(plans: list[PagePlan]) -> int:
    """Nombre de prises que le plan prévoit réellement."""
    return sum(1 for plan in plans for shot in plan.shots if shot.is_placed)


def only(plans: list[PagePlan], page: str = "", shot: str = "") -> list[PagePlan]:
    """
    Restreint le plan à une page, à une prise, ou aux deux.

    Sert à éprouver une capture à la main sans dérouler tout le rapport : la
    comparaison porte sur le nom technique comme sur le titre, et ne tient
    compte ni de la casse ni de la place du fragment.
    """
    kept = []
    for plan in plans:
        if page and not _matches(page, plan.name, plan.title):
            continue
        shots = [s for s in plan.shots if not shot or _matches(shot, s.name, s.title)]
        if shots:
            kept.append(PagePlan(plan.name, plan.title, plan.canvas, shots))
    return kept


def _page_plan(page: ReportPage) -> PagePlan:
    canvas = Size(page.canvas_width, page.canvas_height)
    return PagePlan(page.name, page.display_name, canvas, _shots(page))


def _shots(page: ReportPage) -> list[Shot]:
    """
    Prises d'une page : ses groupes documentés, puis ses visuels isolés.

    `generators.filters.organize_page` a déjà réparti les visuels entre les
    groupes et `ungrouped_visuals`. Sans lui — le plan est aussi calculable sur
    un rapport tout juste lu — la page n'a que `visuals`, et c'est elle qui
    sert.
    """
    grouped = [_group_shot(group) for group in page.groups]
    isolated = page.ungrouped_visuals or (page.visuals if not page.groups else [])
    return grouped + [_visual_shot(visual) for visual in isolated]


def _visual_shot(visual: Visual) -> Shot:
    return Shot(VISUAL, visual.name or visual.id, visual.title, _area(visual))


def _group_shot(group: VisualGroup) -> Shot:
    """
    Prise d'un groupe : l'étendue de ses visuels documentés.

    Un groupe déclare son coin supérieur gauche, jamais ses dimensions. Ses
    sous-groupes sont traversés — `filters` les rattache au groupe racine, mais
    leurs visuels comptent dans l'étendue.
    """
    areas = [_area(visual) for visual in _all_visuals(group)]
    return Shot(GROUP, group.name or group.id, group.title, union(areas))


def _all_visuals(group: VisualGroup) -> list[Visual]:
    visuals = list(group.visuals)
    for subgroup in group.subgroups:
        visuals += _all_visuals(subgroup)
    return visuals


def _area(visual: Visual) -> Rect:
    return Rect(visual.pos_x, visual.pos_y, visual.width, visual.height)


def _matches(fragment: str, *candidates: str) -> bool:
    needle = fragment.strip().lower()
    return any(needle in (candidate or "").lower() for candidate in candidates)
