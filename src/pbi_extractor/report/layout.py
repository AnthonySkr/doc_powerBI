"""
Ramener chaque visuel et chaque groupe dans le repère de la page.

Le problème
───────────
Un membre de groupe déclare sa place tantôt dans le repère de la page, tantôt
dans celui du groupe qui le contient directement — selon la version de Power
BI qui a écrit le rapport. Dans le second cas, un groupe imbriqué se compte à
partir du coin de son parent, et ses visuels à partir du sien : la place d'un
visuel ne se lit qu'en remontant toute la chaîne des groupes.

Ne corriger que le dernier maillon donnait des cadres de la bonne taille,
posés au coin du canevas — c'est ce que montrait le calibrage.

Ce que fait ce module
─────────────────────
Il descend l'arbre des groupes depuis les groupes racines, dont la place est
toujours celle de la page. Pour chaque groupe, une fois sa propre place
établie, il décide du repère de ses membres directs — tous ensemble, un
groupe n'en mélange pas deux — puis les y ramène, et passe aux sous-groupes.

Pour décider, les deux lectures sont éprouvées contre le cadre déclaré du
groupe : celle qui tient tous les membres dans le cadre l'emporte ; si les
deux le font, ou aucune, celle dont l'étendue épouse le mieux ce cadre. Sans
cadre déclaré, rien ne permet de trancher : on garde ce que le rapport dit.

Après cela, `pos_x` et `pos_y` sont des coordonnées de page partout : le plan
de capture comme le tri par position les lisent sans rien savoir des groupes.
"""

from collections import defaultdict

from src.core.models import ReportPage, Visual, VisualGroup

__all__ = ["to_page_coordinates"]

# Tolérance, en unités du canevas, sur l'appartenance d'un membre au cadre de
# son groupe : Power BI arrondit, et un demi-point ne dit pas un changement de
# repère.
INSIDE = 1.0

type _Box = tuple[float, float, float, float]  # gauche, haut, droite, bas
type _Member = Visual | VisualGroup


def to_page_coordinates(page: ReportPage) -> None:
    """Réécrit en place la position des membres de groupe, en coordonnées de page."""
    names = {group.name for group in page.groups}
    members: dict[str, list[_Member]] = defaultdict(list)
    for item in (*page.groups, *page.visuals):
        parent = item.parent_group_name
        if parent in names and not (isinstance(item, VisualGroup) and parent == item.name):
            members[parent].append(item)

    # Les racines d'abord : leur place est celle de la page. Un groupe n'est
    # traité qu'une fois — un rapport retouché pourrait boucler.
    pending = [group for group in page.groups if group.parent_group_name not in names]
    settled: set[str] = set()
    while pending:
        group = pending.pop()
        if group.name in settled:
            continue
        settled.add(group.name)

        inside = members.get(group.name, [])
        if _relative(inside, group):
            for item in inside:
                item.pos_x += group.pos_x
                item.pos_y += group.pos_y
        pending += [item for item in inside if isinstance(item, VisualGroup)]


def _relative(members: list[_Member], group: VisualGroup) -> bool:
    """Les membres sont-ils placés à partir du coin du groupe ?"""
    frame = _box(group)
    placed = [_box(item) for item in members if item.width > 0 and item.height > 0]
    if not placed or group.width <= 0 or group.height <= 0:
        return False
    if group.pos_x == 0 and group.pos_y == 0:
        return False  # les deux lectures se confondent

    moved = [_shifted(box, group.pos_x, group.pos_y) for box in placed]
    as_page, as_group = _all_within(placed, frame), _all_within(moved, frame)
    if as_page != as_group:
        return as_group
    return _gap(_union(moved), frame) < _gap(_union(placed), frame)


def _box(item: _Member) -> _Box:
    return (item.pos_x, item.pos_y, item.pos_x + item.width, item.pos_y + item.height)


def _shifted(box: _Box, dx: float, dy: float) -> _Box:
    return (box[0] + dx, box[1] + dy, box[2] + dx, box[3] + dy)


def _all_within(boxes: list[_Box], frame: _Box) -> bool:
    return all(
        box[0] >= frame[0] - INSIDE
        and box[1] >= frame[1] - INSIDE
        and box[2] <= frame[2] + INSIDE
        and box[3] <= frame[3] + INSIDE
        for box in boxes
    )


def _union(boxes: list[_Box]) -> _Box:
    return (
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    )


def _gap(box: _Box, frame: _Box) -> float:
    """Écart entre deux rectangles, bord à bord."""
    return sum(abs(a - b) for a, b in zip(box, frame, strict=True))
