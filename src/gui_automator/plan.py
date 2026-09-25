"""
Ce qu'il y a à capturer, déduit du rapport déjà lu.

Le plan de capture se calcule **sans ouvrir Power BI** : les positions des
visuels viennent du rapport `.pbip`, que `pbi_extractor.report` a déjà lu. On
sait donc à l'avance combien de captures seront prises, de quoi, et à quel
endroit du canevas — de quoi vérifier le cadrage avant de lancer quoi que ce
soit (`python main.py <rapport> --capture-plan`).

Trois sortes de prises, une par emplacement que le document réserve :

    une page    le canevas entier, tel que la page le déclare
    un groupe   le cadre du groupe, ou l'étendue de ses visuels à défaut
    un visuel   sa place, telle que le rapport la déclare — y compris les
                visuels d'un groupe, qui sont documentés un à un

Le plan ne décide pas *ce qui* est documenté : il reçoit les pages telles que
`core.selection` les a organisées, et les suit.

    Visuels superposés — un navigateur de signets fait alterner au même
    endroit des visuels dont un seul est visible à la fois. La page est
    d'abord prise telle qu'elle s'ouvre, sans rien toucher, visuels masqués
    exclus. Puis chaque visuel masqué est pris sous un signet qui le montre,
    aussitôt défait (voir `View`). Un visuel masqué qu'aucun signet ne montre
    — ou qu'on ne saurait défaire — est décrit, mais pas capturé.

    Coordonnées d'un visuel de groupe — Power BI les écrit tantôt dans le
    repère de la page, tantôt dans celui du groupe qui le contient. La lecture
    du rapport les a déjà ramenées à la page, groupes imbriqués compris (voir
    `pbi_extractor.report.layout`) : le plan les prend telles quelles.
"""

from dataclasses import dataclass, field, replace

from src.core.models import ReportPage, Visual, VisualGroup
from src.gui_automator.geometry import Rect, Size, union

__all__ = [
    "GROUP",
    "PAGE",
    "PAGE_SHOT",
    "VISUAL",
    "PagePlan",
    "Shot",
    "View",
    "build",
    "count",
    "only",
    "without_bookmarks",
]

# Ce qu'une prise cadre : la page entière, un groupe, ou un visuel seul.
PAGE = "page"
VISUAL = "visual"
GROUP = "group"

# Nom de fichier de la capture d'une page entière. Le tiret bas la distingue
# des visuels, dont les noms techniques n'en portent pas au début.
PAGE_SHOT = "_page"


@dataclass(frozen=True)
class Shot:
    """Une capture à prendre : ce qu'elle cadre, et où c'est dans le canevas."""

    kind: str  # PAGE | GROUP | VISUAL
    name: str  # identifiant technique, stable d'une génération à l'autre
    title: str  # titre lisible, pour le compte rendu
    area: Rect  # place dans le canevas de la page
    # Signet à appliquer avant la prise — vide : la page telle qu'elle est.
    view: str = ""
    # Masqué dans tous les affichages : décrit, jamais capturé.
    hidden: bool = False
    # Pourquoi, quand c'est masqué : ce que le compte rendu en dit.
    note: str = ""

    @property
    def is_placed(self) -> bool:
        """
        Vrai si le rapport dit assez de la place de cet élément pour le cadrer.

        Un `visual.json` sans dimensions — retouché à la main, ou produit par
        un outil tiers — ne permet aucun recadrage : la prise est décrite, mais
        écartée à la capture plutôt que de livrer une image vide.
        """
        return not self.area.is_empty


_NOWHERE = Rect(0, 0, 0, 0)


@dataclass(frozen=True)
class View:
    """
    Un signet à appliquer sur la page, et où cliquer pour cela.

    `trigger` est une zone du canevas — la case du navigateur, ou le bouton —,
    vide quand aucun bouton de la page ne mène à ce signet.
    """

    name: str
    title: str
    trigger: Rect = _NOWHERE
    # Les signets à appliquer ensuite, pour rendre la page comme à l'ouverture.
    undo: tuple[str, ...] = ()


@dataclass(frozen=True)
class PagePlan:
    """Les prises d'une page, dans le canevas qui leur donne leur échelle."""

    name: str  # dossier de la page — sert de nom de fichier
    title: str  # `displayName`, pour le compte rendu
    canvas: Size
    shots: list[Shot] = field(default_factory=list)
    # Rang de la page dans le rapport, onglets cachés compris. C'est lui qui
    # permet d'aller d'une page à l'autre au clavier (voir `desktop`).
    order: int = 0
    # Les signets que les prises demandent, et ceux qui les défont.
    views: list[View] = field(default_factory=list)

    def view(self, name: str) -> View | None:
        return next((view for view in self.views if view.name == name), None)

    def shots_for(self, view: str) -> list[Shot]:
        return [shot for shot in self.shots if shot.view == view]


def build(pages: list[ReportPage]) -> list[PagePlan]:
    """Plan de capture des pages données, dans leur ordre."""
    return [_page_plan(page) for page in pages]


def count(plans: list[PagePlan]) -> int:
    """Nombre de prises que le plan prévoit réellement."""
    return sum(1 for plan in plans for shot in plan.shots if shot.is_placed and not shot.hidden)


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
            kept.append(replace(plan, shots=shots))
    return kept


def without_bookmarks(plan: PagePlan) -> PagePlan:
    """Le plan sans aucun clic : ce qui demandait un signet est écarté."""
    shots = [
        replace(shot, view="", hidden=True, note="masqué à l'ouverture (signets coupés)")
        if shot.view
        else shot
        for shot in plan.shots
    ]
    return replace(plan, shots=shots, views=[])


def _page_plan(page: ReportPage) -> PagePlan:
    canvas = Size(page.canvas_width, page.canvas_height)
    undos = _undoable(page)
    shots = [_in_view(shot, page, undos) for shot in _shots(page, canvas)]

    # Tous les signets de la page, même ceux qu'aucune prise ne demande : le
    # calibrage montre où chacun serait cliqué.
    views = [
        View(
            view.name,
            view.title,
            Rect(*view.trigger) if view.trigger else _NOWHERE,
            tuple(undos.get(view.name, ())),
        )
        for view in page.views
    ]
    return PagePlan(page.name, page.display_name, canvas, shots, page.order, views)


def _undoable(page: ReportPage) -> dict[str, list[str]]:
    """
    Les signets qu'on sait appliquer **et défaire**, avec de quoi les défaire.

    Un signet n'est appliqué que si un clic y mène, et si d'autres, sur la
    même page, remettent ensuite comme à l'ouverture tout ce qu'il a changé :
    le « Chiffrage » d'un navigateur défait son « Évolution », la croix d'une
    fenêtre de filtres défait le bouton qui l'a ouverte. Un signet qu'on ne
    saurait pas défaire laisserait la page masquée pour toutes les prises
    suivantes — on ne l'applique pas.
    """
    clickable = [view for view in page.views if view.trigger]
    undos = {}
    for view in clickable:
        remaining = {
            name
            for name in view.touched
            if (name in view.hidden) != (name in page.hidden_by_default)
        }
        chosen = []
        for other in clickable:
            if other is view or not other.touched & remaining:
                continue
            if other.hidden & other.touched == page.hidden_by_default & other.touched:
                chosen.append(other.name)
                remaining -= other.touched
        if remaining and view.selected in {other.name for other in clickable}:
            # Le navigateur dit lequel de ses signets était actif à l'ouverture :
            # c'est lui qui remet ce que celui-ci change, même s'il touche
            # aussi à autre chose.
            chosen, remaining = [view.selected], set()
        if not remaining:
            undos[view.name] = chosen
    return undos


def _in_view(shot: Shot, page: ReportPage, undos: dict[str, list[str]]) -> Shot:
    """
    La prise, rangée dans l'affichage où la prendre.

    Ce qui est visible à l'ouverture se prend tel quel, sans rien toucher :
    c'est le cas de presque tout. Ce qui est masqué à l'ouverture se prend
    sous le premier signet qui le montre **explicitement** et qu'on sait
    défaire. Le reste n'est pas pris : cadrer un visuel masqué, ce serait
    photographier celui qui est à sa place.
    """
    if shot.kind == PAGE or shot.name not in page.hidden_by_default:
        return shot

    showing = [
        view for view in page.views if shot.name in view.touched and shot.name not in view.hidden
    ]
    for view in showing:
        if view.name in undos:
            return replace(shot, view=view.name)

    if not showing:
        note = "masqué à l'ouverture, et aucun signet ne l'affiche"
    elif not any(view.trigger for view in showing):
        note = (
            f"masqué ; « {showing[0].title} » l'affiche, mais aucun bouton de la page "
            f"n'y mène ({showing[0].note})"
        )
    else:
        note = f"masqué ; « {showing[0].title} » l'affiche, mais aucun signet ne le défait"
    return replace(shot, hidden=True, note=note)


def _shots(page: ReportPage, canvas: Size) -> list[Shot]:
    """
    Prises d'une page : la page entière, ses groupes, puis tous ses visuels.

    Une prise par emplacement que le document réserve — il en réserve un pour
    la page, un par groupe et un par visuel documenté, **y compris ceux d'un
    groupe**, dont il détaille chacun sous la capture d'ensemble.

    `core.selection.organize_page` a déjà réparti les visuels documentés entre
    les groupes et `ungrouped_visuals`, et `page.visuals` les porte tous. Sans
    lui — le plan est aussi calculable sur un rapport tout juste lu — la page
    n'a que ses visuels bruts, et ce sont eux qui servent.
    """
    shots = [Shot(PAGE, PAGE_SHOT, page.display_name, Rect(0, 0, canvas.width, canvas.height))]
    shots += [_group_shot(group) for group in page.groups]

    seen: set[str] = set()
    for visual in page.visuals or page.ungrouped_visuals:
        name = visual.name or visual.id
        if name in seen:
            continue
        seen.add(name)
        shots.append(Shot(VISUAL, name, visual.title, _area(visual)))
    return shots


def _group_shot(group: VisualGroup) -> Shot:
    """
    Prise d'un groupe : son cadre déclaré, ou l'étendue de ses visuels.

    Le cadre déclaré vaut mieux : c'est celui que Power BI dessine, espaces
    compris, quand l'étendue des visuels s'arrête au dernier d'entre eux. Les
    rapports qui ne le déclarent pas — anciens, ou retouchés — gardent le
    calcul par étendue, sous-groupes compris.
    """
    return Shot(GROUP, group.name or group.id, group.title, _frame(group))


def _frame(group: VisualGroup) -> Rect:
    """Cadre du groupe dans le canevas de la page."""
    declared = Rect(group.pos_x, group.pos_y, group.width, group.height)
    if not declared.is_empty:
        return declared
    return union([_area(visual) for visual in _all_visuals(group)])


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
