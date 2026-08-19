"""Pages et visuels du rapport (`Report/definition/pages/`)."""

import json
import os
from typing import Any

from src import console
from src.models.data_models import ReportPage, Visual
from src.parsers.report.fields import parse_elements, parse_filters


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
        visual = parse_visual(os.path.join(visuals_dir, folder, "visual.json"), folder)
        if visual:
            page.visuals.append(visual)

    return page


def parse_visual(visual_json_path: str, folder_name: str) -> Visual | None:
    """Parse un `visual.json`. Les visuels sont tous lus : le tri revient à `data.visuals`."""
    data = read_json(visual_json_path)
    if data is None:
        return None

    node = data.get("visual") or {}
    if node.get("visualGroup"):
        return None  # conteneur de groupe : pas de contenu propre à documenter

    visual_type = node.get("visualType", "unknown")
    elements = parse_elements(node.get("query") or {})
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
