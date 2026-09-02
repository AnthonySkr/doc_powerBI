"""Pages, groupes et visuels du rapport (`Report/definition/pages/`)."""

import json
import os
from typing import Any

from src import console
from src.models.data_models import ReportPage, Visual, VisualGroup
from src.parsers.report.fields import parse_elements, parse_filters, parse_reference_labels

# Titre de repli d'un groupe dont le `displayName` est vide.
UNTITLED_GROUP = "Groupe sans nom"


def load_page_order(pages_dir: str) -> dict[str, int]:
    """Ordre d'affichage des pages, depuis `pages.json` → {dossier: rang}."""
    data = read_json(os.path.join(pages_dir, "pages.json"))
    return {name: index for index, name in enumerate((data or {}).get("pageOrder", []))}


def parse_page(page_path: str, folder_name: str, page_order: dict[str, int]) -> ReportPage | None:
    """Parse un dossier de page : `page.json` puis `visuals/*/visual.json`."""
    data = read_json(os.path.join(page_path, "page.json"))
    if data is None:
        return None

    page = ReportPage(
        name=folder_name,
        display_name=data.get("displayName", folder_name),
        order=page_order.get(folder_name, data.get("ordinal", 999)),
        is_hidden=str(data.get("visibility", "")).lower().startswith("hidden"),
        filters=parse_filters(data.get("filters", [])),
    )

    visuals_dir = os.path.join(page_path, "visuals")
    if not os.path.isdir(visuals_dir):
        return page

    for folder in sorted(os.listdir(visuals_dir)):
        container = parse_container(os.path.join(visuals_dir, folder, "visual.json"), folder)
        if isinstance(container, VisualGroup):
            page.groups.append(container)
        elif container is not None:
            page.visuals.append(container)

    return page


def parse_container(visual_json_path: str, folder_name: str) -> Visual | VisualGroup | None:
    """
    Parse un `visual.json`.

    Le fichier décrit soit un visuel (`visual`), soit un conteneur de groupe
    (`visualGroup`) — les deux clés s'excluent. Les visuels sont tous lus : le
    tri revient à `data.visuals`.
    """
    data = read_json(visual_json_path)
    if data is None:
        return None

    if data.get("visualGroup"):
        return parse_group(data, folder_name)
    return parse_visual(data, folder_name)


def parse_group(data: dict, folder_name: str) -> VisualGroup:
    """Conteneur de groupe : pas de contenu propre, mais un nom et une place."""
    node = data.get("visualGroup") or {}
    position = data.get("position") or {}

    return VisualGroup(
        id=folder_name,
        name=data.get("name") or folder_name,
        title=(node.get("displayName") or "").strip() or UNTITLED_GROUP,
        group_mode=node.get("groupMode", ""),
        parent_group_name=data.get("parentGroupName", ""),
        pos_x=float(position.get("x") or 0),
        pos_y=float(position.get("y") or 0),
    )


def parse_visual(data: dict, folder_name: str) -> Visual | None:
    """Visuel proprement dit : type, champs projetés, filtres et position."""
    node = data.get("visual") or {}
    if not node:
        return None

    visual_type = node.get("visualType", "unknown")
    # Une carte porte ses étiquettes de référence hors de la requête : leurs
    # champs rejoignent les projections, ce sont des champs affichés comme
    # les autres.
    elements = parse_elements(node.get("query") or {}) + parse_reference_labels(node)
    position = data.get("position") or {}

    return Visual(
        id=folder_name,
        visual_type=visual_type,
        title=_title(node) or f"{visual_type} ({folder_name[:8]})",
        elements=elements,
        filters=parse_filters((data.get("filterConfig") or {}).get("filters", [])),
        has_measures=any(element.type_category == "Mesure" for element in elements),
        pos_x=float(position.get("x") or 0),
        pos_y=float(position.get("y") or 0),
        name=data.get("name") or folder_name,
        parent_group_name=data.get("parentGroupName", ""),
    )


def _title(visual_node: dict) -> str | None:
    """Titre saisi dans `visualContainerObjects.title`, s'il en existe un."""
    titles = (visual_node.get("visualContainerObjects") or {}).get("title") or []
    if not titles:
        return None

    node: Any = titles[0]
    for key in ("properties", "text", "expr", "Literal"):
        if not isinstance(node, dict):
            return None
        node = node.get(key, {})

    value = node.get("Value", "") if isinstance(node, dict) else ""
    return value.strip("'\"") or None


def read_json(path: str) -> dict | None:
    """Lit un fichier JSON du rapport. Retourne None si absent ou illisible."""
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as e:
        console.warn(f"Erreur de lecture de '{path}' : {e}")
        return None
